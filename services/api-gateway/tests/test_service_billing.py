"""Point-of-sale billing for ordered services (lab, imaging, pharmacy).

A clinician's order is charged when it is raised, released only once it is
paid, and the payment carries the receipt the patient shows at the service
desk before the lab, the x-ray room or the pharmacy will serve them.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.base import EventBase
from app.models.billing import InvoiceItem, Payment
from app.schemas.lab import LabOrderCreate, LabTestRequest
from app.schemas.radiology import ImagingOrderCreate
from app.services.billing_service import BillingService
from app.services.imaging_fee import resolve_imaging_price_cents
from app.services.lab_catalog import seed_default_lab_catalog
from app.services.lab_service import LabService
from app.services.radiology_service import RadiologyService
from app.services.service_billing import (
    IMAGING_ORDER,
    LAB_ORDER,
    PRESCRIPTION,
    SERVICE_PAYMENT_EVENT,
    ServiceBillingService,
    build_service_reference,
    parse_service_reference,
    post_service_charge,
)
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _billed_lab_order(db) -> tuple[object, uuid.UUID]:
    """
    Raise a lab order whose catalogued test (Malaria RDT, KES 200) is billed.

    @param db: Database session
    @returns Tuple of (lab order, encounter id)
    """
    await seed_default_lab_catalog(db, FACILITY_ID, USER_ID)
    encounter_id = uuid.uuid4()
    order = await LabService(db).create_order(
        LabOrderCreate(
            encounter_id=encounter_id,
            patient_id=uuid.uuid4(),
            priority="routine",
            tests=[LabTestRequest(test_code="MRDT", test_name="Malaria RDT")],
        ),
        FACILITY_ID,
        USER_ID,
    )
    await db.flush()
    return order, encounter_id


def test_imaging_price_prefers_study_then_modality_then_default() -> None:
    """The most specific configured imaging price wins."""
    settings = {
        "imaging_prices": {
            "default_cents": 111_000,
            "by_modality": {"xray": 150_000},
            "by_study": {"chest x-ray pa": 175_000},
        }
    }

    assert (
        resolve_imaging_price_cents(
            settings, modality="xray", study_description="Chest X-Ray PA"
        )
        == 175_000
    )
    assert (
        resolve_imaging_price_cents(
            settings, modality="xray", study_description="Knee"
        )
        == 150_000
    )
    assert resolve_imaging_price_cents(settings, modality="ct") == 111_000


def test_imaging_price_falls_back_to_builtin_defaults() -> None:
    """A facility that configured nothing still gets a billable price."""
    assert resolve_imaging_price_cents(None, modality="ct") == 900_000
    assert resolve_imaging_price_cents({}, modality="unknown") == 200_000


def test_imaging_price_of_zero_turns_billing_off() -> None:
    """A facility can stop charging for a modality."""
    settings = {"imaging_prices": {"by_modality": {"xray": 0}}}
    assert resolve_imaging_price_cents(settings, modality="xray") == 0


def test_imaging_price_ignores_unusable_overrides() -> None:
    """Strings, booleans and negatives are not prices."""
    settings = {
        "imaging_prices": {
            "default_cents": True,
            "by_modality": {"ct": -5},
        }
    }
    assert resolve_imaging_price_cents(settings, modality="ct") == 900_000


@pytest.mark.asyncio
async def test_service_charge_posts_a_line_and_recomputes_the_invoice() -> None:
    """A priced request lands on the encounter's open invoice; a free one does not."""
    async with session_factory() as db:
        encounter_id = uuid.uuid4()
        patient_id = uuid.uuid4()

        free = await post_service_charge(
            db,
            facility_id=FACILITY_ID,
            encounter_id=encounter_id,
            patient_id=patient_id,
            item_type="procedure",
            description="Imaging: Chest X-Ray",
            unit_price_cents=0,
            reference_type=IMAGING_ORDER,
            reference_id=uuid.uuid4(),
            created_by=USER_ID,
        )
        assert free is None
        assert (
            await ServiceBillingService(db).list_charges(
                encounter_id, FACILITY_ID
            )
            == []
        )

        request_id = uuid.uuid4()
        invoice = await post_service_charge(
            db,
            facility_id=FACILITY_ID,
            encounter_id=encounter_id,
            patient_id=patient_id,
            item_type="procedure",
            description="Imaging: Chest X-Ray",
            unit_price_cents=150_000,
            reference_type=IMAGING_ORDER,
            reference_id=request_id,
            created_by=USER_ID,
        )
        assert invoice is not None
        assert invoice.total_cents == 150_000
        assert invoice.balance_cents == 150_000

        charges = await ServiceBillingService(db).list_charges(
            encounter_id, FACILITY_ID
        )
        assert len(charges) == 1
        assert charges[0].reference_type == IMAGING_ORDER
        assert charges[0].reference_id == request_id
        assert charges[0].total_cents == 150_000
        assert charges[0].paid is False


