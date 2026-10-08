"""The seam between a clinical visit and the call board.

Registering or routing a patient must put them on the queue the speakers read
from, whatever unit they are sent to. These tests drive the real routers, so
they fail if the bridge between the encounter workflow and the queue engine is
ever unplugged again.
"""

import pytest
from httpx import AsyncClient

from app.models.staff import Department
from app.services.queue.broadcaster import broadcaster
from app.services.voice.text import build_call_text
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _department(code: str, name: str) -> str:
    """Insert a real department, since tests do not seed the HR module."""

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


async def _patient(client: AsyncClient, phone: str = "0700000000") -> str:
    """Register a patient and return their id."""

    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Amina",
            "last_name": "Wanjiku",
            "date_of_birth": "1995-03-10",
            "gender": "female",
            "phone_number": phone,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _visit(client: AsyncClient, patient_id: str, **overrides) -> dict:
    """Open a visit and return the created encounter."""

    payload = {
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Antenatal review",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/encounters", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _live_tickets(board: dict, encounter_id: str) -> list[dict]:
    """The live board rows that belong to one encounter."""

    return [t for t in board["items"] if t.get("encounter_id") == encounter_id]


@pytest.mark.asyncio
async def test_creating_a_visit_puts_the_patient_on_the_board(
    client: AsyncClient,
) -> None:
    """The reported bug: reception opened a visit and the board stayed empty."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)

    board = (await client.get("/api/v1/queue")).json()

    tickets = _live_tickets(board, encounter["id"])
    assert len(tickets) == 1
    assert tickets[0]["status"] == "WAITING"
    assert tickets[0]["patient_id"] == patient
    # A unitless front-desk visit still reads cleanly to the speaker.
    assert tickets[0]["ticket_number"].startswith("OPD")


@pytest.mark.asyncio
async def test_an_inpatient_admission_stays_off_the_call_board(
    client: AsyncClient,
) -> None:
    """An admission is not a wait, so it must not clutter the board."""

    patient = await _patient(client)
    encounter = await _visit(client, patient, encounter_type="ipd")

    board = (await client.get("/api/v1/queue")).json()

    assert _live_tickets(board, encounter["id"]) == []


@pytest.mark.asyncio
async def test_routing_moves_the_ticket_to_the_receiving_unit(
    client: AsyncClient,
) -> None:
    """Handing a patient to MCH clears the sender and queues the receiver."""

    sending = await _department("OPD", "Outpatient")
    receiving = await _department("MCH", "Maternal")
    patient = await _patient(client)
    encounter = await _visit(client, patient, department_id=sending)
    encounter_id = encounter["id"]

    before = (await client.get("/api/v1/queue")).json()
    assert _live_tickets(before, encounter_id)[0]["ticket_number"].startswith("OPD")

    routed = await client.post(
        f"/api/v1/encounters/{encounter_id}/route",
        json={
            "receiving_department_id": receiving,
            "urgency": "urgent",
            "reason": "Needs antenatal assessment",
        },
    )
    assert routed.status_code == 200, routed.text

    after = (await client.get("/api/v1/queue")).json()
    tickets = _live_tickets(after, encounter_id)
    assert len(tickets) == 1
    assert tickets[0]["department_id"] == receiving
    assert tickets[0]["ticket_number"].startswith("MCH")


@pytest.mark.asyncio
async def test_a_closed_visit_leaves_the_board(client: AsyncClient) -> None:
    """Completing a visit outside the queue board still clears its ticket."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    encounter_id = encounter["id"]

    closed = await client.patch(
        f"/api/v1/encounters/{encounter_id}",
        json={"status": "completed", "outcome": "Reviewed and discharged"},
    )
    assert closed.status_code == 200, closed.text

    board = (await client.get("/api/v1/queue")).json()

    assert _live_tickets(board, encounter_id) == []


@pytest.mark.asyncio
async def test_retriage_moves_the_patient_up_the_board(client: AsyncClient) -> None:
    """Making a waiting patient urgent must re-rank their ticket."""

    first_patient = await _patient(client, phone="0700000011")
    await _visit(client, first_patient)
    second_patient = await _patient(client, phone="0700000012")
    second = await _visit(client, second_patient)

    retriaged = await client.patch(
        f"/api/v1/encounters/{second['id']}",
        json={"triage_category": "emergency"},
    )
    assert retriaged.status_code == 200, retriaged.text

    called = (await client.post("/api/v1/queue/call-next", json={})).json()

    assert called["patient_id"] == second_patient
    assert called["triage_category"] == "emergency"


@pytest.mark.asyncio
async def test_admitting_the_patient_takes_the_ticket_off_the_board(
    client: AsyncClient,
) -> None:
    """A patient sent to a ward is not waiting, so their ticket must close."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    encounter_id = encounter["id"]

    ward = (
        await client.post(
            "/api/v1/ipd/wards",
            json={
                "name": "Maternity Ward",
                "code": "MATW",
                "ward_type": "general",
                "total_beds": 4,
            },
        )
    ).json()
    bed = (
        await client.post(
            "/api/v1/ipd/beds",
            json={
                "ward_id": ward["id"],
                "bed_number": "MAT-1",
                "bed_type": "standard",
            },
        )
    ).json()

    admitted = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient,
            "ward_id": ward["id"],
            "bed_id": bed["id"],
            "admitted_from": "opd",
        },
    )
    assert admitted.status_code == 201, admitted.text

    board = (await client.get("/api/v1/queue")).json()

    assert _live_tickets(board, encounter_id) == []


@pytest.mark.asyncio
async def test_mch_registration_puts_the_patient_on_the_board(
    client: AsyncClient,
) -> None:
    """A pregnancy registration is a patient waiting in the maternal clinic."""

    patient = await _patient(client)

    response = await client.post(
        "/api/v1/mch/anc",
        json={"patient_id": patient, "gravida": 2, "parity": 1},
    )
    assert response.status_code == 201, response.text

    board = (await client.get("/api/v1/queue")).json()
    mine = [t for t in board["items"] if t["patient_id"] == patient]
    assert len(mine) == 1
    assert mine[0]["ticket_number"].startswith("MCH")
    assert mine[0]["status"] == "WAITING"
    assert mine[0]["encounter_id"] is None


@pytest.mark.asyncio
async def test_mch_first_visit_reuses_the_registration_ticket(
    client: AsyncClient,
) -> None:
    """Recording the first visit must not queue the patient a second time."""

    patient = await _patient(client)
    profile = (
        await client.post(
            "/api/v1/mch/anc",
            json={"patient_id": patient, "gravida": 2, "parity": 1},
        )
    ).json()

    visit = await client.post(
        "/api/v1/mch/anc/visits",
        json={
            "anc_profile_id": profile["id"],
            "visit_date": "2026-04-10",
            "gestation_weeks": 12,
        },
    )
    assert visit.status_code == 201, visit.text

    board = (await client.get("/api/v1/queue")).json()
    mine = [t for t in board["items"] if t["patient_id"] == patient]
    assert len(mine) == 1


@pytest.mark.asyncio
async def test_a_high_risk_pregnancy_is_called_before_a_routine_one(
    client: AsyncClient,
) -> None:
    """Risk drives the ticket's priority, so red comes before green."""

    routine_patient = await _patient(client, phone="0700000001")
    await client.post(
        "/api/v1/mch/anc",
        json={"patient_id": routine_patient, "gravida": 1, "parity": 0},
    )
    high_patient = await _patient(client, phone="0700000002")
    await client.post(
        "/api/v1/mch/anc",
        json={
            "patient_id": high_patient,
            "gravida": 3,
            "parity": 2,
            "risk_level": "high",
        },
    )

    called = (await client.post("/api/v1/queue/call-next", json={})).json()

    assert called["patient_id"] == high_patient
    assert called["triage_category"] == "urgent"


@pytest.mark.asyncio
async def test_calling_a_bridged_ticket_announces_its_number(
    client: AsyncClient,
) -> None:
    """The speaker learns about the visit without anyone issuing a ticket."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)

    inbox = broadcaster.subscribe()
    try:
        response = await client.post(
            "/api/v1/queue/call-next", json={"announce": True}
        )
        assert response.status_code == 200, response.text
        called = response.json()
        event = inbox.get_nowait()
    finally:
        broadcaster.unsubscribe(inbox)

    assert event["action"] == "CALLED"
    assert called["status"] == "CALLED"
    assert called["encounter_id"] == encounter["id"]
    assert event["speech"]["text"] == build_call_text(called["ticket_number"], None)
    assert "zero" in event["speech"]["normalised"]



@pytest.mark.asyncio
async def test_calling_a_room_patient_announces_the_ticket_number(
    client: AsyncClient,
) -> None:
    """A call made from a room reaches the speaker, not just the row."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    paid = await client.post(
        f"/api/v1/encounters/{encounter['id']}/consultation-payment",
        json={"payment_method": "cash"},
    )
    assert paid.status_code == 201, paid.text
    assessed = await client.post(f"/api/v1/encounters/{encounter['id']}/assessment")
    assert assessed.status_code == 200, assessed.text
    board = (await client.get("/api/v1/queue")).json()
    ticket_number = _live_tickets(board, encounter["id"])[0]["ticket_number"]

    inbox = broadcaster.subscribe()
    try:
        response = await client.post("/api/v1/encounters/queue/call-next", json={})
        assert response.status_code == 200, response.text
        event = inbox.get_nowait()
    finally:
        broadcaster.unsubscribe(inbox)

    assert event["action"] == "CALLED"
    assert event["speech"]["text"] == build_call_text(
        ticket_number, "Consultation Room"
    )
