import logging
import uuid
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.schemas.encounter import EncounterCreate, EncounterUpdate
from app.services.consultation_fee import load_consultation_fee_cents

_logger = logging.getLogger(__name__)


class EncounterService:
    """Service layer for OPD encounter and queue management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_encounter(
        self,
        data: EncounterCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Encounter:
        """
        Create a new encounter and add to OPD queue.

        @param data: Encounter creation data
        @param facility_id: Facility UUID from JWT
        @param created_by: Staff UUID
        @param idempotency_key: Optional idempotency key
        @returns Created encounter
        """
        # Generate queue number for today
        queue_number = await self._next_queue_number(facility_id)

        encounter = Encounter(
            facility_id=facility_id,
            patient_id=data.patient_id,
            encounter_type=data.encounter_type,
            department_id=data.department_id,
            attending_doctor_id=getattr(data, "attending_doctor_id", None),
            chief_complaint=data.chief_complaint,
            triage_category=data.triage_category,
            priority=self._triage_priority(data.triage_category),
            queue_number=queue_number,
            status="waiting",
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(encounter)
        await self.db.flush()
        await self.db.refresh(encounter)


        # Fee quoted at the desk for this department / doctor combination.
        # Resolved once so the invoice and the GL entry always agree.
        fee_cents = await self._get_consultation_fee_cents(
            facility_id,
            department_id=encounter.department_id,
            doctor_id=encounter.attending_doctor_id,
        )

        # GL auto-post: DR 1100 AR / CR 4000 Consultation Revenue
        await self._post_encounter_to_gl(
            encounter=encounter,
            facility_id=facility_id,
            user_id=created_by,
            fee_cents=fee_cents,
        )


        # Auto-create consultation invoice
        await self._create_consultation_invoice(
            encounter=encounter,
            facility_id=facility_id,
            created_by=created_by,
            fee_cents=fee_cents,
        )

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="encounter",
            stream_id=encounter.id,
            event_type="EncounterCreated",
            event_data={
                "patient_id": str(data.patient_id),
                "encounter_type": data.encounter_type,
                "chief_complaint": data.chief_complaint,
                "triage_category": data.triage_category,
                "queue_number": queue_number,
            },
            version=1,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return encounter

    async def _post_encounter_to_gl(
        self, encounter, facility_id, user_id, fee_cents: int
    ):
        from decimal import Decimal
        if fee_cents <= 0:
            return
        amount = Decimal(str(fee_cents)) / 100
        try:
            from app.services.finance import post_compound_transaction
        except ImportError:
            _logger.warning('encounter.gl.unavailable encounter_id=%s', encounter.id)
            return
        entries = [
            {'account_code': '1100', 'debit': amount, 'credit': Decimal('0')},
            {'account_code': '4000', 'debit': Decimal('0'), 'credit': amount},
        ]
        enc_date = encounter.encounter_date
        date_str = enc_date.date().isoformat() if hasattr(enc_date, 'date') else str(enc_date)
        metadata = {
            'date': date_str,
            'event_type': 'encounter_created',
            'reference_type': 'encounter',
            'reference_id': str(encounter.id),
            'description': f'OPD Encounter #{encounter.queue_number}',
        }
        try:
            txn = await post_compound_transaction(
                db=self.db, facility_id=facility_id, entries=entries,
                metadata=metadata,
                idempotency_key=f'encounter_created:{encounter.id}',
                user_id=user_id,
            )
            _logger.info('encounter.gl.posted encounter=%s txn=%s', encounter.id, getattr(txn, 'id', None))
        except Exception as exc:
            _logger.warning('encounter.gl.post_failed encounter=%s error=%s', encounter.id, exc)


    async def get_opd_queue(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
    ) -> list[Encounter]:
        """
        Get the OPD queue ordered by triage priority then queue number.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @returns List of encounters in queue order
        """
        from sqlalchemy.orm import selectinload
        stmt = (
            select(Encounter)
            .options(selectinload(Encounter.patient))
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
        )

        if status_filter:
            stmt = stmt.where(Encounter.status == status_filter)
        else:
            stmt = stmt.where(
                Encounter.status.in_(["waiting", "in_consultation"])
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_encounter(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Encounter | None:
        """
        Get a single encounter by ID.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Encounter or None
        """
        result = await self.db.execute(
            select(Encounter).where(
                Encounter.id == encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
        )
        encounter = result.scalar_one_or_none()
        if encounter:
            from app.models.patient import Patient
            p_result = await self.db.execute(
                select(Patient).where(Patient.id == encounter.patient_id)
            )
            patient = p_result.scalar_one_or_none()
            if patient:
                encounter.patient_name = f"{patient.first_name} {patient.last_name}".strip()  # type: ignore[attr-defined]
                encounter.patient_mrn = patient.mrn  # type: ignore[attr-defined]
        return encounter

    async def update_encounter(
        self,
        encounter_id: uuid.UUID,
        data: EncounterUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Encounter | None:
        """
        Update encounter (status, triage, disposition, etc.).

        @param encounter_id: Encounter UUID
        @param data: Fields to update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated encounter or None
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if not encounter:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(encounter, field, value)

        if data.triage_category:
            encounter.priority = self._triage_priority(data.triage_category)

        encounter.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(encounter)

        return encounter

    async def call_next(
        self, facility_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> Encounter | None:
        """
        Call the next patient in the OPD queue (highest priority waiting).

        @param facility_id: Facility UUID
        @param doctor_id: Doctor's staff UUID
        @returns Next encounter or None if queue empty
        """
        result = await self.db.execute(
            select(Encounter)
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                Encounter.status == "waiting",
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
            .limit(1)
        )
        encounter = result.scalar_one_or_none()
        if not encounter:
            return None

        await self.assert_consultation_paid(encounter)

        encounter.status = "in_consultation"
        encounter.attending_doctor_id = doctor_id
        encounter.updated_by = doctor_id
        await self.db.flush()
        await self.db.refresh(encounter)

        return encounter

    async def _get_consultation_fee_cents(
        self, facility_id, department_id=None, doctor_id=None
    ) -> int:
        """
        Resolve the consultation fee for a department / doctor combination.

        @param facility_id: Facility UUID
        @param department_id: Target department UUID (optional override)
        @param doctor_id: Target doctor's staff UUID (optional override)
        @returns Fee in KES cents
        """
        return await load_consultation_fee_cents(
            self.db,
            facility_id,
            department_id=department_id,
            doctor_id=doctor_id,
        )

    async def _consultation_invoice(self, encounter_id):
        """
        Fetch the invoice carrying an encounter's consultation fee.

        @param encounter_id: Encounter UUID
        @returns Invoice, or None when the encounter was never consultation-billed
        """
        from app.models.billing import Invoice, InvoiceItem

        result = await self.db.execute(
            select(Invoice)
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .where(
                Invoice.encounter_id == encounter_id,
                InvoiceItem.item_type == "consultation",
                Invoice.is_deleted == False,  # noqa: E712
            )
            .order_by(Invoice.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def assert_consultation_paid(self, encounter) -> None:
        """
        Block a consultation that has not been settled at reception.

        Encounters without a consultation invoice (facility fee configured as
        0, or encounters billed before this feature existed) pass through, so
        the gate can never strand a patient with no way to proceed.

        @param encounter: Encounter about to be seen
        @raises ValueError: When the consultation fee is still outstanding
        """
        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None or invoice.balance_cents <= 0:
            return
        balance = invoice.balance_cents / 100
        raise ValueError(
            "Consultation fee not settled at reception: invoice "
            f"{invoice.invoice_number} has a balance of {balance:,.2f} KES."
        )

    async def get_consultation_fee_quote(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> dict | None:
        """
        Quote the consultation fee for an encounter plus its payment state.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Quote dict, or None when the encounter does not exist
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            return None

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            fee = await self._get_consultation_fee_cents(
                facility_id,
                department_id=encounter.department_id,
                doctor_id=encounter.attending_doctor_id,
            )
            return {
                "encounter": encounter,
                "fee_cents": fee,
                "invoice": None,
                "paid": fee == 0,
            }

        return {
            "encounter": encounter,
            "fee_cents": invoice.total_cents,
            "invoice": invoice,
            "paid": invoice.balance_cents <= 0,
        }

    async def collect_consultation_payment(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
        payment_method: str,
        reference_number: str | None = None,
        mpesa_transaction_id: str | None = None,
        notes: str | None = None,
        amount_cents: int | None = None,
        idempotency_key: str | None = None,
    ):
        """
        Record the reception payment for an encounter's consultation fee.

        An invoice that is already settled is returned untouched, so a double
        click at the desk cannot take the patient's money twice.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param received_by: Staff UUID of the receptionist taking payment
        @param payment_method: cash, mpesa, insurance or exemption
        @param reference_number: Optional receipt / M-Pesa reference
        @param mpesa_transaction_id: Optional M-Pesa transaction id
        @param notes: Optional free-text note
        @param amount_cents: Amount to collect (defaults to the full balance)
        @param idempotency_key: Optional client key for safe retries
        @raises ValueError: When the encounter or its invoice is missing
        @returns Tuple of (invoice, payment) - payment is None when settled
        """
        from app.schemas.billing import PaymentCreate
        from app.services.billing_service import BillingService

        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            raise ValueError("Encounter not found")

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            raise ValueError("This encounter has no consultation invoice to pay")

        if invoice.balance_cents <= 0:
            return invoice, None

        payable = amount_cents if amount_cents is not None else invoice.balance_cents
        payment = await BillingService(self.db).record_payment(
            invoice_id=invoice.id,
            data=PaymentCreate(
                amount_cents=payable,
                payment_method=payment_method,
                reference_number=reference_number,
                mpesa_transaction_id=mpesa_transaction_id,
                notes=notes,
            ),
            facility_id=facility_id,
            received_by=received_by,
            idempotency_key=idempotency_key,
        )
        return invoice, payment

    async def set_consultation_fee(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        amount_cents: int,
        updated_by: uuid.UUID,
    ) -> dict | None:
        """
        Set the consultation fee charged for an encounter.

        The front desk corrects the quoted fee here: a negotiated amount, a
        follow-up rate, a doctor who charges differently. The visit's
        consultation invoice is re-priced, so the money taken, the patient's
        bill and the printed receipt all show the same amount.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param amount_cents: New fee in KES cents (must be positive)
        @param updated_by: Staff UUID making the change
        @raises ValueError: When the amount is not positive, or is below what
            the patient has already paid
        @returns Fresh fee quote, or None when the encounter does not exist
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            return None

        if amount_cents <= 0:
            raise ValueError("Enter a consultation fee greater than zero")

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            await self._create_consultation_invoice(
                encounter, facility_id, updated_by, amount_cents
            )
            invoice = await self._consultation_invoice(encounter.id)
            if invoice is None:
                raise ValueError("Could not raise a consultation invoice")
        else:
            paid_cents = invoice.paid_cents or 0
            if amount_cents < paid_cents:
                raise ValueError(
                    "The fee cannot be less than the "
                    f"{paid_cents / 100:,.2f} KES already collected"
                )
            await self._reprice_consultation_invoice(
                invoice, amount_cents, updated_by
            )
            # A correction that leaves money owing reopens the bill.
            if invoice.balance_cents > 0 and encounter.billing_status == "paid":
                encounter.billing_status = "billed"

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="billing",
                stream_id=encounter.patient_id,
                event_type="ConsultationFeeSet",
                event_data={
                    "encounter_id": str(encounter.id),
                    "invoice_number": invoice.invoice_number,
                    "fee_cents": amount_cents,
                },
                version=1,
                created_by=updated_by,
            )
        )
        await self.db.flush()
        return await self.get_consultation_fee_quote(encounter_id, facility_id)

    async def _reprice_consultation_invoice(
        self, invoice, fee_cents: int, updated_by: uuid.UUID
    ) -> None:
        """
        Re-price the consultation line on a visit's invoice.

        Any other line the visit accrued keeps its own price, and the invoice
        totals are recomputed exactly the way a payment recomputes them.

        @param invoice: The encounter's consultation invoice
        @param fee_cents: New fee in KES cents
        @param updated_by: Staff UUID making the change
        """
        from app.models.billing import InvoiceItem

        result = await self.db.execute(
            select(InvoiceItem).where(
                InvoiceItem.invoice_id == invoice.id,
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
        )
        items = list(result.scalars().all())
        for item in items:
            if item.item_type != "consultation":
                continue
            item.unit_price_cents = fee_cents
            item.total_cents = fee_cents * max(item.quantity, 1)
            item.updated_by = updated_by

        subtotal = sum(item.total_cents for item in items)
        invoice.subtotal_cents = subtotal
        invoice.total_cents = (
            subtotal - (invoice.discount_cents or 0) + (invoice.tax_cents or 0)
        )
        invoice.balance_cents = max(invoice.total_cents - invoice.paid_cents, 0)
        if invoice.balance_cents <= 0:
            if invoice.paid_cents > 0:
                invoice.status = "paid"
        elif invoice.paid_cents > 0:
            invoice.status = "partially_paid"
        invoice.updated_by = updated_by

    async def _create_consultation_invoice(
        self, encounter, facility_id, created_by, fee_cents: int
    ):
        """
        Auto-create a draft invoice for the fee quoted at the front desk.
        Failures never block the clinical flow.

        @param encounter: The encounter being billed
        @param facility_id: Facility UUID
        @param created_by: Staff UUID starting the consultation
        @param fee_cents: Fee resolved for this department / doctor
        """
        try:
            from app.models.billing import Invoice, InvoiceItem

            fee = fee_cents
            if fee == 0:
                return
            inv_num = await self._next_invoice_number(facility_id)
            inv = Invoice(
                facility_id=facility_id,
                encounter_id=encounter.id,
                patient_id=encounter.patient_id,
                invoice_number=inv_num,
                status="draft",
                subtotal_cents=fee,
                total_cents=fee,
                balance_cents=fee,
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(inv)
            await self.db.flush()
            await self.db.refresh(inv)
            item = InvoiceItem(
                facility_id=facility_id,
                invoice_id=inv.id,
                item_type="consultation",
                description=f"OPD Consultation Fee - {encounter.chief_complaint or 'General'}",
                quantity=1,
                unit_price_cents=fee,
                total_cents=fee,
                discount_cents=0,
                reference_id=encounter.id,
                reference_type="encounter",
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(item)
            await self.db.flush()
            encounter.billing_status = "billed"
            _logger.info("encounter.invoice.created %s", inv.invoice_number)
        except Exception as exc:
            _logger.warning("encounter.invoice.failed %s %s", encounter.id, exc)

    async def _next_invoice_number(self, facility_id):
        from datetime import datetime

        from sqlalchemy import func as sqlfunc
        from sqlalchemy import select

        from app.models.billing import Invoice

        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f'INV-{today}-'
        result = await self.db.execute(
            select(sqlfunc.count()).select_from(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.invoice_number.like(f'{prefix}%'),
            )
        )
        count = result.scalar_one()
        return f'{prefix}{count + 1:04d}'


    async def _next_queue_number(self, facility_id: uuid.UUID) -> int:
        """Generate the next queue number for today."""
        result = await self.db.execute(
            select(func.coalesce(func.max(Encounter.queue_number), 0))
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) == func.current_date(),
            )
        )
        return (result.scalar_one() or 0) + 1

    @staticmethod
    def _triage_priority(category: str | None) -> int:
        """Map SATS triage category to numeric priority."""
        mapping = {
            "emergency": 5,   # Red
            "urgent": 4,      # Orange
            "standard": 3,    # Yellow
            "non_urgent": 2,  # Green
            "dead": 1,        # Blue
        }
        return mapping.get(category or "", 2)
