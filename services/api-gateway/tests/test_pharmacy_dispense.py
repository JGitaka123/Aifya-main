"""Dispensing safety tests: prescription/stock matching rules.

Clinical-safety path: drug dispensing must match the prescription —
quantity capped to what was prescribed, drug identity verified, no
double dispensing, substitutions explicitly documented.
"""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.prescription import Prescription
from tests.conftest import session_factory


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Dispense",
            "last_name": "Safety",
            "date_of_birth": "1980-01-01",
            "gender": "male",
            "phone_number": "0700000002",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_prescription(
    client: AsyncClient, patient_id: str, quantity: int = 10
) -> str:
    """Create an encounter with a Paracetamol prescription.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @param quantity: Prescribed quantity
    @returns Prescription UUID string
    """
    encounter = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Fever",
        },
    )
    assert encounter.status_code == 201
    encounter_id = encounter.json()["id"]

    rx = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "drug_name": "Paracetamol 500mg",
            "drug_code": "PARA-500",
            "generic_name": "Paracetamol",
            "dosage": "500mg",
            "route": "oral",
            "frequency": "tds",
            "duration_days": 3,
            "quantity": quantity,
        },
    )
    assert rx.status_code == 201, rx.text
    body = rx.json()
    assert body["blocked"] is False
    return body["prescription"]["id"]


async def _create_stock_item(
    client: AsyncClient,
    drug_code: str = "PARA-500",
    drug_name: str = "Paracetamol 500mg",
    generic_name: str = "Paracetamol",
    quantity: int = 100,
) -> str:
    """Create a pharmacy inventory item with stock on hand.

    @param client: Async HTTP test client
    @param drug_code: Formulary code
    @param drug_name: Brand/label name
    @param generic_name: Generic name
    @param quantity: Opening stock quantity
    @returns Pharmacy item UUID string
    """
    response = await client.post(
        "/api/v1/pharmacy/inventory",
        json={
            "drug_code": drug_code,
            "drug_name": drug_name,
            "generic_name": generic_name,
            "dosage_form": "tablet",
            "strength": "500mg",
            "unit_of_measure": "tablet",
            "reorder_level": 10,
            "selling_price_cents": 500,
            "buying_price_cents": 300,
            "current_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _dispense_payload(
    prescription_id: str, patient_id: str, item_id: str, quantity: int
) -> dict:
    """Build a dispense request payload.

    @param prescription_id: Prescription UUID string
    @param patient_id: Patient UUID string
    @param item_id: Pharmacy item UUID string
    @param quantity: Quantity to dispense
    @returns Dispense request body
    """
    return {
        "prescription_id": prescription_id,
        "patient_id": patient_id,
        "pharmacy_item_id": item_id,
        "quantity_dispensed": quantity,
        "counseling_done": True,
    }


@pytest.mark.asyncio
async def test_dispense_matching_drug_succeeds(client: AsyncClient) -> None:
    """Dispensing the prescribed drug at the prescribed quantity works."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 10),
    )
    assert response.status_code == 201, response.text
    assert response.json()["quantity_dispensed"] == 10


@pytest.mark.asyncio
async def test_dispense_cannot_exceed_prescribed_quantity(
    client: AsyncClient,
) -> None:
    """Over-dispensing beyond the prescription must be rejected."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 20),
    )
    assert response.status_code == 400
    assert "exceeds prescription" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_partial_then_remainder_cap(client: AsyncClient) -> None:
    """After a partial dispense, only the remaining balance may be issued."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    first = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 6),
    )
    assert first.status_code == 201

    too_much = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 6),
    )
    assert too_much.status_code == 400

    remainder = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 4),
    )
    assert remainder.status_code == 201


@pytest.mark.asyncio
async def test_dispense_fully_dispensed_prescription_rejected(
    client: AsyncClient,
) -> None:
    """A fully dispensed prescription cannot be dispensed again."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=5)
    item_id = await _create_stock_item(client)

    first = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 5),
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 5),
    )
    assert second.status_code == 400
    assert "cannot be dispensed" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dispense_wrong_drug_rejected(client: AsyncClient) -> None:
    """Selecting a different stock item than prescribed must be rejected."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    wrong_item_id = await _create_stock_item(
        client,
        drug_code="AMOX-250",
        drug_name="Amoxicillin 250mg",
        generic_name="Amoxicillin",
    )

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, wrong_item_id, 10),
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dispense_substitution_requires_reason(client: AsyncClient) -> None:
    """A substitution without a documented reason must be rejected."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    sub_item_id = await _create_stock_item(
        client,
        drug_code="PARA-GEN",
        drug_name="Panadol 500mg",
        generic_name="Panadol",
    )

    payload = _dispense_payload(rx_id, patient_id, sub_item_id, 10)
    payload["substitution_drug"] = "Panadol 500mg"
    rejected = await client.post("/api/v1/pharmacy/dispense", json=payload)
    assert rejected.status_code == 400
    assert "reason" in rejected.json()["detail"].lower()

    payload["substitution_reason"] = "Paracetamol brand out of stock"
    accepted = await client.post("/api/v1/pharmacy/dispense", json=payload)
    assert accepted.status_code == 201


