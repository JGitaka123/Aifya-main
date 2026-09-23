"""D2/D6: lab orders add a priced catalog line to the encounter invoice."""

import uuid

import pytest
from sqlalchemy import select

from app.models.billing import Invoice, InvoiceItem
from app.schemas.lab import LabOrderCreate, LabTestRequest
from app.services.lab_catalog import seed_default_lab_catalog
from app.services.lab_service import LabService
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest.mark.asyncio
async def test_lab_order_adds_priced_line_to_encounter_invoice() -> None:
    """
    Ordering a catalogued test (Malaria RDT, KES 200) adds exactly one lab
    line to the encounter's open invoice at the managed catalog price, and
    the invoice total/balance grow accordingly (D2 revenue leak closed).
    """
    async with session_factory() as db:
        seeded = await seed_default_lab_catalog(db, FACILITY_ID, USER_ID)
        assert seeded > 0

        encounter_id = uuid.uuid4()
        patient_id = uuid.uuid4()

        # Existing consultation draft invoice (KES 1,000), like the QA case.
        invoice = Invoice(
            facility_id=FACILITY_ID,
            encounter_id=encounter_id,
            patient_id=patient_id,
            invoice_number="INV-D2",
            status="draft",
            subtotal_cents=100_000,
            total_cents=100_000,
            balance_cents=100_000,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(invoice)
        await db.flush()
        db.add(
            InvoiceItem(
                facility_id=FACILITY_ID,
                invoice_id=invoice.id,
                item_type="consultation",
                description="OPD Consultation",
                quantity=1,
                unit_price_cents=100_000,
                total_cents=100_000,
                discount_cents=0,
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.flush()

        order = await LabService(db).create_order(
            LabOrderCreate(
                encounter_id=encounter_id,
                patient_id=patient_id,
                priority="routine",
                tests=[LabTestRequest(test_code="MRDT", test_name="Malaria RDT")],
            ),
            FACILITY_ID,
            USER_ID,
        )
        await db.flush()

        # Order priced from the catalog (not the request).
        assert order.total_cost_cents == 20_000

        # Exactly one lab line was added at the catalog price.
        items = (
            await db.execute(
                select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)
            )
        ).scalars().all()
        lab_lines = [i for i in items if i.item_type == "lab"]
        assert len(lab_lines) == 1
        assert lab_lines[0].total_cents == 20_000

        # Invoice total/balance grew by the lab charge (1,000 -> 1,200).
        await db.refresh(invoice)
        assert invoice.total_cents == 120_000
        assert invoice.balance_cents == 120_000
