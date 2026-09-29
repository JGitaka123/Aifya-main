"""Admission orders — the bridge between consultation and IPD.

The point of an admission order is that it is *not* an admission. A clinician
asking for a bed must never create an inpatient on its own; only the admission
desk accepting the request and assigning a ward and bed does that. These tests
pin that separation down, because it is the kind of guarantee that quietly
regresses.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def patient_id(client: AsyncClient) -> str:
    """Create a test patient and return their ID."""
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "John",
            "last_name": "Kamau",
            "date_of_birth": "1978-04-11",
            "gender": "male",
            "phone_number": "0733000444",
        },
    )
    return response.json()["id"]


@pytest.fixture
async def encounter_id(client: AsyncClient, patient_id: str) -> str:
    """Create an open OPD encounter to request admission from."""
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Severe pneumonia",
        },
    )
    return response.json()["id"]


@pytest.fixture
async def bed(client: AsyncClient) -> dict:
    """Create a ward with one bed and return both."""
    ward = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Medical Ward",
            "code": "MED",
            "ward_type": "general",
            "total_beds": 1,
        },
    )
    ward_id = ward.json()["id"]

    created = await client.post(
        "/api/v1/ipd/beds",
        json={"ward_id": ward_id, "bed_number": "M-12"},
    )
    return {"ward_id": ward_id, "bed_id": created.json()["id"]}


async def _raise_order(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> dict:
    """Raise an admission order and return the response body."""
    response = await client.post(
        "/api/v1/ipd/admission-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "reason": "Needs IV antibiotics and oxygen",
            "primary_diagnosis": "Pneumonia",
            "admission_type": "urgent",
            "priority": "urgent",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_requesting_admission_does_not_admit_the_patient(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """The clinician's request creates an order, never an inpatient."""
    order = await _raise_order(client, encounter_id, patient_id)

    assert order["status"] == "pending"
    assert order["order_number"].startswith("AO-")
    assert order["admission_id"] is None
    assert order["encounter_id"] == encounter_id
    assert order["admission_type"] == "urgent"

    # The crucial assertion: nobody is on the ward board yet.
    admissions = await client.get("/api/v1/ipd/admissions")
    assert admissions.json()["total"] == 0


@pytest.mark.asyncio
async def test_a_visit_cannot_have_two_open_requests(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """The desk must always know which request it is working."""
    await _raise_order(client, encounter_id, patient_id)

    duplicate = await client.post(
        "/api/v1/ipd/admission-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "reason": "Second request",
        },
    )
    assert duplicate.status_code == 400


@pytest.mark.asyncio
async def test_accepting_then_assigning_a_bed_creates_the_admission(
    client: AsyncClient, encounter_id: str, patient_id: str, bed: dict
) -> None:
    """Acceptance is a decision; the bed assignment is the admission."""
    order = await _raise_order(client, encounter_id, patient_id)

    accepted = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/accept",
        json={"decision_notes": "Ward has capacity"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    # Still nobody in a bed.
    assert (await client.get("/api/v1/ipd/admissions")).json()["total"] == 0

    admitted = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/admit",
        json={"ward_id": bed["ward_id"], "bed_id": bed["bed_id"]},
    )
    assert admitted.status_code == 201, admitted.text
    admission = admitted.json()
    assert admission["admission_number"].startswith("IP-")
    assert admission["admitted_from"] == "opd"
    assert admission["admission_reason"] == "Needs IV antibiotics and oxygen"

    # The order now points at the admission it became.
    detail = await client.get(f"/api/v1/ipd/admission-orders/{order['id']}")
    assert detail.json()["status"] == "admitted"
    assert detail.json()["admission_id"] == admission["id"]

    assert (await client.get("/api/v1/ipd/admissions")).json()["total"] == 1


@pytest.mark.asyncio
async def test_accepting_without_a_free_bed_records_bed_pending(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """A ward that has accepted but has no bed still owes the patient one."""
    order = await _raise_order(client, encounter_id, patient_id)

    accepted = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/accept",
        json={"bed_pending": True},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "bed_pending"

    # It stays in the open queue so it cannot be forgotten.
    open_orders = await client.get("/api/v1/ipd/admission-orders?status=open")
    assert open_orders.json()["total"] == 1
    assert (await client.get("/api/v1/ipd/admissions")).json()["total"] == 0


@pytest.mark.asyncio
async def test_declining_closes_the_request(
    client: AsyncClient, encounter_id: str, patient_id: str, bed: dict
) -> None:
    """A declined request cannot be admitted afterwards."""
    order = await _raise_order(client, encounter_id, patient_id)

    declined = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/decline",
        json={"decision_notes": "No clinical indication for admission"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"

    late = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/admit",
        json={"ward_id": bed["ward_id"], "bed_id": bed["bed_id"]},
    )
    assert late.status_code == 400
    assert (await client.get("/api/v1/ipd/admissions")).json()["total"] == 0


@pytest.mark.asyncio
async def test_cancelling_a_request_leaves_the_patient_an_outpatient(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """Withdrawing the request before it is worked admits nobody."""
    order = await _raise_order(client, encounter_id, patient_id)

    cancelled = await client.post(
        f"/api/v1/ipd/admission-orders/{order['id']}/cancel",
        json={"decision_notes": "Patient improved after treatment"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    open_orders = await client.get("/api/v1/ipd/admission-orders?status=open")
    assert open_orders.json()["total"] == 0
    assert (await client.get("/api/v1/ipd/admissions")).json()["total"] == 0


@pytest.mark.asyncio
async def test_a_closed_visit_cannot_raise_a_new_request(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """Admission is requested from an open consultation, not a finished visit."""
    await client.patch(
        f"/api/v1/encounters/{encounter_id}",
        json={"status": "completed", "outcome": "Visit closed for the test"},
    )

    response = await client.post(
        "/api/v1/ipd/admission-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "reason": "Too late",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unknown_order_is_not_found(client: AsyncClient) -> None:
    """A missing order is a 404, not a stack trace."""
    response = await client.get(f"/api/v1/ipd/admission-orders/{uuid.uuid4()}")
    assert response.status_code == 404
