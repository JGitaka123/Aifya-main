import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.models.pharmacy import (
    Dispensing,
    PharmacyBatch,
    PharmacyItem,
    StockTransaction,
)
from app.models.prescription import Prescription
from app.schemas.pharmacy import (
    DispenseRequest,
    PharmacyItemCreate,
    PharmacyItemUpdate,
    PharmacyQueueItem,
    StockAdjustmentRequest,
    StockAlert,
    StockReceiptRequest,
)
from app.services.finance import post_compound_transaction
from app.services.service_billing import PRESCRIPTION, ServiceBillingService

_logger = logging.getLogger(__name__)


class PharmacyService:
    """
    Service layer for pharmacy operations: inventory, dispensing, stock management.
    Drug interaction checks MUST have passed before dispensing (CLAUDE.md).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Pharmacy Queue ────────────────────────────────────────────────────

    async def get_pending_prescriptions(
        self, facility_id: uuid.UUID
    ) -> tuple[list[PharmacyQueueItem], int]:
        """
        Get prescriptions pending dispensing (the pharmacy queue).
        Ordered by creation time (FIFO).

        @param facility_id: Facility UUID
        @returns Tuple of (queue items, total count)
        """
        stmt = (
            select(Prescription, Patient)
            .join(Patient, Prescription.patient_id == Patient.id)
            .where(
                Prescription.facility_id == facility_id,
                Prescription.status.in_(["pending", "partially_dispensed"]),
                Prescription.is_deleted == False,  # noqa: E712
            )
            .order_by(Prescription.created_at.asc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[PharmacyQueueItem] = []
        for rx, patient in rows:
            items.append(
                PharmacyQueueItem(
                    prescription_id=rx.id,
                    encounter_id=rx.encounter_id,
                    patient_id=rx.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    drug_name=rx.drug_name,
                    generic_name=rx.generic_name,
                    is_keml=rx.is_keml,
                    dosage=rx.dosage,
                    route=rx.route,
                    frequency=rx.frequency,
                    duration_days=rx.duration_days,
                    quantity=rx.quantity,
                    instructions=rx.instructions,
                    prescriber_id=rx.prescriber_id,
                    status=rx.status,
                    created_at=rx.created_at,
                )
            )

        return items, len(items)

    # ── Dispensing ────────────────────────────────────────────────────────

    async def dispense(
        self,
        data: DispenseRequest,
        facility_id: uuid.UUID,
        dispensed_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Dispensing:
        """
        Dispense a prescription. Validates stock, deducts inventory,
        updates prescription status. Idempotent per X-Idempotency-Key —
        a retried request returns the original dispensing instead of
        deducting stock twice.

        @param data: Dispense request data
        @param facility_id: Facility UUID
        @param dispensed_by: Pharmacist staff UUID
        @param idempotency_key: Optional client key for safe retries
        @returns Dispensing record
        @raises ValueError: If prescription not found, already dispensed, or stock insufficient
        """
        if idempotency_key:
            event_result = await self.db.execute(
                select(EventBase).where(
                    EventBase.idempotency_key == idempotency_key,
                    EventBase.facility_id == facility_id,
                    EventBase.event_type == "PrescriptionDispensed",
                )
            )
            event = event_result.scalar_one_or_none()
            if event is not None:
                dispensing_id = (event.event_data or {}).get("dispensing_id")
                if dispensing_id:
                    existing = await self.db.execute(
                        select(Dispensing).where(
                            Dispensing.id == uuid.UUID(dispensing_id)
                        )
                    )
                    dispensing = existing.scalar_one_or_none()
                    if dispensing is not None:
                        return dispensing

        # Fetch prescription with a row lock: the status/quantity guards below
        # must hold under concurrent dispense attempts (double-dispense race).
        rx_result = await self.db.execute(
            select(Prescription)
            .where(
                Prescription.id == data.prescription_id,
                Prescription.facility_id == facility_id,
                Prescription.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
        rx = rx_result.scalar_one_or_none()
        if not rx:
            raise ValueError("Prescription not found")
        if rx.status not in ("pending", "partially_dispensed"):
            raise ValueError(f"Prescription cannot be dispensed (status: {rx.status})")
        if data.patient_id != rx.patient_id:
            raise ValueError("Patient does not match the prescription")

        self._validate_interaction_safety(rx)

        # Never dispense more than the prescriber ordered (remaining balance).
        if rx.quantity:
            remaining = rx.quantity - (rx.dispensed_quantity or 0)
            if data.quantity_dispensed > remaining:
                raise ValueError(
                    f"Quantity exceeds prescription: {remaining} remaining of "
                    f"{rx.quantity} prescribed, {data.quantity_dispensed} requested"
                )

        # Payment is a precondition of dispensing: the patient settles the
        # prescription at the cashier and shows the receipt here. A
        # prescription with no charge on the bill passes through.
        billing = ServiceBillingService(self.db)
        prescription_charge = await billing.charge_for(
            facility_id, PRESCRIPTION, rx.id
        )
        await billing.assert_service_paid(
            facility_id, PRESCRIPTION, rx.id, label="Prescription"
        )

        # Check stock if pharmacy item linked
        pharmacy_item: PharmacyItem | None = None
        unit_price: int | None = None
        if data.pharmacy_item_id:
            item_result = await self.db.execute(
                select(PharmacyItem).where(
                    PharmacyItem.id == data.pharmacy_item_id,
                    PharmacyItem.facility_id == facility_id,
                    PharmacyItem.is_deleted == False,  # noqa: E712
                ).with_for_update()
            )
            pharmacy_item = item_result.scalar_one_or_none()
            if not pharmacy_item:
                raise ValueError("Pharmacy item not found")
            self._check_drug_identity(rx, pharmacy_item, data)
            # FEFO: only non-expired batch stock counts as dispensable.
            usable = await self._usable_batch_quantity(pharmacy_item.id)
            if usable < data.quantity_dispensed:
                raise ValueError(
                    f"Insufficient non-expired stock: {usable} available, "
                    f"{data.quantity_dispensed} requested"
                )
            unit_price = pharmacy_item.selling_price_cents

        total_price = (
            unit_price * data.quantity_dispensed if unit_price else None
        )

        # Create dispensing record
        dispensing = Dispensing(
            facility_id=facility_id,
            prescription_id=data.prescription_id,
            patient_id=data.patient_id,
            pharmacy_item_id=data.pharmacy_item_id,
            dispensed_by=dispensed_by,
            drug_name=rx.drug_name,
            quantity_requested=rx.quantity or data.quantity_dispensed,
            quantity_dispensed=data.quantity_dispensed,
            substitution_drug=data.substitution_drug,
            substitution_reason=data.substitution_reason,
            dosage_instructions=data.dosage_instructions,
            counseling_done=data.counseling_done,
            counseling_notes=data.counseling_notes,
            unit_price_cents=unit_price,
            total_price_cents=total_price,
            payment_status=(
                "paid" if prescription_charge is not None else "pending"
            ),
            payment_method=data.payment_method,
            created_by=dispensed_by,
            updated_by=dispensed_by,
        )

        self.db.add(dispensing)
        await self.db.flush()
        await self.db.refresh(dispensing)

        # Deduct stock — consume batches earliest-expiry-first (FEFO)
        consumed_batches: list[str] = []
        if pharmacy_item:
            qty_before = pharmacy_item.current_quantity
            consumed_batches = await self._consume_batches_fefo(
                pharmacy_item, data.quantity_dispensed, dispensed_by
            )
            pharmacy_item.current_quantity -= data.quantity_dispensed
            qty_after = pharmacy_item.current_quantity
            await self._refresh_item_batch_summary(pharmacy_item)

            stock_tx = StockTransaction(
                facility_id=facility_id,
                pharmacy_item_id=pharmacy_item.id,
                dispensing_id=dispensing.id,
                transaction_type="dispensing",
                quantity_change=-data.quantity_dispensed,
                quantity_before=qty_before,
                quantity_after=qty_after,
                unit_cost_cents=unit_price,
                created_by=dispensed_by,
                updated_by=dispensed_by,
            )
            self.db.add(stock_tx)

        # Update prescription status
        rx.dispensed_by = dispensed_by
        rx.dispensed_at = datetime.now(UTC)
        rx.dispensed_quantity = (rx.dispensed_quantity or 0) + data.quantity_dispensed
        rx.unit_cost_cents = unit_price
        rx.total_cost_cents = total_price

        if rx.quantity and rx.dispensed_quantity < rx.quantity:
            rx.status = "partially_dispensed"
        else:
            rx.status = "dispensed"

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="prescription",
            stream_id=data.patient_id,
            event_type="PrescriptionDispensed",
            event_data={
                "dispensing_id": str(dispensing.id),
                "prescription_id": str(data.prescription_id),
                "drug_name": rx.drug_name,
                "quantity_dispensed": data.quantity_dispensed,
                "batches_consumed": consumed_batches,
                "substitution": data.substitution_drug,
                "counseling_done": data.counseling_done,
            },
            version=1,
            created_by=dispensed_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        # GL postings must never block dispensing (e.g. a locked period) —
        # post inside a SAVEPOINT so any GL failure rolls back only the ledger
        # entries, never the dispense/stock write, then log and continue.
        try:
            async with self.db.begin_nested():
                # GL: Pharmacy Revenue — DR 1100 AR / CR 4010 Pharmacy Revenue
                if total_price:
                    revenue_amount = Decimal(total_price) / Decimal("100")
                    await post_compound_transaction(
                        db=self.db,
                        facility_id=facility_id,
                        entries=[
                            {"account_code": "1100", "debit": revenue_amount, "credit": Decimal("0")},
                            {"account_code": "4010", "debit": Decimal("0"), "credit": revenue_amount},
                        ],
                        metadata={"event_type": "pharmacy_dispensed", "description": f"Pharmacy: {rx.drug_name} x{data.quantity_dispensed}"},
                        idempotency_key=f"pharmacy_dispensed:{dispensing.id}",
                        user_id=dispensed_by,
                    )
                # GL: COGS — DR 5100 Cost of Goods Sold / CR 1300 Drug Inventory
                if pharmacy_item and pharmacy_item.buying_price_cents:
                    cogs_amount = Decimal(pharmacy_item.buying_price_cents * data.quantity_dispensed) / Decimal("100")
                    await post_compound_transaction(
                        db=self.db,
                        facility_id=facility_id,
                        entries=[
                            {"account_code": "5100", "debit": cogs_amount, "credit": Decimal("0")},
                            {"account_code": "1300", "debit": Decimal("0"), "credit": cogs_amount},
                        ],
                        metadata={"event_type": "pharmacy_cogs", "description": f"COGS: {rx.drug_name} x{data.quantity_dispensed}"},
                        idempotency_key=f"pharmacy_cogs:{dispensing.id}",
                        user_id=dispensed_by,
                    )
        except Exception as exc:
            _logger.warning(
                "pharmacy.gl.post_failed dispensing=%s error=%s", dispensing.id, exc
            )

        return dispensing

    @staticmethod
    def _validate_interaction_safety(rx: Prescription) -> None:
        """
        Ensure dispensing cannot bypass the prescription safety check.

        @param rx: Locked prescription being dispensed
        @raises ValueError: If the check is missing, malformed, or critical
        """
        if not rx.interaction_checked:
            raise ValueError(
                "Prescription cannot be dispensed: drug interaction check not completed"
            )

        interactions = rx.interactions
        if interactions is None:
            return
        if not isinstance(interactions, list):
            raise ValueError(
                "Prescription cannot be dispensed: interaction check result is invalid"
            )

        for interaction in interactions:
            if not isinstance(interaction, dict):
                raise ValueError(
                    "Prescription cannot be dispensed: interaction check result is invalid"
                )
            severity = interaction.get("severity")
            if isinstance(severity, str) and severity.lower() == "critical":
                raise ValueError(
                    "Prescription cannot be dispensed: critical drug interaction present"
                )


    async def _usable_batch_quantity(self, pharmacy_item_id: uuid.UUID) -> int:
        """
        Total non-expired stock across an item's batches.

        @param pharmacy_item_id: Pharmacy item UUID
        @returns Sum of quantity_remaining over non-expired batches
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(PharmacyBatch.quantity_remaining), 0)).where(
                PharmacyBatch.pharmacy_item_id == pharmacy_item_id,
                PharmacyBatch.quantity_remaining > 0,
                PharmacyBatch.is_deleted == False,  # noqa: E712
                (PharmacyBatch.expiry_date.is_(None))
                | (PharmacyBatch.expiry_date >= date.today()),
            )
        )
        return int(result.scalar_one())

    async def _consume_batches_fefo(
        self,
        pharmacy_item: PharmacyItem,
        quantity: int,
        consumed_by: uuid.UUID,
    ) -> list[str]:
        """
        Consume stock from non-expired batches, earliest expiry first
        (batches without an expiry are used last). Caller must have
        verified availability via _usable_batch_quantity.

        @param pharmacy_item: The (row-locked) pharmacy item
        @param quantity: Units to consume
        @param consumed_by: Staff UUID
        @returns Batch numbers consumed from (for the audit event)
        @raises ValueError: If non-expired batch stock is insufficient
        """
        result = await self.db.execute(
            select(PharmacyBatch)
            .where(
                PharmacyBatch.pharmacy_item_id == pharmacy_item.id,
                PharmacyBatch.quantity_remaining > 0,
                PharmacyBatch.is_deleted == False,  # noqa: E712
                (PharmacyBatch.expiry_date.is_(None))
                | (PharmacyBatch.expiry_date >= date.today()),
            )
            .order_by(
                PharmacyBatch.expiry_date.is_(None),
                PharmacyBatch.expiry_date.asc(),
                PharmacyBatch.received_at.asc(),
            )
            .with_for_update()
        )
        batches = list(result.scalars().all())

        remaining = quantity
        consumed: list[str] = []
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_remaining, remaining)
            batch.quantity_remaining -= take
            batch.updated_by = consumed_by
            remaining -= take
            consumed.append(batch.batch_number or "unbatched")
        if remaining > 0:
            raise ValueError(
                f"Insufficient non-expired stock during FEFO consumption "
                f"({remaining} short)"
            )
        return consumed

    async def _consume_batches_for_adjustment(
        self,
        pharmacy_item: PharmacyItem,
        quantity: int,
        adjusted_by: uuid.UUID,
    ) -> None:
        """
        Consume stock for a negative adjustment: expired batches first
        (typical write-off), then FEFO across the rest.

        @param pharmacy_item: Pharmacy item
        @param quantity: Units to remove (positive number)
        @param adjusted_by: Staff UUID
        @raises ValueError: If batch stock is insufficient
        """
        result = await self.db.execute(
            select(PharmacyBatch)
            .where(
                PharmacyBatch.pharmacy_item_id == pharmacy_item.id,
                PharmacyBatch.quantity_remaining > 0,
                PharmacyBatch.is_deleted == False,  # noqa: E712
            )
            .order_by(
                # Expired first, then earliest expiry, then oldest receipt.
                (PharmacyBatch.expiry_date.is_(None))
                | (PharmacyBatch.expiry_date >= date.today()),
                PharmacyBatch.expiry_date.is_(None),
                PharmacyBatch.expiry_date.asc(),
                PharmacyBatch.received_at.asc(),
            )
            .with_for_update()
        )
        batches = list(result.scalars().all())
        remaining = quantity
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_remaining, remaining)
            batch.quantity_remaining -= take
            batch.updated_by = adjusted_by
            remaining -= take
        if remaining > 0:
            raise ValueError(
                f"Adjustment exceeds batch stock ({remaining} short)"
            )

    async def _refresh_item_batch_summary(self, pharmacy_item: PharmacyItem) -> None:
        """
        Keep the item's legacy batch_number/expiry_date columns pointing at
        the earliest-expiring batch that still has stock (display compat).

        @param pharmacy_item: Pharmacy item to refresh
        """
        await self.db.flush()
        result = await self.db.execute(
            select(PharmacyBatch)
            .where(
                PharmacyBatch.pharmacy_item_id == pharmacy_item.id,
                PharmacyBatch.quantity_remaining > 0,
                PharmacyBatch.is_deleted == False,  # noqa: E712
            )
            .order_by(
                PharmacyBatch.expiry_date.is_(None),
                PharmacyBatch.expiry_date.asc(),
                PharmacyBatch.received_at.asc(),
            )
            .limit(1)
        )
        earliest = result.scalar_one_or_none()
        pharmacy_item.batch_number = earliest.batch_number if earliest else None
        pharmacy_item.expiry_date = earliest.expiry_date if earliest else None

    @staticmethod
    def _check_drug_identity(
        rx: Prescription,
        pharmacy_item: PharmacyItem,
        data: DispenseRequest,
    ) -> None:
        """
        Ensure the stock item being deducted is the prescribed drug, or an
        explicitly documented substitution.

        @param rx: The prescription being dispensed
        @param pharmacy_item: The pharmacy stock item selected
        @param data: Dispense request (substitution fields)
        @raises ValueError: If the item does not match and no substitution
            with a reason is documented
        """
        if data.substitution_drug:
            if not data.substitution_reason:
                raise ValueError("Substitution requires a documented reason")
            return

        def _norm(value: str | None) -> str:
            return (value or "").strip().lower()

        # Prefer formulary code match when both sides carry a code.
        if rx.drug_code and pharmacy_item.drug_code:
            if _norm(rx.drug_code) == _norm(pharmacy_item.drug_code):
                return
        else:
            names = {_norm(pharmacy_item.drug_name), _norm(pharmacy_item.generic_name)}
            names.discard("")
            if _norm(rx.drug_name) in names or _norm(rx.generic_name) in names:
                return

        raise ValueError(
            f"Selected stock item '{pharmacy_item.drug_name}' does not match "
            f"prescribed drug '{rx.drug_name}'. Use substitution fields to "
            "dispense a different product."
        )

    # ── Inventory Management ──────────────────────────────────────────────

    async def create_item(
        self,
        data: PharmacyItemCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> PharmacyItem:
        """
        Add a new item to pharmacy inventory.

        @param data: Pharmacy item data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created pharmacy item
        """
        item = PharmacyItem(
            facility_id=facility_id,
            created_by=created_by,
            updated_by=created_by,
            **data.model_dump(),
        )

        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)

        # Initial stock receipt transaction + opening batch (FEFO source)
        if data.current_quantity > 0:
            self.db.add(
                PharmacyBatch(
                    facility_id=facility_id,
                    pharmacy_item_id=item.id,
                    batch_number=data.batch_number,
                    expiry_date=data.expiry_date,
                    quantity_received=data.current_quantity,
                    quantity_remaining=data.current_quantity,
                    unit_cost_cents=data.buying_price_cents,
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
            stock_tx = StockTransaction(
                facility_id=facility_id,
                pharmacy_item_id=item.id,
                transaction_type="receipt",
                quantity_change=data.current_quantity,
                quantity_before=0,
                quantity_after=data.current_quantity,
                batch_number=data.batch_number,
                expiry_date=data.expiry_date,
                unit_cost_cents=data.buying_price_cents,
                reason="Initial stock entry",
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(stock_tx)

        return item

    async def update_item(
        self,
        item_id: uuid.UUID,
        data: PharmacyItemUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> PharmacyItem | None:
        """
        Update a pharmacy inventory item.

        @param item_id: PharmacyItem UUID
        @param data: Fields to update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated item or None
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        item.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_inventory(
        self,
        facility_id: uuid.UUID,
        query: str | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PharmacyItem], int]:
        """
        List pharmacy inventory with search and pagination.

        @param facility_id: Facility UUID
        @param query: Optional search by drug name or code
        @param active_only: Only show active items
        @param page: Page number
        @param page_size: Items per page
        @returns Tuple of (items, total count)
        """
        stmt = select(PharmacyItem).where(
            PharmacyItem.facility_id == facility_id,
            PharmacyItem.is_deleted == False,  # noqa: E712
        )

        if active_only:
            stmt = stmt.where(PharmacyItem.is_active == True)  # noqa: E712

        if query:
            search = f"%{query}%"
            stmt = stmt.where(
                PharmacyItem.drug_name.ilike(search)
                | PharmacyItem.drug_code.ilike(search)
                | PharmacyItem.generic_name.ilike(search)
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginate
        stmt = (
            stmt.order_by(PharmacyItem.drug_name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def receive_stock(
        self,
        data: StockReceiptRequest,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> StockTransaction:
        """
        Receive new stock into inventory.

        @param data: Stock receipt data
        @param facility_id: Facility UUID
        @param received_by: Staff UUID
        @returns Stock transaction record
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == data.pharmacy_item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found")

        qty_before = item.current_quantity
        item.current_quantity += data.quantity
        qty_after = item.current_quantity

        # Every receipt is its own batch (FEFO consumption at dispense).
        batch = PharmacyBatch(
            facility_id=facility_id,
            pharmacy_item_id=item.id,
            batch_number=data.batch_number,
            expiry_date=data.expiry_date,
            quantity_received=data.quantity,
            quantity_remaining=data.quantity,
            unit_cost_cents=data.unit_cost_cents,
            reference_number=data.reference_number,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(batch)
        await self._refresh_item_batch_summary(item)

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=data.pharmacy_item_id,
            transaction_type="receipt",
            quantity_change=data.quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reference_number=data.reference_number,
            reason=data.reason,
            unit_cost_cents=data.unit_cost_cents,
            batch_number=data.batch_number,
            expiry_date=data.expiry_date,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    async def adjust_stock(
        self,
        data: StockAdjustmentRequest,
        facility_id: uuid.UUID,
        adjusted_by: uuid.UUID,
    ) -> StockTransaction:
        """
        Adjust stock quantity (loss, damage, correction, transfer).

        @param data: Adjustment data
        @param facility_id: Facility UUID
        @param adjusted_by: Staff UUID
        @returns Stock transaction record
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == data.pharmacy_item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found")

        qty_before = item.current_quantity
        new_qty = qty_before + data.quantity_change
        if new_qty < 0:
            raise ValueError(
                f"Adjustment would result in negative stock ({new_qty})"
            )

        if data.quantity_change < 0:
            # Write-offs/corrections consume batches like dispensing.
            # Expired batches are drawn down FIRST here (expired stock is
            # the usual reason for a negative adjustment).
            await self._consume_batches_for_adjustment(
                item, -data.quantity_change, adjusted_by
            )
        elif data.quantity_change > 0:
            self.db.add(
                PharmacyBatch(
                    facility_id=facility_id,
                    pharmacy_item_id=item.id,
                    batch_number=data.reference_number,
                    expiry_date=None,
                    quantity_received=data.quantity_change,
                    quantity_remaining=data.quantity_change,
                    created_by=adjusted_by,
                    updated_by=adjusted_by,
                )
            )

        item.current_quantity = new_qty
        await self._refresh_item_batch_summary(item)

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=data.pharmacy_item_id,
            transaction_type="adjustment",
            quantity_change=data.quantity_change,
            quantity_before=qty_before,
            quantity_after=new_qty,
            reference_number=data.reference_number,
            reason=data.reason,
            created_by=adjusted_by,
            updated_by=adjusted_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    async def get_stock_alerts(
        self, facility_id: uuid.UUID
    ) -> list[StockAlert]:
        """
        Get stock alerts: low stock, expiring soon (30 days), expired, out of stock.

        @param facility_id: Facility UUID
        @returns List of stock alerts
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_active == True,  # noqa: E712
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        items = list(result.scalars().all())
        today = date.today()
        thirty_days = today + timedelta(days=30)

        alerts: list[StockAlert] = []
        for item in items:
            if item.current_quantity == 0:
                alerts.append(StockAlert(
                    item_id=item.id,
                    drug_name=item.drug_name,
                    drug_code=item.drug_code,
                    current_quantity=item.current_quantity,
                    reorder_level=item.reorder_level,
                    expiry_date=item.expiry_date,
                    alert_type="out_of_stock",
                ))
            elif item.current_quantity <= item.reorder_level:
                alerts.append(StockAlert(
                    item_id=item.id,
                    drug_name=item.drug_name,
                    drug_code=item.drug_code,
                    current_quantity=item.current_quantity,
                    reorder_level=item.reorder_level,
                    expiry_date=item.expiry_date,
                    alert_type="low_stock",
                ))

            if item.expiry_date:
                if item.expiry_date < today:
                    alerts.append(StockAlert(
                        item_id=item.id,
                        drug_name=item.drug_name,
                        drug_code=item.drug_code,
                        current_quantity=item.current_quantity,
                        reorder_level=item.reorder_level,
                        expiry_date=item.expiry_date,
                        alert_type="expired",
                    ))
                elif item.expiry_date <= thirty_days:
                    alerts.append(StockAlert(
                        item_id=item.id,
                        drug_name=item.drug_name,
                        drug_code=item.drug_code,
                        current_quantity=item.current_quantity,
                        reorder_level=item.reorder_level,
                        expiry_date=item.expiry_date,
                        alert_type="expiring_soon",
                    ))

        return alerts
