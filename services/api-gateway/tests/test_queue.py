"""Queue management and patient calling.

These tests use the same SQLite schema fixture as the rest of the suite, so
the row locks that make CALL NEXT safe on Postgres are no-ops here. The
concurrency guarantee is therefore asserted at the level the database can
still prove in SQLite - two callers never receive the same ticket - and the
locking clause itself is covered by the migration and service docstrings.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.config import settings

QUEUE = "/api/v1/queue"


@pytest.fixture
async def patient_id(client: AsyncClient) -> str:
    """Create a patient to queue."""

    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Agnes",
            "last_name": "Wanjiru",
            "date_of_birth": "1988-07-22",
            "gender": "female",
            "phone_number": "0711222333",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
async def service_point_id(client: AsyncClient) -> str:
    """Create the room patients are called into."""

    response = await client.post(
        f"{QUEUE}/service-points",
        json={"name": "Consultation Room 2", "kind": "room"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _issue(client: AsyncClient, patient_id: str, **overrides) -> dict:
    payload = {"patient_id": patient_id}
    payload.update(overrides)
    response = await client.post(f"{QUEUE}/tickets", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_issue_ticket_appears_on_the_board(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)

    assert ticket["status"] == "WAITING"
    assert ticket["ticket_number"]
    assert ticket["priority"] == 0

    board = (await client.get(QUEUE)).json()
    assert board["waiting"] == 1
    assert [item["id"] for item in board["items"]] == [ticket["id"]]


@pytest.mark.asyncio
async def test_ticket_numbers_are_unique_and_sequential(client: AsyncClient, patient_id: str) -> None:
    first = await _issue(client, patient_id)
    second = await _issue(client, patient_id)

    assert first["ticket_number"] != second["ticket_number"]
    assert first["ticket_number"].endswith("001")
    assert second["ticket_number"].endswith("002")


@pytest.mark.asyncio
async def test_call_next_takes_priority_over_arrival_order(client: AsyncClient, patient_id: str) -> None:
    routine = await _issue(client, patient_id, priority=0)
    urgent = await _issue(client, patient_id, priority=5)

    called = (await client.post(f"{QUEUE}/call-next", json={})).json()
    assert called["id"] == urgent["id"]
    assert called["status"] == "CALLED"

    # The routine patient is still waiting, and no longer first in line.
    board = (await client.get(QUEUE)).json()
    waiting = [item for item in board["items"] if item["status"] == "WAITING"]
    assert [item["id"] for item in waiting] == [routine["id"]]
    assert board["waiting"] == 1


@pytest.mark.asyncio
async def test_call_next_refuses_when_nobody_is_waiting(client: AsyncClient) -> None:
    response = await client.post(f"{QUEUE}/call-next", json={})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_two_call_next_calls_claim_different_patients(
    client: AsyncClient, patient_id: str
) -> None:
    await _issue(client, patient_id)
    await _issue(client, patient_id)

    first = (await client.post(f"{QUEUE}/call-next", json={})).json()
    second = (await client.post(f"{QUEUE}/call-next", json={})).json()

    assert first["id"] != second["id"]
    assert first["status"] == "CALLED"
    assert second["status"] == "CALLED"


@pytest.mark.asyncio
async def test_full_lifecycle_call_start_complete(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)

    called = (
        await client.post(f"{QUEUE}/tickets/{ticket['id']}/call", json={})
    ).json()
    assert called["status"] == "CALLED"

    started = (
        await client.post(f"{QUEUE}/tickets/{ticket['id']}/start", json={})
    ).json()
    assert started["status"] == "IN_SERVICE"

    completed = (await client.post(f"{QUEUE}/tickets/{ticket['id']}/complete")).json()
    assert completed["status"] == "COMPLETED"
    assert completed["completed_at"] is not None


@pytest.mark.asyncio
async def test_illegal_transition_is_a_conflict(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)

    # A ticket that was never called cannot be completed.
    response = await client.post(f"{QUEUE}/tickets/{ticket['id']}/complete")
    assert response.status_code == 409

    # And nothing moved.
    board = (await client.get(QUEUE)).json()
    assert board["items"][0]["status"] == "WAITING"


@pytest.mark.asyncio
async def test_recall_keeps_the_ticket_called_and_counts(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)
    await client.post(f"{QUEUE}/tickets/{ticket['id']}/call", json={})

    recalled = (
        await client.post(f"{QUEUE}/tickets/{ticket['id']}/recall")
    ).json()
    assert recalled["status"] == "CALLED"
    assert recalled["recall_count"] == 1


@pytest.mark.asyncio
async def test_history_records_every_transition(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)
    await client.post(f"{QUEUE}/tickets/{ticket['id']}/call", json={})
    await client.post(f"{QUEUE}/tickets/{ticket['id']}/start", json={})

    events = (await client.get(f"{QUEUE}/tickets/{ticket['id']}/events")).json()
    assert [event["event_type"] for event in events] == [
        "TICKET_CREATED",
        "CALLED",
        "SERVICE_STARTED",
    ]
    assert events[0]["from_status"] is None
    assert events[0]["to_status"] == "WAITING"
    assert events[-1]["to_status"] == "IN_SERVICE"


@pytest.mark.asyncio
async def test_priority_change_reorders_the_queue(client: AsyncClient, patient_id: str) -> None:
    first = await _issue(client, patient_id)
    second = await _issue(client, patient_id)

    await client.post(
        f"{QUEUE}/tickets/{second['id']}/priority", json={"priority": 9}
    )
    board = (await client.get(QUEUE)).json()
    assert board["items"][0]["id"] == second["id"]

    called = (await client.post(f"{QUEUE}/call-next", json={})).json()
    assert called["id"] == second["id"]
    assert first["id"] != called["id"]


@pytest.mark.asyncio
async def test_transfer_issues_a_new_ticket(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)
    target_department = str(uuid.uuid4())

    transferred = (
        await client.post(
            f"{QUEUE}/tickets/{ticket['id']}/transfer",
            json={"department_id": target_department, "reason": "needs ultrasound"},
        )
    ).json()

    assert transferred["id"] != ticket["id"]
    assert transferred["status"] == "WAITING"
    assert transferred["department_id"] == target_department

    old = (await client.get(f"{QUEUE}/tickets/{ticket['id']}/events")).json()
    assert old[-1]["event_type"] == "TRANSFERRED"


@pytest.mark.asyncio
async def test_unknown_ticket_is_not_found(client: AsyncClient) -> None:
    response = await client.post(f"{QUEUE}/tickets/{uuid.uuid4()}/complete")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stats_count_the_board(client: AsyncClient, patient_id: str) -> None:
    await _issue(client, patient_id)
    ticket = await _issue(client, patient_id)
    await client.post(f"{QUEUE}/tickets/{ticket['id']}/call", json={})

    stats = (await client.get(f"{QUEUE}/stats")).json()
    assert stats["waiting"] == 1
    assert stats["called"] == 1
    assert stats["in_service"] == 0
    assert stats["average_wait_minutes"] is not None


@pytest.mark.asyncio
async def test_public_board_needs_a_token(client: AsyncClient, patient_id: str) -> None:
    await _issue(client, patient_id)

    unconfigured = await client.get(f"{QUEUE}/public/board", params={"token": "x"})
    assert unconfigured.status_code == 503

    settings.queue_display_token = "wall-token"
    settings.queue_display_facility_id = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
    try:
        rejected = await client.get(f"{QUEUE}/public/board", params={"token": "wrong"})
        assert rejected.status_code == 401

        board = await client.get(f"{QUEUE}/public/board", params={"token": "wall-token"})
        assert board.status_code == 200
        row = board.json()["items"][0]
        # A wall in a corridor shows a number, never a person.
        assert row["ticket_number"]
        assert "patient_name" not in row
        assert "patient_id" not in row
    finally:
        settings.queue_display_token = ""
        settings.queue_display_facility_id = ""


@pytest.mark.asyncio
async def test_voice_is_off_by_default(client: AsyncClient, patient_id: str) -> None:
    ticket = await _issue(client, patient_id)

    settings.voice_enabled = False
    settings.tts_api_key = ""

    described = (await client.get(f"/api/v1/voice/announcements/{ticket['id']}")).json()
    assert described["voice_enabled"] is False
    assert described["audio_url"] is None
    assert "proceed" in described["text"]

    audio = await client.get(f"/api/v1/voice/announcements/{ticket['id']}/audio")
    assert audio.status_code == 503


@pytest.mark.asyncio
async def test_announcement_text_is_normalised(client: AsyncClient, patient_id: str, service_point_id: str) -> None:
    ticket = await _issue(client, patient_id, service_point_id=service_point_id)

    described = (await client.get(f"/api/v1/voice/announcements/{ticket['id']}")).json()
    assert "Consultation Room 2" in described["text"]
    # The spoken form spells the number rather than reading it as a quantity.
    assert "zero" in described["normalized_text"]
