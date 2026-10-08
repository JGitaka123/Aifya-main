"""Directing a patient from the consultation room to another unit.

Reception routes a patient once, at registration. The consultation room is
where the clinician sends them on to Dental, Physiotherapy, Laboratory or
Pharmacy. Routing records an internal referral *and* re-queues the encounter in
the destination unit, so the patient actually turns up in that unit's queue.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.staff import Department
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest.fixture
async def patient_id(client: AsyncClient) -> str:
    """Create a test patient and return their ID."""
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Peter",
            "last_name": "Otieno",
            "date_of_birth": "1990-03-14",
            "gender": "male",
            "phone_number": "0722000111",
        },
    )
    return response.json()["id"]


async def _make_department(code: str, name: str) -> str:
    """Insert a department directly, since tests do not seed the HR module."""
    async with session_factory() as db:
        department = Department(
            facility_id=FACILITY_ID,
            code=code,
            name=name,
            department_type="clinical",
            is_active=True,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(department)
        await db.commit()
        await db.refresh(department)
        return str(department.id)


async def _make_encounter(
    client: AsyncClient, patient_id: str, department_id: str | None = None
) -> dict:
    payload: dict = {
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Toothache for two days",
    }
    if department_id is not None:
        payload["department_id"] = department_id
    response = await client.post("/api/v1/encounters", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_route_moves_patient_to_destination_and_queues_them(
    client: AsyncClient, patient_id: str
) -> None:
    """Routing hands the patient to the destination unit's queue."""
    opd_id = await _make_department("OPD", "General OPD")
    dental_id = await _make_department("DEN", "Dental")
    encounter = await _make_encounter(client, patient_id, opd_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": dental_id,
            "urgency": "urgent",
            "reason": "Carious molar needs extraction",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["receiving_department_id"] == dental_id
    assert data["receiving_department_name"] == "Dental"
    assert data["referral_number"].startswith("REF-")
    # Re-queued for the new unit, waiting to be called again.
    assert data["encounter"]["department_id"] == dental_id
    assert data["encounter"]["status"] == "waiting"

    # The destination owns the patient now, so they appear on that unit's
    # board rather than the front-door queue they were routed out of.
    queue = await client.get(
        f"/api/v1/encounters/queue?department_id={dental_id}"
    )
    routed = next(
        item
        for item in queue.json()["items"]
        if item["id"] == encounter["id"]
    )
    assert routed["department_id"] == dental_id


@pytest.mark.asyncio
async def test_route_records_an_internal_referral_on_the_trail(
    client: AsyncClient, patient_id: str
) -> None:
    """The trail shows who sent the patient where, and why."""
    opd_id = await _make_department("OPD", "General OPD")
    physio_id = await _make_department("PHY", "Physiotherapy")
    encounter = await _make_encounter(client, patient_id, opd_id)

    await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": physio_id,
            "urgency": "routine",
            "reason": "Lower back pain - physiotherapy review",
        },
    )

    response = await client.get(f"/api/v1/encounters/{encounter['id']}/routes")
    assert response.status_code == 200
    routes = response.json()
    assert len(routes) == 1
    assert routes[0]["referring_department_id"] == opd_id
    assert routes[0]["referring_department_name"] == "General OPD"
    assert routes[0]["receiving_department_name"] == "Physiotherapy"
    assert routes[0]["urgency"] == "routine"
    assert routes[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_route_to_the_patients_current_unit_is_rejected(
    client: AsyncClient, patient_id: str
) -> None:
    """Sending a patient to the unit they are already in is a mistake."""
    opd_id = await _make_department("OPD", "General OPD")
    encounter = await _make_encounter(client, patient_id, opd_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": opd_id,
            "reason": "Same unit",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_route_to_an_unknown_department_is_rejected(
    client: AsyncClient, patient_id: str
) -> None:
    """A destination that is not a configured unit cannot receive a patient."""
    encounter = await _make_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": str(uuid.uuid4()),
            "reason": "Nowhere in particular",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_route_requires_a_reason(client: AsyncClient, patient_id: str) -> None:
    """A hand-off without a reason is not a clinical record."""
    dental_id = await _make_department("DEN", "Dental")
    encounter = await _make_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={"receiving_department_id": dental_id, "reason": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_closed_visit_cannot_be_routed(
    client: AsyncClient, patient_id: str
) -> None:
    """A cancelled visit is over, so it cannot be handed on."""
    dental_id = await _make_department("DEN", "Dental")
    encounter = await _make_encounter(client, patient_id)
    await client.patch(
        f"/api/v1/encounters/{encounter['id']}", json={"status": "cancelled"}
    )

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={"receiving_department_id": dental_id, "reason": "Too late"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_route_unknown_encounter_is_not_found(client: AsyncClient) -> None:
    """Routing a non-existent encounter is a 404."""
    dental_id = await _make_department("DEN", "Dental")
    response = await client.post(
        f"/api/v1/encounters/{uuid.uuid4()}/route",
        json={"receiving_department_id": dental_id, "reason": "Ghost patient"},
    )
    assert response.status_code == 404
