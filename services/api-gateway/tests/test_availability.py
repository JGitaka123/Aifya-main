"""A clinician's own week, and HR's view of everybody's.

Self-service is resolved from the token alone, so it can only ever touch the
caller's own roster and only its days and hours. HR oversight is facility
scoped: any employee may be read and edited, an employee of another facility
may not. Both report the effective work status the patient picker would use.
"""

import uuid
from datetime import date, time

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appointment import DoctorSchedule
from app.models.hr import LeaveRequest
from app.models.staff import Staff
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _make_staff(
    *,
    staff_id: uuid.UUID | None = None,
    keycloak_user_id: uuid.UUID | None = None,
    facility_id: uuid.UUID = FACILITY_ID,
    role: str = "doctor",
    work_status: str = "available",
) -> uuid.UUID:
    """
    Insert one staff row and return its id.

    @param staff_id: Exact staff UUID, used to stand in for the test token
    @param keycloak_user_id: Keycloak identity the token would carry
    @param facility_id: Facility the staff member belongs to
    @param role: Clinical role
    @param work_status: Declared availability
    @returns The inserted staff id
    """
    async with session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        staff = Staff(
            id=staff_id or uuid.uuid4(),
            facility_id=facility_id,
            keycloak_user_id=keycloak_user_id or uuid.uuid4(),
            employee_number=f"EMP-{suffix}",
            first_name="Test",
            last_name=f"User{suffix}",
            role=role,
            work_status=work_status,
            is_active=True,
            email=f"staff-{suffix}@aifya.health",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(staff)
        await db.commit()
        await db.refresh(staff)
        return staff.id


async def _add_schedule(
    doctor_id: uuid.UUID,
    *,
    weekday: int,
    start: time = time(8, 0),
    end: time = time(17, 0),
    is_active: bool = True,
) -> uuid.UUID:
    """
    Insert one weekly session for a clinician.

    @param doctor_id: Staff UUID the session belongs to
    @param weekday: Weekday covered, 0=Monday
    @param start: Session start time
    @param end: Session end time
    @param is_active: Whether the session is switched on
    @returns The inserted schedule id
    """
    async with session_factory() as db:
        row = DoctorSchedule(
            facility_id=FACILITY_ID,
            doctor_id=doctor_id,
            day_of_week=weekday,
            start_time=start,
            end_time=end,
            slot_duration_minutes=15,
            consultation_type="general",
            is_active=is_active,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id


async def _slots_for(doctor_id: uuid.UUID) -> list[DoctorSchedule]:
    """
    Read a clinician's active sessions straight from the database.

    @param doctor_id: Staff UUID
    @returns Active, non-deleted schedule rows
    """
    async with session_factory() as db:
        rows = await db.execute(
            select(DoctorSchedule).where(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.is_deleted == False,  # noqa: E712
                DoctorSchedule.is_active == True,  # noqa: E712
            )
        )
        return list(rows.scalars().all())


@pytest.mark.asyncio
async def test_self_service_reads_own_week(client: AsyncClient) -> None:
    """The token's own staff row is found and its week returned."""
    today = date.today().weekday()
    staff = await _make_staff(staff_id=USER_ID)
    await _add_schedule(staff, weekday=today)

    response = await client.get("/api/v1/hr/me/schedule")

    assert response.status_code == 200
    body = response.json()
    assert body["staff_id"] == str(staff)
    assert len(body["slots"]) == 1
    assert body["slots"][0]["day_of_week"] == today
    assert body["slots"][0]["start_time"] == "08:00:00"
    assert body["work_status"] == "available"
    assert body["has_schedule"] is True
    assert body["scheduled_today"] is True


@pytest.mark.asyncio
async def test_self_service_resolves_keycloak_identity(
    client: AsyncClient,
) -> None:
    """A staff row linked by keycloak_user_id is the caller's own week too."""
    staff = await _make_staff(keycloak_user_id=USER_ID)

    response = await client.get("/api/v1/hr/me/schedule")

    assert response.status_code == 200
    assert response.json()["staff_id"] == str(staff)


@pytest.mark.asyncio
async def test_self_service_without_staff_record_is_404(
    client: AsyncClient,
) -> None:
    """A token with no staff row gets a clean 404, not someone else's week."""
    response = await client.get("/api/v1/hr/me/schedule")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_replace_week_drives_effective_status(client: AsyncClient) -> None:
    """Saving a week then moving off today flips availability to off duty."""
    today = date.today().weekday()
    other = (today + 1) % 7
    await _make_staff(staff_id=USER_ID)

    on_today = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": today,
                    "start_time": "08:00",
                    "end_time": "13:00",
                }
            ]
        },
    )
    assert on_today.status_code == 200
    assert on_today.json()["work_status"] == "available"
    assert on_today.json()["scheduled_today"] is True

    off_today = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": other,
                    "start_time": "08:00",
                    "end_time": "13:00",
                }
            ]
        },
    )
    assert off_today.status_code == 200
    assert off_today.json()["work_status"] == "off_duty"
    assert off_today.json()["has_schedule"] is True
    assert off_today.json()["scheduled_today"] is False

    cleared = await client.put("/api/v1/hr/me/schedule", json={"slots": []})
    assert cleared.status_code == 200
    # An empty week is "unset", which must leave the declared status standing.
    assert cleared.json()["has_schedule"] is False
    assert cleared.json()["work_status"] == "available"