@pytest.mark.asyncio
async def test_imaging_order_is_billed_at_the_facility_price() -> None:
    """An imaging study reaches the bill (radiology previously billed nothing)."""
    async with session_factory() as db:
        encounter_id = uuid.uuid4()
        patient_id = uuid.uuid4()

        order = await RadiologyService(db).create_order(
            ImagingOrderCreate(
                encounter_id=encounter_id,
                patient_id=patient_id,
                modality="xray",
                body_part="chest",
                study_description="Chest X-Ray PA",
                priority="routine",
            ),
            FACILITY_ID,
            USER_ID,
        )
        await db.flush()

        # Built-in x-ray price, because the test facility configured none.
        assert order.total_cost_cents == 150_000

        lines = (
            await db.execute(
                select(InvoiceItem).where(
                    InvoiceItem.reference_type == IMAGING_ORDER,
                    InvoiceItem.reference_id == order.id,
                )
            )
        ).scalars().all()
        assert len(lines) == 1
        assert lines[0].item_type == "procedure"
        assert lines[0].total_cents == 150_000


@pytest.mark.asyncio
async def test_ordered_lab_request_is_gated_until_it_is_paid() -> None:
    """An unpaid lab request is listed, refused at release, then released."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)

        charges = await billing.list_charges(encounter_id, FACILITY_ID)
        assert len(charges) == 1
        charge = charges[0]
        assert charge.reference_type == LAB_ORDER
        assert charge.reference_id == order.id
        assert charge.total_cents == 20_000
        assert charge.balance_cents == 20_000
        assert charge.paid is False

        with pytest.raises(ValueError, match="not paid"):
            await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)

        invoice, payment, collected = await billing.collect(
            encounter_id=encounter_id,
            facility_id=FACILITY_ID,
            received_by=USER_ID,
            payment_method="cash",
            reference_type=LAB_ORDER,
            reference_id=order.id,
        )
        assert payment is not None
        assert collected is not None
        assert payment.amount_cents == 20_000
        await db.flush()

        await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)

        settled = await billing.list_charges(encounter_id, FACILITY_ID)
        assert settled[0].paid is True
        assert settled[0].balance_cents == 0
        await db.refresh(invoice)
        assert invoice.balance_cents == 0


@pytest.mark.asyncio
async def test_settling_a_request_twice_does_not_charge_twice() -> None:
    """A double click at the desk returns the settled request untouched."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)

        invoice, first_payment, _ = await billing.collect(
            encounter_id=encounter_id,
            facility_id=FACILITY_ID,
            received_by=USER_ID,
            payment_method="cash",
            reference_type=LAB_ORDER,
            reference_id=order.id,
        )
        assert first_payment is not None
        await db.flush()

        again, second_payment, second_charge = await billing.collect(
            encounter_id=encounter_id,
            facility_id=FACILITY_ID,
            received_by=USER_ID,
            payment_method="cash",
            reference_type=LAB_ORDER,
            reference_id=order.id,
        )
        assert second_payment is None
        assert second_charge is not None
        assert second_charge.paid is True
        assert again.id == invoice.id

        payments = (
            await db.execute(
                select(Payment).where(Payment.invoice_id == invoice.id)
            )
        ).scalars().all()
        assert len(payments) == 1


