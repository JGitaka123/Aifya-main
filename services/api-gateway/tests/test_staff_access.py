"""HR adds the employee, HR picks the role, HR turns the login on.

The rule these tests defend: a person can only sign in because HR created them
and left them active, and the tabs they then see are decided by the role HR
chose - never by what they typed into a job-title box, and never by a role the
API does not recognise.

They run against the SQLite schema like the rest of the endpoint tests, so no
Postgres is needed.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth_account import AuthAccount
from app.models.staff import Staff
from tests.conftest import session_factory

pytestmark = pytest.mark.asyncio


def _unique(prefix: str) -> str:
    """A short unique suffix so each test creates its own employee."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


#: The hospital named at sign-in. The API matches it against the employee's HR
#: record, so a test that signs in has to name the facility it registered at.
FACILITY_NAME = "Aifya Test Hospital"


async def _create_employee(client: AsyncClient, **overrides: object):
    """
    Register an employee through the HR employee form.

    @param client: Test HTTP client
    @param overrides: Fields to override on the default payload
    @returns The HTTP response
    """
    payload: dict[str, object] = {
        "staff_id": _unique("EMP"),
        "full_name": "John Maina",
        "job_title": "General Practitioner",
        "employment_type": "permanent",
        "hire_date": "2026-01-05",
    }
    payload.update(overrides)
    return await client.post("/api/v1/payroll/employees", json=payload)


async def _staff_row(employee_number: str) -> Staff:
    """
    Read back the clinical staff row the employee was mirrored into.

    @param employee_number: The employee number used at creation
    @returns The staff row
    """
    async with session_factory() as session:
        return (
            await session.execute(
                select(Staff).where(Staff.employee_number == employee_number)
            )
        ).scalar_one()


async def test_role_catalogue_lists_only_assignable_roles(
    client: AsyncClient,
) -> None:
    """The picker offers the hospital roles, never an administrator role."""
    response = await client.get("/api/v1/hr/roles")

    assert response.status_code == 200
    roles = {item["role"] for item in response.json()["items"]}
    for expected in ("doctor", "nurse", "pharmacist", "lab_tech", "receptionist"):
        assert expected in roles
    # An HR officer who could hand out administrator access could grant
    # themselves anything, so these are deliberately not assignable here.
    assert roles.isdisjoint({"admin", "facility_admin", "super_admin"})


async def test_hr_role_beats_the_job_title(client: AsyncClient) -> None:
    """The role HR picks wins over what the job title would have implied."""
    payload = await _create_employee(
        client,
        job_title="General Practitioner",
        role="pharmacist",
    )
    assert payload.status_code == 201
    number = payload.json()["staff_id"]

    staff = await _staff_row(number)
    assert staff.role == "pharmacist"


async def test_unknown_role_is_refused(client: AsyncClient) -> None:
    """A role outside the catalogue cannot be written onto a staff record."""
    response = await _create_employee(client, role="facility_admin")

    assert response.status_code == 422
    assert "role HR can assign" in response.json()["detail"]


async def test_login_is_created_with_the_employee(
    client: AsyncClient,
) -> None:
    """A password on the form creates a login the employee can actually use."""
    email = f"dorcas.{uuid.uuid4().hex[:6]}@example.com"
    created = await _create_employee(
        client,
        full_name="Dorcas Wangari",
        job_title="Staff Nurse",
        role="nurse",
        email=email,
        login_password="NursePass123",
    )
    assert created.status_code == 201
    assert created.json()["has_login"] is True

    # The password the form carried is the one that signs in.
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "NursePass123",
            "facility": FACILITY_NAME,
        },
    )
    assert login.status_code == 200
    user = login.json()["user"]
    assert user["roles"] == ["nurse"]
    # Nursing access, and none of the doctor's workspace.
    assert "opd.view" in user["permissions"]
    assert "clinical.consult" not in user["permissions"]


async def test_deactivating_staff_stops_the_login(client: AsyncClient) -> None:
    """An employee HR switches off can no longer sign in."""
    email = f"peter.{uuid.uuid4().hex[:6]}@example.com"
    created = await _create_employee(
        client,
        full_name="Peter Otieno",
        role="lab_tech",
        email=email,
        login_password="LabPass1234",
    )
    staff = await _staff_row(created.json()["staff_id"])

    deactivated = await client.patch(
        f"/api/v1/hr/staff/{staff.id}/active", json={"is_active": False}
    )
    assert deactivated.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "LabPass1234",
            "facility": FACILITY_NAME,
        },
    )
    # Deactivation switches the auth account off. The correct password still
    # proves the caller owns the account, so the sign-in form is told the truth
    # - the access was switched off and HR can restore it - rather than the
    # vague answer reserved for a wrong password.
    assert login.status_code == 403
    assert login.json()["code"] == "access_revoked"
    async with session_factory() as session:
        account = (
            await session.execute(
                select(AuthAccount).where(AuthAccount.staff_id == staff.id)
            )
        ).scalar_one()
    assert account.is_active is False


async def test_role_change_moves_the_access(client: AsyncClient) -> None:
    """Editing the role is what changes which tabs the employee may open."""
    email = f"mary.{uuid.uuid4().hex[:6]}@example.com"
    created = await _create_employee(
        client,
        full_name="Mary Wanjiku",
        role="lab_tech",
        email=email,
        login_password="MaryPass123",
    )
    staff = await _staff_row(created.json()["staff_id"])

    moved = await client.patch(
        f"/api/v1/hr/staff/{staff.id}/role", json={"role": "receptionist"}
    )
    assert moved.status_code == 200
    assert moved.json()["role"] == "receptionist"

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "MaryPass123",
            "facility": FACILITY_NAME,
        },
    )
    permissions = login.json()["user"]["permissions"]
    # Registration, not the laboratory bench.
    assert "patients.register" in permissions
    assert "laboratory.result" not in permissions


async def test_a_payroll_edit_does_not_silently_move_access(
    client: AsyncClient,
) -> None:
    """Retyping the job title must not reassign the role HR set."""
    created = await _create_employee(client, role="pharmacist")
    employee_id = created.json()["id"]
    number = created.json()["staff_id"]

    edited = await client.patch(
        f"/api/v1/payroll/employees/{employee_id}",
        json={"job_title": "Senior Nurse"},
    )
    assert edited.status_code == 200

    staff = await _staff_row(number)
    assert staff.role == "pharmacist"


async def test_changing_a_role_to_nonsense_is_refused(
    client: AsyncClient,
) -> None:
    """The role edit endpoint refuses anything outside the catalogue."""
    created = await _create_employee(client, role="nurse")
    staff = await _staff_row(created.json()["staff_id"])

    response = await client.patch(
        f"/api/v1/hr/staff/{staff.id}/role", json={"role": "wizard"}
    )
    assert response.status_code == 422
