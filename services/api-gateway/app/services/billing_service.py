import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.schemas.billing import (
    BillingSummary,
    InvoiceCreate,
    InvoiceListItem,
    PaymentCreate,
)

_logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


class BillingService:
    """
    Service for hospital billing: invoice creation, line items,
    payments (Cash/M-Pesa/Insurance/Exemption), and dashboard summaries.
    Money in KES cents per CLAUDE.md.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _find_by_idempotency_key(
        self,
        idempotency_key: str,
        facility_id: uuid.UUID,
        event_type: str,
        id_field: str,
    ) -> uuid.UUID | None:
        """
        Look up a previously processed request via the event store's unique
        idempotency_key so retried POSTs return the original record.

        @param idempotency_key: Client-supplied X-Idempotency-Key value
        @param facility_id: Facility UUID
        @param event_type: Event type recorded on first processing
        @param id_field: event_data field holding the created record's ID
        @returns UUID of the originally created record, or None
        """
        result = await self.db.execute(
            select(EventBase).where(
                EventBase.idempotency_key == idempotency_key,
                EventBase.facility_id == facility_id,
                EventBase.event_type == event_type,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            return None
        record_id = (event.event_data or {}).get(id_field)
        return uuid.UUID(record_id) if record_id else None

    # â”€â”€ Invoice Creation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def create_invoice(
        self,
        data: InvoiceCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Invoice:
        """
        Create an invoice with line items. Computes subtotal and total.
        Idempotent per X-Idempotency-Key.

        @param data: Invoice data with items
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @param idempotency_key: Optional client key for safe retries
        @returns Created invoice
        """
        if idempotency_key:
            existing_id = await self._find_by_idempotency_key(
                idempotency_key, facility_id, "InvoiceCreated", "invoice_id"
            )
            if existing_id is not None:
                existing = await self.db.execute(
                    select(Invoice).where(Invoice.id == existing_id)
                )
                invoice = existing.scalar_one_or_none()
                if invoice is not None:
                    return invoice

        invoice_number = await self._next_invoice_number(facility_id)

        # Compute line item totals
        subtotal = 0
        total_discount = 0
        items_to_add: list[InvoiceItem] = []
        for item_data in data.items:
            line_total = item_data.quantity * item_data.unit_price_cents
            items_to_add.append(
                InvoiceItem(
                    facility_id=facility_id,
                    item_type=item_data.item_type,
                    description=item_data.description,
                    quantity=item_data.quantity,
                    unit_price_cents=item_data.unit_price_cents,
                    total_cents=line_total,
                    discount_cents=item_data.discount_cents,
                    reference_id=item_data.reference_id,
                    reference_type=item_data.reference_type,
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
            subtotal += line_total
            total_discount += item_data.discount_cents

        total = subtotal - total_discount

        invoice = Invoice(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            invoice_number=invoice_number,
            status="draft",
            payment_method=data.payment_method,
            insurance_provider=data.insurance_provider,
            insurance_member_no=data.insurance_member_no,
            subtotal_cents=subtotal,
            discount_cents=total_discount,
            tax_cents=0,
            total_cents=total,
            paid_cents=0,
            balance_cents=total,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(invoice)
        await self.db.flush()
        await self.db.refresh(invoice)

        # Attach items to invoice
        for item in items_to_add:
            item.invoice_id = invoice.id
            self.db.add(item)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=data.patient_id,
            event_type="InvoiceCreated",
            event_data={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice_number,
                "total_cents": total,
                "item_count": len(data.items),
            },
            version=1,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return invoice

    # â”€â”€ Invoice Detail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_invoice_detail(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID
    ) -> tuple[Invoice | None, list[InvoiceItem], str | None, str | None]:
        """
        Get invoice with all line items and patient info.

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @returns Tuple of (invoice, items, patient_name, patient_mrn)
        """
        result = await self.db.execute(
            select(Invoice, Patient)
            .join(Patient, Invoice.patient_id == Patient.id)
            .where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        row = result.first()
        if not row:
            return None, [], None, None

        invoice, patient = row

        items_result = await self.db.execute(
            select(InvoiceItem)
            .where(
                InvoiceItem.invoice_id == invoice_id,
                InvoiceItem.facility_id == facility_id,
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
            .order_by(InvoiceItem.created_at.asc())
        )
        items = list(items_result.scalars().all())

        patient_name = f"{patient.first_name} {patient.last_name}"
        return invoice, items, patient_name, patient.mrn

    async def get_invoice_payments(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[Payment]:
        """
        List non-deleted payments for an invoice, oldest first.

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @returns Payments ordered by paid_at
        """
        result = await self.db.execute(
            select(Payment)
            .where(
                Payment.invoice_id == invoice_id,
                Payment.facility_id == facility_id,
                Payment.is_deleted == False,  # noqa: E712
            )
            .order_by(Payment.paid_at.asc())
        )
        return list(result.scalars().all())

    # â”€â”€ Invoice List â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_invoices(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        patient_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[InvoiceListItem], int]:
        """
        List invoices with patient info, item counts, and pagination.
        Uses a LEFT JOIN subquery for item counts to avoid N+1 queries.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @param patient_id: Optional patient filter
        @param page: Page number
        @param page_size: Items per page
        @returns Tuple of (invoice list items, total count)
        """
        # Subquery: item counts per invoice
        item_counts_sq = (
            select(
                InvoiceItem.invoice_id,
                func.count(InvoiceItem.id).label("item_count"),
            )
            .where(InvoiceItem.is_deleted == False)  # noqa: E712
            .group_by(InvoiceItem.invoice_id)
            .subquery()
        )

        base = (
            select(Invoice, Patient)
            .join(Patient, Invoice.patient_id == Patient.id)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter:
            base = base.where(Invoice.status == status_filter)
        if patient_id:
            base = base.where(Invoice.patient_id == patient_id)

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginate with item count LEFT JOIN
        stmt = (
            select(
                Invoice,
                Patient,
                func.coalesce(item_counts_sq.c.item_count, 0).label("item_count"),
            )
            .join(Patient, Invoice.patient_id == Patient.id)
            .outerjoin(item_counts_sq, Invoice.id == item_counts_sq.c.invoice_id)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter:
            stmt = stmt.where(Invoice.status == status_filter)
        if patient_id:
            stmt = stmt.where(Invoice.patient_id == patient_id)

        stmt = stmt.order_by(Invoice.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[InvoiceListItem] = []
        for invoice, patient, item_count in rows:
            items.append(
                InvoiceListItem(
                    id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    encounter_id=invoice.encounter_id,
                    patient_id=invoice.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    status=invoice.status,
                    total_cents=invoice.total_cents,
                    paid_cents=invoice.paid_cents,
                    balance_cents=invoice.balance_cents,
                    payment_method=invoice.payment_method,
                    item_count=item_count,
                    created_at=invoice.created_at,
                )
            )

        return items, total

    # â”€â”€ Finalize Invoice â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def finalize_invoice(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID, finalized_by: uuid.UUID
    ) -> Invoice | None:
        """
        Finalize a draft invoice (locks it for payment).

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @param finalized_by: Staff UUID
        @returns Finalized invoice or None
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        if invoice.status != "draft":
            raise ValueError(f"Cannot finalize invoice with status: {invoice.status}")

        invoice.status = "finalized"
        invoice.finalized_at = datetime.now(UTC)
        invoice.finalized_by = finalized_by
        invoice.updated_by = finalized_by

        # Update encounter billing status
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == invoice.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.billing_status = "billed"

        await self.db.flush()
        await self.db.refresh(invoice)

        await self._post_invoice_gl(invoice=invoice, facility_id=facility_id, user_id=finalized_by)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="InvoiceFinalized",
            event_data={
                "invoice_number": invoice.invoice_number,
                "total_cents": invoice.total_cents,
            },
            version=1,
            created_by=finalized_by,
        )
        self.db.add(event)

        return invoice

    # â”€â”€ Record Payment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def record_payment(
        self,
        invoice_id: uuid.UUID,
        data: PaymentCreate,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Payment:
        """
        Record a payment against an invoice. Updates balances and status.
        Supports partial payments. Idempotent per X-Idempotency-Key.

        @param invoice_id: Invoice UUID
        @param data: Payment data
        @param facility_id: Facility UUID
        @param received_by: Staff UUID who received payment
        @param idempotency_key: Optional client key for safe retries
        @returns Created payment
        """
        if idempotency_key:
            existing_id = await self._find_by_idempotency_key(
                idempotency_key, facility_id, "PaymentReceived", "payment_id"
            )
            if existing_id is not None:
                existing = await self.db.execute(
                    select(Payment).where(Payment.id == existing_id)
                )
                payment = existing.scalar_one_or_none()
                if payment is not None:
                    return payment

        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice not found")
        if invoice.status in ("cancelled", "waived"):
            raise ValueError(f"Cannot pay invoice with status: {invoice.status}")
        if data.amount_cents > invoice.balance_cents:
            raise ValueError(
                f"Payment amount ({data.amount_cents}) exceeds balance ({invoice.balance_cents})"
            )

        payment = Payment(
            facility_id=facility_id,
            invoice_id=invoice_id,
            patient_id=invoice.patient_id,
            amount_cents=data.amount_cents,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            mpesa_transaction_id=data.mpesa_transaction_id,
            received_by=received_by,
            notes=data.notes,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(payment)

        # Update invoice
        invoice.paid_cents += data.amount_cents
        invoice.balance_cents = invoice.total_cents - invoice.paid_cents
        if invoice.balance_cents <= 0:
            invoice.status = "paid"
            invoice.balance_cents = 0
        elif invoice.paid_cents > 0:
            invoice.status = "partially_paid"
        invoice.updated_by = received_by

        # Update encounter billing status if fully paid
        if invoice.status == "paid":
            enc_result = await self.db.execute(
                select(Encounter).where(Encounter.id == invoice.encounter_id)
            )
            encounter = enc_result.scalar_one_or_none()
            if encounter:
                encounter.billing_status = "paid"

        await self.db.flush()
        await self.db.refresh(payment)

        await self._post_payment_gl(payment=payment, invoice=invoice, facility_id=facility_id, user_id=received_by)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="PaymentReceived",
            event_data={
                "payment_id": str(payment.id),
                "invoice_number": invoice.invoice_number,
                "amount_cents": data.amount_cents,
                "payment_method": data.payment_method,
                "new_balance_cents": invoice.balance_cents,
                "invoice_status": invoice.status,
            },
            version=1,
            created_by=received_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return payment

    async def record_external_payment(
        self,
        invoice_id: uuid.UUID,
        amount_cents: int,
        mpesa_receipt: str | None,
        phone_number: str | None = None,
        received_by: uuid.UUID | None = None,
    ) -> Payment | None:
        """
        Record a machine-confirmed payment (M-Pesa STK/C2B callback) against
        an invoice. Unlike record_payment this never rejects the money: an
        overpayment is still recorded (balance clamps to 0) because the funds
        have already been received. Idempotent per M-Pesa receipt.

        @param invoice_id: Invoice UUID
        @param amount_cents: Amount received in KES cents
        @param mpesa_receipt: M-Pesa receipt number (idempotency key)
        @param phone_number: Payer MSISDN, stored in payment notes only
        @param received_by: Staff UUID that initiated the STK push, if any
        @returns Created payment, or None if this receipt was already recorded
        """
        if mpesa_receipt:
            existing = await self.db.execute(
                select(Payment).where(
                    Payment.mpesa_transaction_id == mpesa_receipt,
                    Payment.is_deleted == False,  # noqa: E712
                )
            )
            if existing.scalar_one_or_none() is not None:
                _logger.info(
                    "mpesa payment already recorded receipt=%s", mpesa_receipt
                )
                return None

        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.id == invoice_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise ValueError("Invoice not found")

        payment = Payment(
            facility_id=invoice.facility_id,
            invoice_id=invoice.id,
            patient_id=invoice.patient_id,
            amount_cents=amount_cents,
            payment_method="mpesa",
            reference_number=mpesa_receipt,
            mpesa_transaction_id=mpesa_receipt,
            received_by=received_by,
            notes=f"M-Pesa payment from {phone_number}" if phone_number else "M-Pesa payment",
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(payment)

        invoice.paid_cents += amount_cents
        invoice.balance_cents = invoice.total_cents - invoice.paid_cents
        if invoice.balance_cents <= 0:
            invoice.status = "paid"
            invoice.balance_cents = 0
        elif invoice.paid_cents > 0:
            invoice.status = "partially_paid"

        if invoice.status == "paid":
            enc_result = await self.db.execute(
                select(Encounter).where(Encounter.id == invoice.encounter_id)
            )
            encounter = enc_result.scalar_one_or_none()
            if encounter:
                encounter.billing_status = "paid"

        await self.db.flush()
        await self.db.refresh(payment)

        await self._post_payment_gl(
            payment=payment,
            invoice=invoice,
            facility_id=invoice.facility_id,
            user_id=received_by,
        )

        event = EventBase(
            facility_id=invoice.facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="PaymentReceived",
            event_data={
                "invoice_number": invoice.invoice_number,
                "amount_cents": amount_cents,
                "payment_method": "mpesa",
                "mpesa_receipt": mpesa_receipt,
                "new_balance_cents": invoice.balance_cents,
                "invoice_status": invoice.status,
            },
            version=1,
            created_by=received_by,
        )
        self.db.add(event)

        return payment

    # â”€â”€ Waive Invoice â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def waive_invoice(
        self,
        invoice_id: uuid.UUID,
        facility_id: uuid.UUID,
        waived_by: uuid.UUID,
        reason: str,
    ) -> Invoice | None:
        """
        Waive remaining balance on an invoice (exemption/charity).

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @param waived_by: Staff UUID
        @param reason: Reason for waiver
        @returns Updated invoice or None
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None

        invoice.status = "waived"
        invoice.notes = (invoice.notes or "") + f"\nWaiver: {reason}"
        invoice.balance_cents = 0
        invoice.updated_by = waived_by

        # Update encounter
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == invoice.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.billing_status = "waived"

        await self.db.flush()
        await self.db.refresh(invoice)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="InvoiceWaived",
            event_data={
                "invoice_number": invoice.invoice_number,
                "reason": reason,
                "waived_amount_cents": invoice.total_cents - invoice.paid_cents,
            },
            version=1,
            created_by=waived_by,
        )
        self.db.add(event)

        return invoice

    # â”€â”€ Dashboard Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def get_summary(self, facility_id: uuid.UUID) -> BillingSummary:
        """
        Get billing dashboard summary stats.

        @param facility_id: Facility UUID
        @returns Billing summary
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoices = list(result.scalars().all())

        return BillingSummary(
            total_invoices=len(invoices),
            draft_count=sum(1 for i in invoices if i.status == "draft"),
            finalized_count=sum(1 for i in invoices if i.status == "finalized"),
            paid_count=sum(1 for i in invoices if i.status == "paid"),
            partially_paid_count=sum(
                1 for i in invoices if i.status == "partially_paid"
            ),
            total_billed_cents=sum(i.total_cents for i in invoices),
            total_paid_cents=sum(i.paid_cents for i in invoices),
            # Canonical outstanding AR = balance on finalized + partially-paid
            # invoices only. Drafts are NOT receivables (the ledger debits AR on
            # finalize, not on draft), so counting them here is what made Billing
            # disagree with the Reports dashboard and the GL AR balance (QA F8).
            total_outstanding_cents=sum(
                i.balance_cents
                for i in invoices
                if i.status in ("finalized", "partially_paid")
            ),
        )

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _post_invoice_gl(self, invoice, facility_id, user_id):
        from decimal import Decimal
        if invoice.total_cents <= 0:
            return
        try:
            from app.services.finance import post_compound_transaction
        except ImportError:
            return
        amount = Decimal(str(invoice.total_cents)) / 100
        ar = '1110' if invoice.payment_method == 'insurance' else '1100'
        try:
            async with self.db.begin_nested():
                await post_compound_transaction(db=self.db,facility_id=facility_id,entries=[{'account_code':ar,'debit':amount,'credit':Decimal('0')},{'account_code':'4000','debit':Decimal('0'),'credit':amount}],metadata={'event_type':'invoice_finalized','description':f'Invoice {invoice.invoice_number}'},idempotency_key=f'invoice_finalized:{invoice.id}',user_id=user_id)
        except Exception as exc:
            # GL must never block billing, but a silent ledger gap is a
            # reconciliation incident — always leave a trace.
            _logger.warning(
                "billing.gl.invoice_post_failed invoice=%s error=%s",
                invoice.invoice_number, exc,
            )

    async def _post_payment_gl(self, payment, invoice, facility_id, user_id):
        from decimal import Decimal
        if payment.amount_cents <= 0:
            return
        try:
            from app.services.finance import post_compound_transaction
        except ImportError:
            return
        amount = Decimal(str(payment.amount_cents)) / 100
        ar = '1110' if invoice.payment_method == 'insurance' else '1100'
        cash = '1010' if payment.payment_method in ('cash','exemption') else '1020'
        try:
            async with self.db.begin_nested():
                await post_compound_transaction(db=self.db,facility_id=facility_id,entries=[{'account_code':cash,'debit':amount,'credit':Decimal('0')},{'account_code':ar,'debit':Decimal('0'),'credit':amount}],metadata={'event_type':'payment_received','description':f'Payment {invoice.invoice_number} via {payment.payment_method}'},idempotency_key=f'payment_received:{payment.id}',user_id=user_id)
        except Exception as exc:
            _logger.warning(
                "billing.gl.payment_post_failed invoice=%s error=%s",
                invoice.invoice_number, exc,
            )

    async def _next_invoice_number(self, facility_id: uuid.UUID) -> str:
        """Generate the next invoice number (INV-YYYYMMDD-XXXX)."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"INV-{today}-"

        result = await self.db.execute(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.invoice_number.like(f"{prefix}%"),
            )
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"