@pytest.mark.asyncio
async def test_a_replayed_allocation_event_is_counted_once() -> None:
    """Two events naming the same payment must not double the amount paid."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)

        invoice, payment, _ = await billing.collect(
            encounter_id=encounter_id,
            facility_id=FACILITY_ID,
            received_by=USER_ID,
            payment_method="cash",
            reference_type=LAB_ORDER,
            reference_id=order.id,
        )
        assert payment is not None
        await db.flush()

        db.add(
            EventBase(
                facility_id=FACILITY_ID,
                stream_type="billing",
                stream_id=invoice.patient_id,
                event_type=SERVICE_PAYMENT_EVENT,
                event_data={
                    "payment_id": str(payment.id),
                    "invoice_id": str(invoice.id),
                    "reference_type": LAB_ORDER,
                    "reference_id": str(order.id),
                    "amount_cents": 20_000,
                },
                version=1,
                created_by=USER_ID,
            )
        )
        await db.flush()

        charges = await billing.list_charges(encounter_id, FACILITY_ID)
        assert charges[0].total_cents == 20_000
        assert charges[0].paid_cents == 20_000
        assert charges[0].balance_cents == 0


@pytest.mark.asyncio
async def test_uncatalogued_request_is_never_gated() -> None:
    """A test with no managed price is free, so it is never held at the desk."""
    async with session_factory() as db:
        encounter_id = uuid.uuid4()
        order = await LabService(db).create_order(
            LabOrderCreate(
                encounter_id=encounter_id,
                patient_id=uuid.uuid4(),
                priority="routine",
                tests=[
                    LabTestRequest(test_code="NOPE-1", test_name="Unlisted test")
                ],
            ),
            FACILITY_ID,
            USER_ID,
        )
        await db.flush()
        assert order.total_cost_cents == 0

        billing = ServiceBillingService(db)
        assert await billing.charge_for(FACILITY_ID, LAB_ORDER, order.id) is None
        await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)
        assert await billing.list_charges(encounter_id, FACILITY_ID) == []


# ---- M-Pesa: money that arrives against an invoice ------------------------


def test_mpesa_account_reference_carries_the_request_it_pays_for() -> None:
    """The tag rides on the account reference and survives a Daraja round trip."""
    request_id = uuid.uuid4()
    tagged = build_service_reference(
        "INV-20260922-0001", PRESCRIPTION, request_id
    )
    assert tagged == "INV-20260922-0001#prescription:" + str(request_id)
    assert parse_service_reference(tagged) == (PRESCRIPTION, request_id)


def test_an_untagged_account_reference_settles_whatever_it_can() -> None:
    """A plain invoice number, a malformed tag or nothing at all is a request."""
    assert parse_service_reference("INV-20260922-0001") is None
    assert parse_service_reference(None) is None
    assert parse_service_reference("INV-1#lab_order:not-a-uuid") is None
    assert parse_service_reference(
        "INV-1#encounter:" + str(uuid.uuid4())
    ) is None


@pytest.mark.asyncio
async def test_a_tagged_mpesa_payment_releases_the_named_request() -> None:
    """The callback's own money releases the request named on the STK push."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)
        charge = (await billing.list_charges(encounter_id, FACILITY_ID))[0]

        payment = await BillingService(db).record_external_payment(
            invoice_id=charge.invoice_id,
            amount_cents=charge.balance_cents,
            mpesa_receipt="QH12345678",
            phone_number="254712345678",
            received_by=USER_ID,
        )
        assert payment is not None

        tagged = build_service_reference(
            charge.invoice_number, LAB_ORDER, order.id
        )
        named = parse_service_reference(tagged)
        assert named is not None

        settled = await billing.settle_invoice_requests(
            facility_id=FACILITY_ID,
            invoice_id=charge.invoice_id,
            payment_id=payment.id,
            amount_cents=charge.balance_cents,
            created_by=USER_ID,
            reference_type=named[0],
            reference_id=named[1],
        )
        await db.flush()

        assert [c.reference_id for c in settled] == [order.id]
        await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)
        released = await billing.list_charges(encounter_id, FACILITY_ID)
        assert released[0].paid is True

