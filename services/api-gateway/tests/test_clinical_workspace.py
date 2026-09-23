"""The clinical workspace: what one clinician has to do today.

Reception routes a patient to a department (and sometimes to a named
clinician). The worklist is the clinician's answer to "which patients are
mine?", scoped by their staff record rather than by handing every clinician the
whole hospital.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.staff import Staff
from app.services.clinical_workspace import (
    SCOPE_DEPARTMENT,
    SCOPE_FACILITY,
    SCOPE_MINE,
    default_scope,
    is_facility_wide,
    scope_filter,
)
from tests.conftest import FACILITY_ID, USER_ID, session_factory


# ── Scope resolution ────────────────────────────────────────────────────────


def test_clinician_defaults_to_their_own_patients() -> None:
    """A doctor opens their own list, not the whole hospital."""
    assert default_scope(["doctor"]) == SCOPE_MINE
    assert default_scope(["nurse"]) == SCOPE_MINE


def test_administrator_defaults_to_the_whole_facility() -> None:
    """An administrator has no patients of their own, so they see the day."""
    assert default_scope(["admin"]) == SCOPE_FACILITY
    assert default_scope(["facility_admin"]) == SCOPE_FACILITY


def test_only_administrators_are_facility_wide() -> None:
    """Widening to the facility is an administrative action."""
    assert is_facility_wide(["admin"]) is True
    assert is_facility_wide(["facility_admin", "doctor"]) is True
    assert is_facility_wide(["doctor", "nurse"]) is False


def test_my_scope_covers_assigned_and_unclaimed_work() -> None:
    """Mine is what is already assigned, plus what nobody has claimed."""
    sql = str(scope_filter(SCOPE_MINE, staff_id=USER_ID, department_id=None))
    assert "attending_doctor_id" in sql
    assert "IS NULL" in sql


def test_my_scope_narrows_unclaimed_work_to_my_department() -> None:
    """A clinician with a unit sees the unclaimed patients routed to it."""
    department_id = uuid.uuid4()
    sql = str(
        scope_filter(
            SCOPE_MINE, staff_id=USER_ID, department_id=department_id
        )
    )
    assert "department_id" in sql


def test_department_scope_ignores_who_is_assigned() -> None:
    """The departmental view is the unit's work, whoever holds it."""
    sql = str(
        scope_filter(
            SCOPE_DEPARTMENT, staff_id=USER_ID, department_id=uuid.uuid4()
        )
    )
    assert "department_id" in sql
    assert "attending_doctor_id" not in sql


def test_facility_scope_is_unfiltered() -> None:
    """The administrator's view is the whole facility."""
    sql = str(scope_filter(SCOPE_FACILITY, staff_id=None, department_id=None))
    assert sql.strip().lower() == "true"


def test_scope_without_a_staff_record_reaches_nothing() -> None:
    """An account with no staff row has no work to be assigned."""
    sql = str(scope_filter(SCOPE_MINE, staff_id=None, department_id=None))
    assert sql.strip().lower() == "false"


# ── The worklist endpoint ───────────────────────────────────────────────────


async def _patient(client: AsyncClient) -> str:
    """
    Create a test patient.

    @param client: Async HTTP test client
    @returns Patient UUID
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Worklist",
            "last_name": "Patient",
            "date_of_birth": "1988-04-11",
            "gender": "male",
            "phone_number": "0733444555",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _encounter(
    client: AsyncClient, patient_id: str, **extra: object
) -> dict:
    """
    Route a patient to a department (and optionally to a clinician).

    @param client: Async HTTP test client
    @param patient_id: Patient UUID
    @param extra: Routing fields such as department_id or attending_doctor_id
    @returns Created encounter
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Severe tooth pain",
            **extra,
        },
    )
    assert response.status_code == 201
    return response.json()