@pytest.mark.asyncio
async def test_dispense_wrong_patient_rejected(client: AsyncClient) -> None:
    """The dispense request patient must match the prescription's patient."""
    patient_id = await _create_patient(client)
    other = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Other",
            "last_name": "Patient",
            "date_of_birth": "1975-01-01",
            "gender": "female",
            "phone_number": "0700000003",
        },
    )
    other_id = other.json()["id"]
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, other_id, item_id, 10),
    )
    assert response.status_code == 400
    assert "patient" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dispense_deducts_stock(client: AsyncClient) -> None:
    """Dispensing decrements the stock balance by the dispensed quantity."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client, quantity=50)

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 10),
    )
    assert response.status_code == 201

    inventory = await client.get(
        "/api/v1/pharmacy/inventory", params={"q": "PARA-500"}
    )
    assert inventory.status_code == 200
    items = [i for i in inventory.json()["items"] if i["id"] == item_id]
    assert len(items) == 1
    assert items[0]["current_quantity"] == 40


@pytest.mark.asyncio
async def test_dispense_idempotency_key_prevents_double_deduction(
    client: AsyncClient,
) -> None:
    """A retried dispense with the same X-Idempotency-Key must not deduct twice."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client, quantity=50)

    payload = _dispense_payload(rx_id, patient_id, item_id, 5)
    headers = {"X-Idempotency-Key": "dispense-retry-001"}

    first = await client.post(
        "/api/v1/pharmacy/dispense", json=payload, headers=headers
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/pharmacy/dispense", json=payload, headers=headers
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    inventory = await client.get(
        "/api/v1/pharmacy/inventory", params={"q": "PARA-500"}
    )
    items = [i for i in inventory.json()["items"] if i["id"] == item_id]
    assert items[0]["current_quantity"] == 45


@pytest.mark.asyncio
async def test_dispense_rejects_prescription_without_interaction_check(
    client: AsyncClient,
) -> None:
    """A legacy or tampered unchecked prescription cannot be dispensed."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    async with session_factory() as session:
        result = await session.execute(
            select(Prescription).where(Prescription.id == UUID(rx_id))
        )
        prescription = result.scalar_one()
        prescription.interaction_checked = False
        await session.commit()

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 10),
    )

    assert response.status_code == 400
    assert "interaction check not completed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dispense_rejects_persisted_critical_interaction(
    client: AsyncClient,
) -> None:
    """A critical interaction on a persisted prescription blocks dispensing."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=10)
    item_id = await _create_stock_item(client)

    async with session_factory() as session:
        result = await session.execute(
            select(Prescription).where(Prescription.id == UUID(rx_id))
        )
        prescription = result.scalar_one()
        prescription.interactions = [
            {"severity": "critical", "message": "Unsafe combination"}
        ]
        await session.commit()

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 10),
    )

    assert response.status_code == 400
    assert "critical drug interaction" in response.json()["detail"].lower()