@pytest.mark.asyncio
async def test_replace_week_reuses_rows_it_keeps(client: AsyncClient) -> None:
    """An unchanged session keeps its row, so a booked slot is not orphaned."""
    today = date.today().weekday()
    staff = await _make_staff(staff_id=USER_ID)
    original = await _add_schedule(staff, weekday=today, start=time(8, 0))

    response = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": today,
                    "start_time": "08:00",
                    "end_time": "17:00",
                },
                {
                    "day_of_week": (today + 1) % 7,
                    "start_time": "09:00",
                    "end_time": "12:00",
                },
            ]
        },
    )

    assert response.status_code == 200
    rows = await _slots_for(staff)
    assert {row.id for row in rows} >= {original}
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_self_service_rejects_bad_slots(client: AsyncClient) -> None:
    """Order, range and duplicates are refused before anything is written."""
    await _make_staff(staff_id=USER_ID)

    backwards = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "start_time": "17:00",
                    "end_time": "08:00",
                }
            ]
        },
    )
    assert backwards.status_code == 422

    out_of_range = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": 9,
                    "start_time": "08:00",
                    "end_time": "12:00",
                }
            ]
        },
    )
    assert out_of_range.status_code == 422

    duplicate = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "start_time": "08:00",
                    "end_time": "12:00",
                },
                {
                    "day_of_week": 0,
                    "start_time": "08:00",
                    "end_time": "12:00",
                },
            ]
        },
    )
    assert duplicate.status_code == 422


@pytest.mark.asyncio
async def test_self_service_cannot_target_another_staff(
    client: AsyncClient,
) -> None:
    """A crafted staff_id in the body does not redirect the write."""
    today = date.today().weekday()
    mine = await _make_staff(staff_id=USER_ID)
    other = await _make_staff()

    response = await client.put(
        "/api/v1/hr/me/schedule",
        json={
            "staff_id": str(other),
            "doctor_id": str(other),
            "slots": [
                {
                    "day_of_week": today,
                    "start_time": "08:00",
                    "end_time": "13:00",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["staff_id"] == str(mine)
    assert len(await _slots_for(mine)) == 1
    assert await _slots_for(other) == []


@pytest.mark.asyncio
async def test_hr_reads_and_edits_any_employee(client: AsyncClient) -> None:
    """HR may read and rewrite a colleague's week, not only their own."""
    today = date.today().weekday()
    employee = await _make_staff()

    empty = await client.get(f"/api/v1/hr/staff/{employee}/schedule")
    assert empty.status_code == 200
    assert empty.json()["slots"] == []

    saved = await client.put(
        f"/api/v1/hr/staff/{employee}/schedule",
        json={
            "slots": [
                {
                    "day_of_week": today,
                    "start_time": "08:00",
                    "end_time": "16:00",
                }
            ]
        },
    )
    assert saved.status_code == 200
    assert saved.json()["work_status"] == "available"
    assert saved.json()["scheduled_today"] is True

    reread = await client.get(f"/api/v1/hr/staff/{employee}/schedule")
    assert len(reread.json()["slots"]) == 1


@pytest.mark.asyncio
async def test_hr_schedule_is_facility_scoped(client: AsyncClient) -> None:
    """A staff member of another facility is not reachable by id."""
    employee = await _make_staff(facility_id=uuid.uuid4())

    read = await client.get(f"/api/v1/hr/staff/{employee}/schedule")
    assert read.status_code == 404

    write = await client.put(
        f"/api/v1/hr/staff/{employee}/schedule",
        json={
            "slots": [
                {
                    "day_of_week": 0,
                    "start_time": "08:00",
                    "end_time": "12:00",
                }
            ]
        },
    )
    assert write.status_code == 404


@pytest.mark.asyncio
async def test_effective_status_shows_leave_on_the_badge(
    client: AsyncClient,
) -> None:
    """Approved leave outranks an otherwise working week on the HR panel."""
    today = date.today().weekday()
    employee = await _make_staff()
    await _add_schedule(employee, weekday=today)
    async with session_factory() as db:
        db.add(
            LeaveRequest(
                facility_id=FACILITY_ID,
                staff_id=employee,
                leave_type="annual",
                start_date=date.today(),
                end_date=date.today(),
                days_requested=1,
                status="approved",
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    response = await client.get(f"/api/v1/hr/staff/{employee}/schedule")

    assert response.status_code == 200
    assert response.json()["work_status"] == "on_leave"