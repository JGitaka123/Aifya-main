"""Comprehensive tests for the HR module endpoints.

Tests cover: summary, staff directory, shifts, shift assignments,
leave requests, leave processing, attendance clock-in/out, and attendance listing.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.staff import Staff
from tests.conftest import FACILITY_ID, USER_ID
from tests.conftest import session_factory as _session_factory


@pytest_asyncio.fixture(autouse=True)
async def seed_staff_profile(setup_database: None) -> None:
    """Seed a Staff row linked to the test user's Keycloak ID.

    Attendance, leave, and shift-assignment rows reference staff.id, and
    the API resolves the JWT user to a staff profile — without this row
    those endpoints correctly return 404.

    @param setup_database: Ensures tables are reset before seeding
    """
    async with _session_factory() as session:
        session.add(
            Staff(
                id=USER_ID,
                facility_id=FACILITY_ID,
                keycloak_user_id=USER_ID,
                employee_number="EMP-0001",
                first_name="Test",
                last_name="User",
                role="doctor",
                email="test@aifya.health",
            )
        )
        await session.commit()


# ── Summary ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_hr_summary(client: AsyncClient) -> None:
    """GET /api/v1/hr/summary returns HR dashboard summary with expected fields."""
    response = await client.get("/api/v1/hr/summary")

    assert response.status_code == 200
    data = response.json()
    assert "total_staff" in data
    assert "active_staff" in data
    assert "doctors" in data
    assert "nurses" in data
    assert "on_duty_today" in data
    assert "on_leave_today" in data
    assert "pending_leave_requests" in data
    assert "expiring_contracts" in data
    # Fresh DB should have zero counts
    # One staff row is seeded by the module fixture (the test user).
    assert data["total_staff"] == 1
    assert data["active_staff"] == 1
    assert data["pending_leave_requests"] == 0


# ── Staff Directory ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_staff_directory_empty(client: AsyncClient) -> None:
    """GET /api/v1/hr/staff returns only the seeded test user."""
    response = await client.get("/api/v1/hr/staff")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["employee_number"] == "EMP-0001"


@pytest.mark.asyncio
async def test_get_staff_directory_with_role_filter(client: AsyncClient) -> None:
    """GET /api/v1/hr/staff?role=doctor returns the seeded doctor only."""
    response = await client.get("/api/v1/hr/staff", params={"role": "doctor"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["role"] == "doctor"

    nurses = await client.get("/api/v1/hr/staff", params={"role": "nurse"})
    assert nurses.status_code == 200
    assert nurses.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_staff_directory_with_search_filter(client: AsyncClient) -> None:
    """GET /api/v1/hr/staff?search=Wanjiku returns empty list when no staff exist."""
    response = await client.get("/api/v1/hr/staff", params={"search": "Wanjiku"})

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── Shifts ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_shifts_empty(client: AsyncClient) -> None:
    """GET /api/v1/hr/shifts returns empty list on fresh database."""
    response = await client.get("/api/v1/hr/shifts")

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_shift(client: AsyncClient) -> None:
    """POST /api/v1/hr/shifts creates a shift definition and returns 201."""
    payload = {
        "code": "MORN",
        "name": "Morning Shift",
        "start_time": "06:00:00",
        "end_time": "14:00:00",
        "duration_hours": 8,
        "is_night_shift": False,
    }
    response = await client.post("/api/v1/hr/shifts", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Morning Shift"
    assert data["code"] == "MORN"
    assert data["start_time"] == "06:00:00"
    assert data["end_time"] == "14:00:00"
    assert data["duration_hours"] == 8
    assert data["is_night_shift"] is False
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_shift_night(client: AsyncClient) -> None:
    """POST /api/v1/hr/shifts creates a night shift successfully."""
    payload = {
        "code": "NIGHT",
        "name": "Night Shift",
        "start_time": "22:00:00",
        "end_time": "06:00:00",
        "duration_hours": 8,
        "is_night_shift": True,
        "notes": "Night duty rotation",
    }
    response = await client.post("/api/v1/hr/shifts", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Night Shift"
    assert data["is_night_shift"] is True
    assert data["notes"] == "Night duty rotation"


@pytest.mark.asyncio
async def test_create_shift_missing_required_fields(client: AsyncClient) -> None:
    """POST /api/v1/hr/shifts rejects payload missing required fields."""
    payload = {"name": "Incomplete Shift"}
    response = await client.post("/api/v1/hr/shifts", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_shift_invalid_duration(client: AsyncClient) -> None:
    """POST /api/v1/hr/shifts rejects invalid duration_hours value."""
    payload = {
        "code": "BAD",
        "name": "Bad Shift",
        "start_time": "06:00:00",
        "end_time": "14:00:00",
        "duration_hours": 0,  # must be >= 1
    }
    response = await client.post("/api/v1/hr/shifts", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_shifts_after_creation(client: AsyncClient) -> None:
    """GET /api/v1/hr/shifts returns created shifts."""
    payload = {
        "code": "AFT",
        "name": "Afternoon Shift",
        "start_time": "14:00:00",
        "end_time": "22:00:00",
        "duration_hours": 8,
    }
    create_response = await client.post("/api/v1/hr/shifts", json=payload)
    assert create_response.status_code == 201

    response = await client.get("/api/v1/hr/shifts")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [s["name"] for s in data]
    assert "Afternoon Shift" in names


# ── Shift Assignments ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_shift_assignment(client: AsyncClient) -> None:
    """POST /api/v1/hr/shift-assignments assigns a staff member to a shift."""
    # First create a shift
    shift_payload = {
        "code": "MORN",
        "name": "Morning Shift",
        "start_time": "06:00:00",
        "end_time": "14:00:00",
        "duration_hours": 8,
    }
    shift_response = await client.post("/api/v1/hr/shifts", json=shift_payload)
    assert shift_response.status_code == 201
    shift_id: str = shift_response.json()["id"]

    staff_id = "00000000-0000-0000-0000-000000000002"

    assignment_payload = {
        "staff_id": staff_id,
        "shift_id": shift_id,
        "assignment_date": "2026-05-01",
    }
    response = await client.post("/api/v1/hr/shift-assignments", json=assignment_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["staff_id"] == staff_id
    assert data["shift_id"] == shift_id
    assert data["assignment_date"] == "2026-05-01"
    assert data["status"] in ("assigned", "scheduled")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_shift_assignment_with_notes(client: AsyncClient) -> None:
    """POST /api/v1/hr/shift-assignments accepts optional notes."""
    shift_payload = {
        "code": "EVE",
        "name": "Evening Shift",
        "start_time": "14:00:00",
        "end_time": "22:00:00",
        "duration_hours": 8,
    }
    shift_response = await client.post("/api/v1/hr/shifts", json=shift_payload)
    assert shift_response.status_code == 201
    shift_id: str = shift_response.json()["id"]

    staff_id = "00000000-0000-0000-0000-000000000002"

    assignment_payload = {
        "staff_id": staff_id,
        "shift_id": shift_id,
        "assignment_date": "2026-05-02",
        "notes": "Covering for Dr. Ochieng",
    }
    response = await client.post("/api/v1/hr/shift-assignments", json=assignment_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["notes"] == "Covering for Dr. Ochieng"


@pytest.mark.asyncio
async def test_list_shift_assignments_empty(client: AsyncClient) -> None:
    """GET /api/v1/hr/shift-assignments returns empty list on fresh database."""
    response = await client.get("/api/v1/hr/shift-assignments")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_shift_assignments_after_creation(client: AsyncClient) -> None:
    """GET /api/v1/hr/shift-assignments returns created assignments."""
    # Create shift
    shift_payload = {
        "code": "MORN",
        "name": "Morning Shift",
        "start_time": "06:00:00",
        "end_time": "14:00:00",
        "duration_hours": 8,
    }
    shift_response = await client.post("/api/v1/hr/shifts", json=shift_payload)
    assert shift_response.status_code == 201
    shift_id: str = shift_response.json()["id"]

    staff_id = "00000000-0000-0000-0000-000000000002"

    # Create assignment
    assignment_payload = {
        "staff_id": staff_id,
        "shift_id": shift_id,
        "assignment_date": "2026-05-01",
    }
    create_response = await client.post("/api/v1/hr/shift-assignments", json=assignment_payload)
    assert create_response.status_code == 201

    # List
    response = await client.get("/api/v1/hr/shift-assignments")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_shift_assignments_filter_by_date(client: AsyncClient) -> None:
    """GET /api/v1/hr/shift-assignments?date=... filters by assignment date."""
    response = await client.get(
        "/api/v1/hr/shift-assignments",
        params={"date": "2026-05-01"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_shift_assignment_missing_fields(client: AsyncClient) -> None:
    """POST /api/v1/hr/shift-assignments rejects incomplete payload."""
    payload = {"staff_id": str(uuid.uuid4())}
    response = await client.post("/api/v1/hr/shift-assignments", json=payload)

    assert response.status_code == 422


# ── Leave Requests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_leave_requests_empty(client: AsyncClient) -> None:
    """GET /api/v1/hr/leave returns empty list on fresh database."""
    response = await client.get("/api/v1/hr/leave")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_leave_request(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave creates a leave request and returns 201."""
    payload = {
        "leave_type": "annual",
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "days_requested": 5,
        "reason": "Family vacation",
    }
    response = await client.post("/api/v1/hr/leave", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["leave_type"] == "annual"
    assert data["start_date"] == "2026-06-01"
    assert data["end_date"] == "2026-06-05"
    assert data["days_requested"] == 5
    assert data["reason"] == "Family vacation"
    assert data["status"] == "pending"
    assert data["approved_by"] is None
    assert data["approved_at"] is None
    assert data["rejection_reason"] is None
    assert "id" in data
    assert "staff_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_leave_request_sick(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave creates a sick leave request."""
    payload = {
        "leave_type": "sick",
        "start_date": "2026-07-10",
        "end_date": "2026-07-12",
        "days_requested": 3,
        "reason": "Flu symptoms",
    }
    response = await client.post("/api/v1/hr/leave", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["leave_type"] == "sick"
    assert data["days_requested"] == 3


@pytest.mark.asyncio
async def test_create_leave_request_with_handover(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave accepts handover details."""
    handover_staff_id = str(uuid.uuid4())
    payload = {
        "leave_type": "annual",
        "start_date": "2026-08-01",
        "end_date": "2026-08-10",
        "days_requested": 10,
        "reason": "Extended holiday",
        "handover_to": handover_staff_id,
        "handover_notes": "Please cover ward rounds",
    }
    response = await client.post("/api/v1/hr/leave", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["handover_to"] == handover_staff_id
    assert data["handover_notes"] == "Please cover ward rounds"


@pytest.mark.asyncio
async def test_create_leave_request_invalid_type(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave rejects invalid leave type."""
    payload = {
        "leave_type": "holiday",
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "days_requested": 5,
    }
    response = await client.post("/api/v1/hr/leave", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_leave_request_missing_fields(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave rejects payload missing required fields."""
    payload = {"leave_type": "annual"}
    response = await client.post("/api/v1/hr/leave", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_leave_requests_after_creation(client: AsyncClient) -> None:
    """GET /api/v1/hr/leave returns created leave requests."""
    payload = {
        "leave_type": "annual",
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "days_requested": 5,
        "reason": "Family vacation",
    }
    create_response = await client.post("/api/v1/hr/leave", json=payload)
    assert create_response.status_code == 201

    response = await client.get("/api/v1/hr/leave")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_leave_requests_filter_by_status(client: AsyncClient) -> None:
    """GET /api/v1/hr/leave?status=pending filters by leave status."""
    response = await client.get("/api/v1/hr/leave", params={"status": "pending"})

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


# ── Leave Processing ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_leave_request(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave/{id}/process approves a pending leave request."""
    # Create a leave request
    leave_payload = {
        "leave_type": "annual",
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "days_requested": 5,
        "reason": "Family vacation",
    }
    create_response = await client.post("/api/v1/hr/leave", json=leave_payload)
    assert create_response.status_code == 201
    leave_id: str = create_response.json()["id"]

    # Approve it
    approval_payload = {"action": "approve"}
    response = await client.post(
        f"/api/v1/hr/leave/{leave_id}/process",
        json=approval_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == leave_id
    assert data["status"] == "approved"
    assert data["approved_by"] is not None
    assert data["approved_at"] is not None


@pytest.mark.asyncio
async def test_reject_leave_request(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave/{id}/process rejects a pending leave request."""
    # Create a leave request
    leave_payload = {
        "leave_type": "annual",
        "start_date": "2026-09-01",
        "end_date": "2026-09-10",
        "days_requested": 10,
        "reason": "Travel plans",
    }
    create_response = await client.post("/api/v1/hr/leave", json=leave_payload)
    assert create_response.status_code == 201
    leave_id: str = create_response.json()["id"]

    # Reject it
    rejection_payload = {
        "action": "reject",
        "rejection_reason": "Staffing shortages during that period",
    }
    response = await client.post(
        f"/api/v1/hr/leave/{leave_id}/process",
        json=rejection_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == leave_id
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Staffing shortages during that period"


@pytest.mark.asyncio
async def test_process_leave_invalid_action(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave/{id}/process rejects invalid action value."""
    leave_payload = {
        "leave_type": "annual",
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
        "days_requested": 5,
    }
    create_response = await client.post("/api/v1/hr/leave", json=leave_payload)
    assert create_response.status_code == 201
    leave_id: str = create_response.json()["id"]

    response = await client.post(
        f"/api/v1/hr/leave/{leave_id}/process",
        json={"action": "cancel"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_leave_not_found(client: AsyncClient) -> None:
    """POST /api/v1/hr/leave/{id}/process returns 404 for nonexistent leave."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/hr/leave/{fake_id}/process",
        json={"action": "approve"},
    )

    assert response.status_code == 404


# ── Attendance: Clock In ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clock_in(client: AsyncClient) -> None:
    """POST /api/v1/hr/attendance/clock-in records a clock-in and returns 201."""
    payload: dict[str, str | None] = {}
    response = await client.post("/api/v1/hr/attendance/clock-in", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["staff_id"] == "00000000-0000-0000-0000-000000000002"
    assert data["clock_in"] is not None
    assert data["clock_out"] is None
    assert data["status"] in ("present", "clocked_in")
    assert "attendance_date" in data


@pytest.mark.asyncio
async def test_clock_in_with_shift(client: AsyncClient) -> None:
    """POST /api/v1/hr/attendance/clock-in accepts optional shift_id."""
    # Create a shift first
    shift_payload = {
        "code": "MORN",
        "name": "Morning Shift",
        "start_time": "06:00:00",
        "end_time": "14:00:00",
        "duration_hours": 8,
    }
    shift_response = await client.post("/api/v1/hr/shifts", json=shift_payload)
    assert shift_response.status_code == 201
    shift_id: str = shift_response.json()["id"]

    payload = {"shift_id": shift_id}
    response = await client.post("/api/v1/hr/attendance/clock-in", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["shift_id"] == shift_id


@pytest.mark.asyncio
async def test_clock_in_with_notes(client: AsyncClient) -> None:
    """POST /api/v1/hr/attendance/clock-in accepts optional notes."""
    payload = {"notes": "Arrived early for handover"}
    response = await client.post("/api/v1/hr/attendance/clock-in", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["notes"] == "Arrived early for handover"


# ── Attendance: Clock Out ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clock_out(client: AsyncClient) -> None:
    """POST /api/v1/hr/attendance/{id}/clock-out records a clock-out."""
    # Clock in first
    clock_in_response = await client.post(
        "/api/v1/hr/attendance/clock-in",
        json={},
    )
    assert clock_in_response.status_code == 201
    attendance_id: str = clock_in_response.json()["id"]

    # Clock out
    payload = {"notes": "End of shift"}
    response = await client.post(
        f"/api/v1/hr/attendance/{attendance_id}/clock-out",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == attendance_id
    assert data["clock_out"] is not None
    assert data["notes"] == "End of shift"


@pytest.mark.asyncio
async def test_clock_out_not_found(client: AsyncClient) -> None:
    """POST /api/v1/hr/attendance/{id}/clock-out returns 404 for nonexistent record."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/hr/attendance/{fake_id}/clock-out",
        json={},
    )

    assert response.status_code == 404


# ── Attendance: List ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_attendance_empty(client: AsyncClient) -> None:
    """GET /api/v1/hr/attendance returns empty list on fresh database."""
    response = await client.get("/api/v1/hr/attendance")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_attendance_after_clock_in(client: AsyncClient) -> None:
    """GET /api/v1/hr/attendance returns records after clock-in."""
    # Clock in
    clock_in_response = await client.post(
        "/api/v1/hr/attendance/clock-in",
        json={},
    )
    assert clock_in_response.status_code == 201

    # List
    response = await client.get("/api/v1/hr/attendance")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    record = data["items"][0]
    assert record["staff_id"] == "00000000-0000-0000-0000-000000000002"
    assert record["clock_in"] is not None


@pytest.mark.asyncio
async def test_list_attendance_filter_by_date(client: AsyncClient) -> None:
    """GET /api/v1/hr/attendance?date=... filters by attendance date."""
    response = await client.get(
        "/api/v1/hr/attendance",
        params={"date": "2026-05-01"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_attendance_filter_by_staff(client: AsyncClient) -> None:
    """GET /api/v1/hr/attendance?staff_id=... filters by staff member."""
    staff_id = "00000000-0000-0000-0000-000000000002"
    response = await client.get(
        "/api/v1/hr/attendance",
        params={"staff_id": staff_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