@pytest.mark.asyncio
async def test_an_untagged_mpesa_payment_prefers_the_exact_match() -> None:
    """Money that matches one request exactly is not spent on a bigger one."""
    async with session_factory() as db:
        encounter_id = uuid.uuid4()
        first_id = uuid.uuid4()
        second_id = uuid.uuid4()

        for request_id, price in ((first_id, 150_000), (second_id, 20_000)):
            await post_service_charge(
                db,
                facility_id=FACILITY_ID,
                encounter_id=encounter_id,
                patient_id=uuid.uuid4(),
                item_type="procedure",
                description="Imaging: " + str(request_id),
                unit_price_cents=price,
                reference_type=IMAGING_ORDER,
                reference_id=request_id,
                created_by=USER_ID,
            )
        await db.flush()

        billing = ServiceBillingService(db)
        charges = await billing.list_charges(encounter_id, FACILITY_ID)
        assert len(charges) == 2
        invoice_id = charges[0].invoice_id
        assert charges[1].invoice_id == invoice_id

        # The patient pays only the small, newer request.
        payment = await BillingService(db).record_external_payment(
            invoice_id=invoice_id,
            amount_cents=20_000,
            mpesa_receipt="QH87654321",
            phone_number="254712345678",
            received_by=USER_ID,
        )
        assert payment is not None
        await billing.settle_invoice_requests(
            facility_id=FACILITY_ID,
            invoice_id=invoice_id,
            payment_id=payment.id,
            amount_cents=20_000,
            created_by=USER_ID,
        )
        await db.flush()

        await billing.assert_service_paid(
            FACILITY_ID, IMAGING_ORDER, second_id
        )
        with pytest.raises(ValueError, match="not paid"):
            await billing.assert_service_paid(
                FACILITY_ID, IMAGING_ORDER, first_id
            )

@pytest.mark.asyncio
async def test_a_part_payment_releases_nothing_until_the_balance_is_met() -> None:
    """Half the money holds the request; the second half releases it."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)
        charge = (await billing.list_charges(encounter_id, FACILITY_ID))[0]

        first = await BillingService(db).record_external_payment(
            invoice_id=charge.invoice_id,
            amount_cents=10_000,
            mpesa_receipt="QH00000001",
            received_by=USER_ID,
        )
        assert first is not None
        await billing.settle_invoice_requests(
            facility_id=FACILITY_ID,
            invoice_id=charge.invoice_id,
            payment_id=first.id,
            amount_cents=10_000,
            created_by=USER_ID,
        )
        await db.flush()

        with pytest.raises(ValueError, match="not paid"):
            await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)
        part = (await billing.list_charges(encounter_id, FACILITY_ID))[0]
        assert part.paid_cents == 10_000
        assert part.balance_cents == 10_000

        second = await BillingService(db).record_external_payment(
            invoice_id=charge.invoice_id,
            amount_cents=10_000,
            mpesa_receipt="QH00000002",
            received_by=USER_ID,
        )
        assert second is not None
        await billing.settle_invoice_requests(
            facility_id=FACILITY_ID,
            invoice_id=charge.invoice_id,
            payment_id=second.id,
            amount_cents=10_000,
            created_by=USER_ID,
        )
        await db.flush()

        await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)
        settled = (await billing.list_charges(encounter_id, FACILITY_ID))[0]
        assert settled.balance_cents == 0

@pytest.mark.asyncio
async def test_repeating_a_callback_cannot_credit_a_request_twice() -> None:
    """Safaricom retries callbacks; the request must only be credited once."""
    async with session_factory() as db:
        order, encounter_id = await _billed_lab_order(db)
        billing = ServiceBillingService(db)
        charge = (await billing.list_charges(encounter_id, FACILITY_ID))[0]

        payment = await BillingService(db).record_external_payment(
            invoice_id=charge.invoice_id,
            amount_cents=charge.balance_cents,
            mpesa_receipt="QH11111111",
            received_by=USER_ID,
        )
        assert payment is not None

        for _ in range(2):
            await billing.settle_invoice_requests(
                facility_id=FACILITY_ID,
                invoice_id=charge.invoice_id,
                payment_id=payment.id,
                amount_cents=charge.balance_cents,
                created_by=USER_ID,
            )
            await db.flush()

        events = (
            await db.execute(
                select(EventBase).where(
                    EventBase.event_type == SERVICE_PAYMENT_EVENT,
                    EventBase.event_data["reference_id"].as_string()
                    == str(order.id),
                )
            )
        ).scalars().all()
        assert len(events) == 1

        after = (await billing.list_charges(encounter_id, FACILITY_ID))[0]
        assert after.paid_cents == 20_000
        assert after.balance_cents == 0
        await billing.assert_service_paid(FACILITY_ID, LAB_ORDER, order.id)