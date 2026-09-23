"""Point-of-sale billing for ordered services (lab, imaging, pharmacy).

A clinician orders lab tests, an imaging study or a medicine. The patient pays
for that request at the front desk, takes the printed receipt to the service
point, and the service is released only once the request is paid.

Where the money lives
---------------------
Charges are ordinary InvoiceItem rows on the encounter invoice, tagged with
reference_type / reference_id naming the request they belong to. Payments are
ordinary Payment rows. A point-of-sale payment additionally records which
request it settles in a ServicePaymentRecorded event, so the question "is this
request paid?" is answered without a new table or column:

    paid_cents(request) = sum of ServicePaymentRecorded amounts naming it

Amounts are de-duplicated by payment id, so a retried payment can never be
counted twice. A request with no charge at all (free test, uncatalogued drug,
study priced at 0) reports as paid, so the gate can never strand a patient.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.billing import Invoice, InvoiceItem, Payment

# Reference types the point of sale collects for.
LAB_ORDER = "lab_order"
IMAGING_ORDER = "imaging_order"
PRESCRIPTION = "prescription"

SERVICE_REFERENCE_TYPES: tuple[str, ...] = (LAB_ORDER, IMAGING_ORDER, PRESCRIPTION)

# Event tying a payment to the request it settles.
SERVICE_PAYMENT_EVENT = "ServicePaymentRecorded"

# Human labels used in refusal messages.
REFERENCE_LABELS: dict[str, str] = {
    LAB_ORDER: "Lab request",
    IMAGING_ORDER: "Imaging request",
    PRESCRIPTION: "Prescription",
}

# Statuses that mean the bill can no longer take money.
_CLOSED_INVOICE_STATUSES = ("cancelled", "waived")


@dataclass
class ServiceCharge:
    """What a patient owes for one ordered service."""

    encounter_id: uuid.UUID
    reference_type: str
    reference_id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    description: str
    total_cents: int
    paid_cents: int

    @property
    def balance_cents(self) -> int:
        """Outstanding amount for this request, floored at zero."""
        return max(self.total_cents - self.paid_cents, 0)

    @property
    def paid(self) -> bool:
        """Whether the request is settled (or was never charged)."""
        return self.total_cents <= 0 or self.balance_cents <= 0


def _summarise(descriptions: list[str], limit: int = 3) -> str:
    """
    Build a short receipt-friendly label from line item descriptions.

    @param descriptions: Line item descriptions in creation order
    @param limit: Maximum descriptions to spell out
    @returns Summary label
    """
    if not descriptions:
        return "Service"
    if len(descriptions) <= limit:
        return ", ".join(descriptions)
    shown = ", ".join(descriptions[:limit])
    return shown + " (+" + str(len(descriptions) - limit) + " more)"


# Marker separating the account reference a patient sees on the M-Pesa SMS from
# the internal note naming the request the payment should settle.
REFERENCE_MARKER = "#"


def build_service_reference(
    base: str,
    reference_type: str | None = None,
    reference_id: uuid.UUID | str | None = None,
) -> str:
    """
    Tag an M-Pesa account reference with the request it should settle.

    Daraja only shows the first twelve characters to the customer, so the
    human-readable part stays first and the marker rides along for our own
    callback to read.

    @param base: Reference shown on the M-Pesa SMS (usually the invoice number)
    @param reference_type: lab_order, imaging_order or prescription
    @param reference_id: The request UUID
    @returns Base reference, tagged when a request was named
    """
    if not reference_type or not reference_id:
        return base[:100]
    return f"{base}{REFERENCE_MARKER}{reference_type}:{reference_id}"[:100]


def parse_service_reference(
    reference: str | None,
) -> tuple[str, uuid.UUID] | None:
    """
    Read the request marker an STK push left in its account reference.

    @param reference: Stored account reference, tagged or untagged
    @returns (reference_type, reference_id) or None when untagged
    """
    if not reference or REFERENCE_MARKER not in reference:
        return None
    tail = reference.split(REFERENCE_MARKER, 1)[1]
    reference_type, _, raw_id = tail.partition(":")
    if reference_type not in SERVICE_REFERENCE_TYPES or not raw_id:
        return None
    try:
        return reference_type, uuid.UUID(raw_id)
    except (ValueError, AttributeError, TypeError):
        return None


class ServiceBillingService:
    """Point-of-sale lookups and collections for ordered services."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Charges

    async def _encounter_invoices(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[Invoice]:
        """
        Fetch the encounter's live invoices, oldest first.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Non-deleted, non-closed invoices
        """
        result = await self.db.execute(
            select(Invoice)
            .where(
                Invoice.encounter_id == encounter_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
                Invoice.status.notin_(_CLOSED_INVOICE_STATUSES),
            )
            .order_by(Invoice.created_at.asc())
        )
        return list(result.scalars().all())

    async def _paid_by_request(
        self,
        facility_id: uuid.UUID,
        keys: list[tuple[str, uuid.UUID]],
    ) -> dict[uuid.UUID, int]:
        """
        Sum the point-of-sale payments recorded against each request.

        De-duplicates by payment id so a retried payment is counted once.

        @param facility_id: Facility UUID
        @param keys: (reference_type, reference_id) pairs to total
        @returns Map of reference_id -> amount paid in cents
        """
        if not keys:
            return {}
        reference_ids = sorted({str(rid) for _rt, rid in keys})
        result = await self.db.execute(
            select(EventBase.event_data).where(
                EventBase.facility_id == facility_id,
                EventBase.event_type == SERVICE_PAYMENT_EVENT,
                EventBase.event_data["reference_id"].as_string().in_(reference_ids),
            )
        )

        totals: dict[uuid.UUID, int] = {}
        seen: set[tuple[str, str]] = set()
        for row in result.all():
            data = row[0] or {}
            raw_id = data.get("reference_id")
            payment_id = str(data.get("payment_id") or "")
            if not raw_id:
                continue
            marker = (payment_id, str(raw_id))
            if marker in seen:
                continue
            seen.add(marker)
            try:
                key = uuid.UUID(str(raw_id))
            except (ValueError, AttributeError):
                continue
            totals[key] = totals.get(key, 0) + int(data.get("amount_cents") or 0)
        return totals

    async def _charges_from_items(
        self,
        items: list[InvoiceItem],
        invoices: dict[uuid.UUID, Invoice],
        facility_id: uuid.UUID,
        encounter_id: uuid.UUID,
    ) -> list[ServiceCharge]:
        """
        Group invoice items into per-request charges.

        @param items: Charge line items
        @param invoices: Invoice lookup by id
        @param facility_id: Facility UUID
        @param encounter_id: Encounter UUID
        @returns One charge per ordered service
        """
        grouped: dict[tuple[str, uuid.UUID], dict] = {}
        for item in items:
            if item.reference_id is None or not item.reference_type:
                continue
            key = (item.reference_type, item.reference_id)
            entry = grouped.setdefault(
                key,
                {"total": 0, "invoice_id": item.invoice_id, "descriptions": []},
            )
            entry["total"] += int(item.total_cents or 0)
            entry["descriptions"].append(item.description)

        paid = await self._paid_by_request(facility_id, list(grouped))

        charges: list[ServiceCharge] = []
        for (reference_type, reference_id), entry in grouped.items():
            invoice = invoices.get(entry["invoice_id"])
            total = int(entry["total"])
            charges.append(
                ServiceCharge(
                    encounter_id=encounter_id,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    invoice_id=entry["invoice_id"],
                    invoice_number=invoice.invoice_number if invoice else "",
                    description=_summarise(entry["descriptions"]),
                    total_cents=total,
                    paid_cents=min(paid.get(reference_id, 0), total),
                )
            )
        return charges

    async def list_charges(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[ServiceCharge]:
        """
        List every ordered service on an encounter that carries a charge.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Charges in creation order
        """
        invoices = await self._encounter_invoices(encounter_id, facility_id)
        if not invoices:
            return []
        by_id = {invoice.id: invoice for invoice in invoices}
        result = await self.db.execute(
            select(InvoiceItem)
            .where(
                InvoiceItem.invoice_id.in_(list(by_id)),
                InvoiceItem.reference_type.in_(SERVICE_REFERENCE_TYPES),
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
            .order_by(InvoiceItem.created_at.asc())
        )
        return await self._charges_from_items(
            list(result.scalars().all()), by_id, facility_id, encounter_id
        )

    async def list_patient_charges(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        *,
        max_encounters: int = 5,
        include_paid: bool = False,
    ) -> list[ServiceCharge]:
        """
        Outstanding service charges across a patient's recent encounters.

        This is what the cashier searches on: a patient walks up with a
        prescription and the desk needs everything still owed.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param max_encounters: How many recent encounters to scan
        @param include_paid: Keep settled requests in the result
        @returns Charges across the scanned encounters
        """
        from app.models.encounter import Encounter

        result = await self.db.execute(
            select(Encounter.id)
            .where(
                Encounter.patient_id == patient_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(Encounter.encounter_date.desc())
            .limit(max_encounters)
        )
        charges: list[ServiceCharge] = []
        for encounter_id in result.scalars().all():
            charges.extend(await self.list_charges(encounter_id, facility_id))
        if include_paid:
            return charges
        return [charge for charge in charges if not charge.paid]

    async def charge_for(
        self,
        facility_id: uuid.UUID,
        reference_type: str,
        reference_id: uuid.UUID,
    ) -> ServiceCharge | None:
        """
        Fetch the charge for a single ordered service.

        @param facility_id: Facility UUID
        @param reference_type: lab_order, imaging_order or prescription
        @param reference_id: The request UUID
        @returns The charge, or None when the request was never billed
        """
        result = await self.db.execute(
            select(InvoiceItem)
            .where(
                InvoiceItem.facility_id == facility_id,
                InvoiceItem.reference_type == reference_type,
                InvoiceItem.reference_id == reference_id,
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
            .order_by(InvoiceItem.created_at.asc())
        )
        items = list(result.scalars().all())
        if not items:
            return None

        invoice = (
            await self.db.execute(
                select(Invoice).where(Invoice.id == items[0].invoice_id)
            )
        ).scalar_one_or_none()
        invoices = {invoice.id: invoice} if invoice else {}
        charges = await self._charges_from_items(
            items,
            invoices,
            facility_id,
            invoice.encounter_id if invoice else uuid.UUID(int=0),
        )
        return charges[0] if charges else None

    # Gate

    async def assert_service_paid(
        self,
        facility_id: uuid.UUID,
        reference_type: str,
        reference_id: uuid.UUID,
        *,
        label: str | None = None,
    ) -> None:
        """
        Refuse to release a service whose charge is still outstanding.

        A request with no charge passes through, so free and uncatalogued
        services keep working and legacy records are never stranded.

        @param facility_id: Facility UUID
        @param reference_type: lab_order, imaging_order or prescription
        @param reference_id: The request UUID
        @param label: Optional label for the message
        @raises ValueError: When the request has an unpaid charge
        """
        charge = await self.charge_for(facility_id, reference_type, reference_id)
        if charge is None or charge.paid:
            return
        name = label or REFERENCE_LABELS.get(reference_type, "Service")
        raise ValueError(
            name
            + " not paid: "
            + charge.description
            + " still has "
            + format(charge.balance_cents / 100, ",.2f")
            + " KES outstanding. Collect payment at the cashier and present"
            + " the receipt."
        )

    # Collection

    async def collect(
        self,
        *,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
        payment_method: str,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
        reference_number: str | None = None,
        mpesa_transaction_id: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Invoice, Payment | None, ServiceCharge | None]:
        """
        Take payment for one ordered service, or for the whole outstanding bill.

        Settling an already-settled request is a no-op returning the charge
        untouched, so a double click at the desk cannot take the money twice.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param received_by: Cashier staff UUID
        @param payment_method: cash, mpesa, insurance or exemption
        @param reference_type: Request kind, omit to settle the whole bill
        @param reference_id: Request UUID, omit to settle the whole bill
        @param reference_number: Optional receipt / M-Pesa reference
        @param mpesa_transaction_id: Optional M-Pesa transaction id
        @param notes: Optional free-text note
        @param idempotency_key: Optional client key for safe retries
        @raises ValueError: When there is nothing to pay
        @returns Tuple of (invoice, payment, charge); payment is None when the
            request was already settled
        """
        from app.schemas.billing import PaymentCreate
        from app.services.billing_service import BillingService

        invoices = await self._encounter_invoices(encounter_id, facility_id)
        if not invoices:
            raise ValueError("This visit has no open bill to pay")

        charge: ServiceCharge | None = None
        invoice: Invoice | None = None

        if reference_type and reference_id:
            charge = await self.charge_for(facility_id, reference_type, reference_id)
            if charge is None:
                raise ValueError(
                    "This request carries no charge, so there is nothing to pay"
                )
            invoice = next(
                (inv for inv in invoices if inv.id == charge.invoice_id), None
            )
            if invoice is None:
                raise ValueError("The bill holding this request is closed")
        else:
            invoice = next((inv for inv in invoices if inv.balance_cents > 0), None)
            if invoice is None:
                raise ValueError("This visit has nothing outstanding")

        amount = charge.balance_cents if charge is not None else invoice.balance_cents
        if amount <= 0:
            return invoice, None, charge

        payment = await BillingService(self.db).record_payment(
            invoice_id=invoice.id,
            data=PaymentCreate(
                amount_cents=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                mpesa_transaction_id=mpesa_transaction_id,
                notes=notes,
            ),
            facility_id=facility_id,
            received_by=received_by,
            idempotency_key=idempotency_key,
        )

        if payment is not None:
            await self.settle_invoice_requests(
                facility_id=facility_id,
                invoice_id=invoice.id,
                payment_id=payment.id,
                amount_cents=amount,
                created_by=received_by,
                reference_type=charge.reference_type if charge else None,
                reference_id=charge.reference_id if charge else None,
            )

        return invoice, payment, charge

    async def _record_allocation(
        self,
        *,
        facility_id: uuid.UUID,
        patient_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
        reference_type: str,
        reference_id: uuid.UUID,
        amount_cents: int,
        created_by: uuid.UUID | None,
    ) -> None:
        """
        Record which request a payment settled (idempotent per payment).

        @param facility_id: Facility UUID
        @param patient_id: Patient UUID
        @param invoice_id: Invoice UUID
        @param payment_id: Payment UUID
        @param reference_type: Request kind
        @param reference_id: Request UUID
        @param amount_cents: Amount applied to the request
        @param created_by: Cashier staff UUID
        """
        existing = await self.db.execute(
            select(EventBase.id).where(
                EventBase.facility_id == facility_id,
                EventBase.event_type == SERVICE_PAYMENT_EVENT,
                EventBase.event_data["payment_id"].as_string() == str(payment_id),
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="billing",
                stream_id=patient_id,
                event_type=SERVICE_PAYMENT_EVENT,
                event_data={
                    "payment_id": str(payment_id),
                    "invoice_id": str(invoice_id),
                    "reference_type": reference_type,
                    "reference_id": str(reference_id),
                    "amount_cents": amount_cents,
                },
                version=1,
                created_by=created_by,
            )
        )

    async def allocate_payment(
        self,
        *,
        facility_id: uuid.UUID,
        patient_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
        reference_type: str,
        reference_id: uuid.UUID,
        amount_cents: int,
        created_by: uuid.UUID | None,
    ) -> None:
        """
        Record which request a payment settled (idempotent per payment).

        Every collection path goes through here - cash at the desk, an M-Pesa
        STK push answered on the patient's phone, and a manually captured
        M-Pesa code - so "was this request paid for?" always has one answer.

        @param facility_id: Facility UUID
        @param patient_id: Patient UUID
        @param invoice_id: Invoice UUID
        @param payment_id: Payment UUID
        @param reference_type: Request kind
        @param reference_id: Request UUID
        @param amount_cents: Amount applied to the request
        @param created_by: Staff UUID that took the money, if known
        """
        await self._record_allocation(
            facility_id=facility_id,
            patient_id=patient_id,
            invoice_id=invoice_id,
            payment_id=payment_id,
            reference_type=reference_type,
            reference_id=reference_id,
            amount_cents=amount_cents,
            created_by=created_by,
        )

    async def settle_invoice_requests(
        self,
        *,
        facility_id: uuid.UUID,
        invoice_id: uuid.UUID,
        payment_id: uuid.UUID,
        amount_cents: int,
        created_by: uuid.UUID | None,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
    ) -> list[ServiceCharge]:
        """
        Apply a payment to the ordered services it clears on one invoice.

        Money confirmed by the machine (an M-Pesa callback) lands against an
        invoice rather than a named request, so which requests it pays for has
        to be decided here: a named request first, then a request whose
        outstanding balance the money matches exactly, then the rest oldest
        first. A part payment therefore releases what the patient actually
        paid for instead of leaving it stuck behind the lab, x-ray or
        pharmacy desk.

        Requests that carry no charge are skipped, and an already-settled
        request is never credited twice, so a repeated callback cannot
        double-count a shilling.

        @param facility_id: Facility UUID
        @param invoice_id: Invoice UUID
        @param payment_id: Payment UUID
        @param amount_cents: Amount received, in cents
        @param created_by: Staff UUID that took the money, if known
        @param reference_type: Optional request kind to settle first
        @param reference_id: Optional request UUID to settle first
        @returns The charges this payment settled, in settlement order
        """
        if amount_cents <= 0:
            return []

        invoice = (
            await self.db.execute(
                select(Invoice).where(
                    Invoice.id == invoice_id,
                    Invoice.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if invoice is None:
            return []

        charges = await self.list_charges(invoice.encounter_id, facility_id)
        on_invoice = [c for c in charges if c.invoice_id == invoice_id]

        ordered: list[ServiceCharge] = []
        used: set[tuple[str, uuid.UUID]] = set()

        def take(charge: ServiceCharge) -> None:
            """Queue a charge once, ignoring repeats."""
            key = (charge.reference_type, charge.reference_id)
            if key not in used:
                used.add(key)
                ordered.append(charge)

        if reference_type and reference_id:
            for charge in on_invoice:
                if (
                    charge.reference_type == reference_type
                    and charge.reference_id == reference_id
                ):
                    take(charge)
        for charge in on_invoice:
            if charge.balance_cents == amount_cents:
                take(charge)
        for charge in on_invoice:
            take(charge)

        remaining = amount_cents
        settled: list[ServiceCharge] = []
        for charge in ordered:
            if remaining <= 0:
                break
            if charge.paid:
                continue
            applied = min(charge.balance_cents, remaining)
            if applied <= 0:
                continue
            await self.allocate_payment(
                facility_id=facility_id,
                patient_id=invoice.patient_id,
                invoice_id=invoice_id,
                payment_id=payment_id,
                reference_type=charge.reference_type,
                reference_id=charge.reference_id,
                amount_cents=applied,
                created_by=created_by,
            )
            remaining -= applied
            settled.append(charge)
        return settled

    # Receipt

    async def service_receipt_data(
        self, payment_id: uuid.UUID, facility_id: uuid.UUID
    ) -> tuple[Payment, Invoice, list[InvoiceItem]] | None:
        """
        Load the receipt payload for a point-of-sale payment.

        @param payment_id: Payment UUID
        @param facility_id: Facility UUID
        @returns (payment, invoice, charged items) or None when unknown
        """
        result = await self.db.execute(
            select(EventBase.event_data)
            .where(
                EventBase.facility_id == facility_id,
                EventBase.event_type == SERVICE_PAYMENT_EVENT,
                EventBase.event_data["payment_id"].as_string() == str(payment_id),
            )
            .order_by(EventBase.created_at.desc())
            .limit(1)
        )
        event_data = result.scalar_one_or_none()
        if not event_data:
            return None

        payment = (
            await self.db.execute(
                select(Payment).where(
                    Payment.id == payment_id,
                    Payment.facility_id == facility_id,
                )
            )
        ).scalar_one_or_none()
        if payment is None:
            return None

        invoice = (
            await self.db.execute(
                select(Invoice).where(Invoice.id == payment.invoice_id)
            )
        ).scalar_one_or_none()
        if invoice is None:
            return None

        items: list[InvoiceItem] = []
        reference_id = event_data.get("reference_id")
        reference_type = event_data.get("reference_type")
        if reference_id and reference_type:
            try:
                parsed_id = uuid.UUID(str(reference_id))
            except (ValueError, AttributeError):
                parsed_id = None
            if parsed_id is not None:
                rows = await self.db.execute(
                    select(InvoiceItem)
                    .where(
                        InvoiceItem.facility_id == facility_id,
                        InvoiceItem.reference_type == reference_type,
                        InvoiceItem.reference_id == parsed_id,
                        InvoiceItem.is_deleted == False,  # noqa: E712
                    )
                    .order_by(InvoiceItem.created_at.asc())
                )
                items = list(rows.scalars().all())

        return payment, invoice, items


async def post_service_charge(
    db: AsyncSession,
    *,
    facility_id: uuid.UUID,
    encounter_id: uuid.UUID,
    patient_id: uuid.UUID,
    item_type: str,
    description: str,
    unit_price_cents: int,
    reference_type: str,
    reference_id: uuid.UUID,
    created_by: uuid.UUID,
    quantity: int = 1,
) -> Invoice | None:
    """
    Add a priced line item to the encounter's open invoice.

    The encounter's draft invoice is reused when it has one, otherwise a new
    draft is opened, and the invoice totals are then recomputed from all of its
    line items. A zero price posts nothing, so free services never reach a bill.

    @param db: Database session
    @param facility_id: Facility scope
    @param encounter_id: Encounter the charge belongs to
    @param patient_id: Patient being billed
    @param item_type: Invoice item type (lab, procedure, pharmacy, ...)
    @param description: Line item description
    @param unit_price_cents: Unit price in KES cents
    @param reference_type: Kind of source record
    @param reference_id: Source record UUID
    @param created_by: Staff UUID
    @param quantity: Line quantity
    @returns The billed invoice, or None when there is nothing to charge
    """
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    if unit_price_cents <= 0 or quantity <= 0:
        return None

    invoice = (
        await db.execute(
            sa_select(Invoice).where(
                Invoice.encounter_id == encounter_id,
                Invoice.facility_id == facility_id,
                Invoice.status == "draft",
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().first()

    if invoice is None:
        from app.services.billing_service import BillingService

        invoice = Invoice(
            facility_id=facility_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
            invoice_number=await BillingService(db)._next_invoice_number(facility_id),
            status="draft",
            subtotal_cents=0,
            total_cents=0,
            balance_cents=0,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(invoice)
        await db.flush()

    db.add(
        InvoiceItem(
            facility_id=facility_id,
            invoice_id=invoice.id,
            item_type=item_type,
            description=description,
            quantity=quantity,
            unit_price_cents=unit_price_cents,
            total_cents=unit_price_cents * quantity,
            discount_cents=0,
            reference_id=reference_id,
            reference_type=reference_type,
            created_by=created_by,
            updated_by=created_by,
        )
    )
    await db.flush()

    items_total = int(
        (
            await db.execute(
                sa_select(func.coalesce(func.sum(InvoiceItem.total_cents), 0)).where(
                    InvoiceItem.invoice_id == invoice.id,
                    InvoiceItem.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()
    )
    invoice.subtotal_cents = items_total
    invoice.total_cents = items_total
    invoice.balance_cents = max(items_total - int(invoice.paid_cents or 0), 0)
    invoice.updated_by = created_by
    await db.flush()
    return invoice
