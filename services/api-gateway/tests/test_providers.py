"""Choosing the clinician a patient is handed to, not just the unit.

A hand-off is a referral to a person. The directory narrows by department,
then specialty, then effective availability, and the route endpoint refuses a
named receiver who cannot take the patient.
"""

import uuid
from datetime import date, datetime, time, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appointment import DoctorSchedule
from app.models.encounter import Encounter
from app.models.facility import Facility
from app.models.hr import LeaveRequest
from app.models.staff import Department, Staff
from app.services.provider_directory import _effective_work_status
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _make_department(code: str, name: str) -> uuid.UUID:
    """Insert a clinical department directly."""
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
        return department.id


@pytest.fixture
async def facility(setup_database) -> None:
    """Seed the hospital so a roster is judged in its own timezone."""
    async with session_factory() as db:
        db.add(
            Facility(
                id=FACILITY_ID,
                name="Aifya Test Hospital",
                code="AIFYA-TEST",
                facility_type="hospital",
                timezone="Africa/Nairobi",
                currency="KES",
                onboarding_status="approved",
                is_active=True,
            )
        )
        await db.commit()


async def _make_schedule(
    doctor_id: uuid.UUID,
    *,
    weekday: int | None = None,
    is_active: bool = True,
) -> None:
    """
    Insert one weekly availability slot for a clinician.

    @param doctor_id: Staff UUID the roster belongs to
    @param weekday: Weekday the slot covers, 0=Monday; defaults to today
    @param is_active: Whether the slot is switched on
    """
    day = date.today().weekday() if weekday is None else weekday
    async with session_factory() as db:
        db.add(
            DoctorSchedule(
                facility_id=FACILITY_ID,
                doctor_id=doctor_id,
                day_of_week=day,
                start_time=time(8, 0),
                end_time=time(17, 0),
                slot_duration_minutes=15,
                consultation_type="general",
                is_active=is_active,
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()


async def _make_staff(
    department_id: uuid.UUID,
    *,
    role: str = "doctor",
    specialization: str | None = None,
    work_status: str = "available",
    is_active: bool = True,
    first_name: str = "Test",
    last_name: str | None = None,
) -> uuid.UUID:
    """Insert a staff row directly and return its id."""
    async with session_factory() as db:
        suffix = uuid.uuid4().hex[:8]
        staff = Staff(
            facility_id=FACILITY_ID,
            keycloak_user_id=uuid.uuid4(),
            employee_number=f"EMP-{suffix}",
            first_name=first_name,
            last_name=last_name or f"User{suffix}",
            role=role,
            specialization=specialization,
            department_id=department_id,
            work_status=work_status,
            is_active=is_active,
            email=f"staff-{suffix}@aifya.health",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(staff)
        await db.commit()
        await db.refresh(staff)
        return staff.id


async def _make_patient(client: AsyncClient) -> str:
    """Register a patient and return their id."""
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Amina",
            "last_name": "Hassan",
            "date_of_birth": "1992-06-02",
            "gender": "female",
            "phone_number": "0722333444",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _make_encounter(client: AsyncClient, patient_id: str) -> dict:
    """Open an OPD encounter for the patient."""
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Needs a specialist review",
        },
    )
    assert response.status_code == 201
    return response.json()


def _provider_ids(response) -> set[str]:
    """The ids the directory returned."""
    return {item["id"] for item in response.json()["items"]}


@pytest.mark.asyncio
async def test_directory_narrows_by_department_then_specialty(
    client: AsyncClient,
) -> None:
    """Only clinical staff of the chosen unit, and only the chosen specialty."""
    dental = await _make_department("DEN", "Dental")
    opd = await _make_department("OPD", "General OPD")
    mary = await _make_staff(
        dental, role="dentist", specialization="Orthodontics", first_name="Mary"
    )
    peter = await _make_staff(
        dental, role="dentist", specialization="Oral Surgery", first_name="Peter"
    )
    john = await _make_staff(
        opd, role="doctor", specialization="General Medicine", first_name="John"
    )
    clerk = await _make_staff(dental, role="records", first_name="Clerk")

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    assert response.status_code == 200
    body = response.json()
    returned = _provider_ids(response)
    assert returned == {str(mary), str(peter)}
    assert str(clerk) not in returned
    assert str(john) not in returned
    assert set(body["specialties"]) == {"Orthodontics", "Oral Surgery"}

    orthodontics = await client.get(
        "/api/v1/encounters/providers",
        params={"department_id": str(dental), "specialty": "Orthodontics"},
    )
    assert _provider_ids(orthodontics) == {str(mary)}


@pytest.mark.asyncio
async def test_directory_uses_effective_availability(client: AsyncClient) -> None:
    """Leave and an open consultation override the declared work status."""
    dental = await _make_department("DEN", "Dental")
    free = await _make_staff(dental, role="dentist", first_name="Free")
    on_leave = await _make_staff(dental, role="dentist", first_name="Away")
    busy = await _make_staff(dental, role="dentist", first_name="Busy")

    async with session_factory() as db:
        db.add(
            LeaveRequest(
                facility_id=FACILITY_ID,
                staff_id=on_leave,
                leave_type="annual",
                start_date=date.today(),
                end_date=date.today(),
                days_requested=1,
                status="approved",
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        db.add(
            Encounter(
                facility_id=FACILITY_ID,
                patient_id=uuid.uuid4(),
                encounter_type="opd",
                department_id=dental,
                attending_doctor_id=busy,
                status="in_consultation",
                encounter_date=datetime.now(timezone.utc),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    statuses = {
        uuid.UUID(item["id"]): item["work_status"]
        for item in response.json()["items"]
    }
    assert statuses[free] == "available"
    assert statuses[on_leave] == "on_leave"
    assert statuses[busy] == "busy"

    available_only = await client.get(
        "/api/v1/encounters/providers",
        params={"department_id": str(dental), "available_only": "true"},
    )
    assert _provider_ids(available_only) == {str(free)}


@pytest.mark.asyncio
async def test_route_assigns_the_named_provider(client: AsyncClient) -> None:
    """The chosen clinician becomes the encounter's attending provider."""
    dental = await _make_department("DEN", "Dental")
    mary = await _make_staff(
        dental, role="dentist", specialization="Orthodontics", first_name="Mary"
    )
    patient_id = await _make_patient(client)
    encounter = await _make_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": str(dental),
            "receiving_doctor_id": str(mary),
            "urgency": "routine",
            "reason": "Orthodontic review",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["encounter"]["attending_doctor_id"] == str(mary)
    assert body["encounter"]["department_id"] == str(dental)


@pytest.mark.asyncio
async def test_route_rejects_a_provider_from_another_unit(
    client: AsyncClient,
) -> None:
    """A clinician who does not work in the destination cannot receive them."""
    dental = await _make_department("DEN", "Dental")
    opd = await _make_department("OPD", "General OPD")
    other_unit = await _make_staff(opd, role="doctor", first_name="Other")
    patient_id = await _make_patient(client)
    encounter = await _make_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": str(dental),
            "receiving_doctor_id": str(other_unit),
            "reason": "Wrong unit",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_route_rejects_an_inactive_provider(client: AsyncClient) -> None:
    """A deactivated account cannot be handed a patient."""
    dental = await _make_department("DEN", "Dental")
    inactive = await _make_staff(
        dental, role="dentist", first_name="Off", is_active=False
    )
    patient_id = await _make_patient(client)
    encounter = await _make_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/route",
        json={
            "receiving_department_id": str(dental),
            "receiving_doctor_id": str(inactive),
            "reason": "Should be refused",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_hr_sets_declared_work_status(client: AsyncClient) -> None:
    """HR can park someone off duty without deactivating their account."""
    dental = await _make_department("DEN", "Dental")
    staff = await _make_staff(dental, role="dentist", first_name="Rita")

    response = await client.patch(
        f"/api/v1/hr/staff/{staff}/work-status",
        json={"work_status": "off_duty"},
    )
    assert response.status_code == 200
    assert response.json()["work_status"] == "off_duty"
    assert response.json()["is_active"] is True

    invalid = await client.patch(
        f"/api/v1/hr/staff/{staff}/work-status",
        json={"work_status": "napping"},
    )
    assert invalid.status_code == 422

@pytest.mark.asyncio
async def test_specialty_filter_excludes_other_and_unspecialised(
    client: AsyncClient,
) -> None:
    """Asking for Orthodontics must not offer a general dentist or surgeon."""
    dental = await _make_department("DEN", "Dental")
    ortho = await _make_staff(
        dental, role="dentist", specialization="Orthodontics", first_name="Ortho"
    )
    await _make_staff(
        dental, role="dentist", specialization=None, first_name="General"
    )
    await _make_staff(
        dental, role="dentist", specialization="Oral Surgery", first_name="Surgeon"
    )

    response = await client.get(
        "/api/v1/encounters/providers",
        params={"department_id": str(dental), "specialty": "Orthodontics"},
    )
    assert response.status_code == 200
    assert _provider_ids(response) == {str(ortho)}


# ── Weekly roster ────────────────────────────────────────────────────────────


def _statuses(response) -> dict[uuid.UUID, str]:
    """The id -> effective status map the directory returned."""
    return {
        uuid.UUID(item["id"]): item["work_status"]
        for item in response.json()["items"]
    }


def test_status_precedence_is_leave_then_busy_then_roster() -> None:
    """The engine's rule, checked directly: leave > busy > roster > declared."""
    # Approved leave outranks everything else.
    assert (
        _effective_work_status(
            "available", True, True, has_schedule=True, scheduled_today=False
        )
        == "on_leave"
    )
    # An open consultation outranks an off-duty roster day.
    assert (
        _effective_work_status(
            "available", False, True, has_schedule=True, scheduled_today=False
        )
        == "busy"
    )
    # On the roster today, the declared status stands.
    assert (
        _effective_work_status(
            "available", False, False, has_schedule=True, scheduled_today=True
        )
        == "available"
    )
    # A roster in force that omits today parks the clinician off duty.
    assert (
        _effective_work_status(
            "available", False, False, has_schedule=True, scheduled_today=False
        )
        == "off_duty"
    )
    # No roster at all leaves the declared status alone.
    assert (
        _effective_work_status(
            "busy", False, False, has_schedule=False, scheduled_today=False
        )
        == "busy"
    )
    # An unusable declared value still resolves to unavailable.
    assert _effective_work_status(None, False, False) == "unavailable"


@pytest.mark.asyncio
async def test_weekly_roster_parks_today_off(
    client: AsyncClient, facility: None
) -> None:
    """A roster that omits today parks its clinician; an unset roster never does."""
    dental = await _make_department("DEN", "Dental")
    working = await _make_staff(dental, role="dentist", first_name="Today")
    resting = await _make_staff(dental, role="dentist", first_name="Rest")
    unscheduled = await _make_staff(dental, role="dentist", first_name="New")
    await _make_schedule(working)
    await _make_schedule(resting, weekday=(date.today().weekday() + 1) % 7)

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    statuses = _statuses(response)
    assert statuses[working] == "available"
    assert statuses[resting] == "off_duty"
    # No schedule on file means the declared status stands: nobody vanishes.
    assert statuses[unscheduled] == "available"

    available_only = await client.get(
        "/api/v1/encounters/providers",
        params={"department_id": str(dental), "available_only": "true"},
    )
    offered = _provider_ids(available_only)
    assert str(working) in offered
    assert str(unscheduled) in offered
    assert str(resting) not in offered


@pytest.mark.asyncio
async def test_switched_off_roster_stops_restricting(
    client: AsyncClient, facility: None
) -> None:
    """A roster row that is switched off must not park its clinician."""
    dental = await _make_department("DEN", "Dental")
    staff = await _make_staff(dental, role="dentist", first_name="Inactive")
    await _make_schedule(
        staff, weekday=(date.today().weekday() + 1) % 7, is_active=False
    )

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    assert _statuses(response)[staff] == "available"


@pytest.mark.asyncio
async def test_leave_outranks_the_roster(
    client: AsyncClient, facility: None
) -> None:
    """Approved leave today beats a roster that would otherwise have them on."""
    dental = await _make_department("DEN", "Dental")
    staff = await _make_staff(dental, role="dentist", first_name="Away")
    await _make_schedule(staff)
    async with session_factory() as db:
        db.add(
            LeaveRequest(
                facility_id=FACILITY_ID,
                staff_id=staff,
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

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    assert _statuses(response)[staff] == "on_leave"


@pytest.mark.asyncio
async def test_consultation_outranks_an_off_day(
    client: AsyncClient, facility: None
) -> None:
    """A clinician mid-consultation reads busy even off their roster day."""
    dental = await _make_department("DEN", "Dental")
    staff = await _make_staff(dental, role="dentist", first_name="Busy")
    await _make_schedule(staff, weekday=(date.today().weekday() + 1) % 7)
    async with session_factory() as db:
        db.add(
            Encounter(
                facility_id=FACILITY_ID,
                patient_id=uuid.uuid4(),
                encounter_type="opd",
                department_id=dental,
                attending_doctor_id=staff,
                status="in_consultation",
                encounter_date=datetime.now(timezone.utc),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    response = await client.get(
        "/api/v1/encounters/providers", params={"department_id": str(dental)}
    )
    assert _statuses(response)[staff] == "busy"