async def _register_clinician(
    department_id: uuid.UUID | None = None,
) -> None:
    """
    Give the signed-in test user a staff record.

    The workspace reads the clinician's profession, speciality and unit from
    `staff`, so a token subject alone is not a clinician yet.

    @param department_id: Department to attach the clinician to
    """
    async with session_factory() as db:
        db.add(
            Staff(
                id=USER_ID,
                facility_id=FACILITY_ID,
                keycloak_user_id=uuid.uuid4(),
                employee_number="EMP-WORKLIST-1",
                first_name="Alice",
                last_name="Mwangi",
                role="doctor",
                department_id=department_id,
                is_active=True,
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_worklist_lists_the_patient_reception_routed(client: AsyncClient) -> None:
    """A routed patient shows up on the clinician's list with their reason."""
    encounter = await _encounter(client, await _patient(client))

    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["waiting"] == 1
    assert body["counts"]["total"] == 1

    item = next(i for i in body["items"] if i["id"] == encounter["id"])
    assert item["patient_name"] == "Worklist Patient"
    assert item["chief_complaint"] == "Severe tooth pain"
    assert item["status"] == "waiting"


@pytest.mark.asyncio
async def test_status_filter_narrows_the_list_not_the_counts(client: AsyncClient) -> None:
    """Filtering to `waiting` still shows the work already completed today."""
    encounter = await _encounter(client, await _patient(client))
    completed = await client.patch(
        f"/api/v1/encounters/{encounter['id']}", json={"status": "completed"}
    )
    assert completed.status_code == 200
    await _encounter(client, await _patient(client))

    filtered = await client.get("/api/v1/encounters/worklist?status=completed")

    assert filtered.status_code == 200
    body = filtered.json()
    assert [i["id"] for i in body["items"]] == [encounter["id"]]
    assert body["counts"]["completed"] == 1
    assert body["counts"]["waiting"] == 1
    assert body["counts"]["total"] == 2


@pytest.mark.asyncio
async def test_my_scope_is_the_clinicians_own_work(client: AsyncClient) -> None:
    """Mine holds the patients routed to me and the ones nobody has claimed."""
    department_id = uuid.uuid4()
    await _register_clinician(department_id)
    mine = await _encounter(
        client, await _patient(client), attending_doctor_id=str(USER_ID)
    )
    await _encounter(
        client, await _patient(client), department_id=str(department_id)
    )
    # A colleague's patient, in a different unit, must not appear.
    await _encounter(
        client,
        await _patient(client),
        attending_doctor_id=str(uuid.uuid4()),
        department_id=str(uuid.uuid4()),
    )

    response = await client.get("/api/v1/encounters/worklist?scope=mine")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == SCOPE_MINE
    ids = {i["id"] for i in body["items"]}
    assert mine["id"] in ids
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_department_scope_returns_the_whole_unit(client: AsyncClient) -> None:
    """The departmental view is every patient routed to the unit today."""
    department_id = uuid.uuid4()
    await _register_clinician(department_id)
    colleague = await _encounter(
        client,
        await _patient(client),
        attending_doctor_id=str(uuid.uuid4()),
        department_id=str(department_id),
    )
    await _encounter(client, await _patient(client))

    response = await client.get("/api/v1/encounters/worklist?scope=department")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == SCOPE_DEPARTMENT
    assert body["clinician"]["department_name"] is None
    assert [i["id"] for i in body["items"]] == [colleague["id"]]


@pytest.mark.asyncio
async def test_department_scope_falls_back_when_the_account_has_no_unit(
    client: AsyncClient,
) -> None:
    """Asking for a department this account has none of narrows to own work."""
    await _register_clinician(None)
    encounter = await _encounter(
        client, await _patient(client), attending_doctor_id=str(USER_ID)
    )

    response = await client.get("/api/v1/encounters/worklist?scope=department")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == SCOPE_MINE
    assert [i["id"] for i in body["items"]] == [encounter["id"]]


@pytest.mark.asyncio
async def test_clinician_profile_reports_profession_and_unit(client: AsyncClient) -> None:
    """The workspace header shows who the clinician is and where they work."""
    await _register_clinician(None)

    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 200
    clinician = response.json()["clinician"]
    assert clinician["staff_id"] == str(USER_ID)
    assert clinician["name"] == "Alice Mwangi"
    assert clinician["profession"] == "doctor"
    assert response.json()["facility_wide"] is True


@pytest.mark.asyncio
async def test_admitted_and_cancelled_visits_leave_the_list(client: AsyncClient) -> None:
    """Work that has left the clinician's day is not on today's list."""
    admitted = await _encounter(client, await _patient(client))
    await client.patch(
        f"/api/v1/encounters/{admitted['id']}", json={"status": "admitted"}
    )

    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["counts"]["total"] == 0