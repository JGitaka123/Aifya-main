"""The role/permission matrix, its overrides, and the endpoints it guards.

The matrix is the answer to "which parts of Aifya may this person open?", as
opposed to the department on the staff record, which answers "which patients
of that part are theirs?". These tests pin the first answer:

* the front desk and the cashier hold no clinical permission at all,
* an unknown role still gets a working, narrow app rather than an empty one,
* an administrator cannot be narrowed by an override row,
* a facility's own row replaces the shipped baseline,
* the consultation fee is the front desk's to read, not the clinic's, and
* the seeded matrix in migration 029 matches the one in code.

The endpoint tests use the receptionist role because that is the case the
hospital reported: a receptionist could open the doctor's clinical workspace.
"""

import importlib.util
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    UNCLASSIFIED_PERMISSIONS,
    Permission,
    is_allowed,
    permissions_for_roles,
    resolve_permissions,
)
from app.main import app
from app.models.role_permission import RolePermission
from tests.conftest import FACILITY_ID, USER_ID, session_factory

#: Signature of the grant fixture: (role, permission, allowed=True).
GrantFn = Callable[..., Awaitable[None]]


def _user(*roles: str) -> CurrentUser:
    """Build a test user with the given roles."""
    return CurrentUser(
        user_id=USER_ID,
        facility_id=FACILITY_ID,
        email="test@aifya.health",
        roles=list(roles),
        name="Test User",
    )


def _act_as(*roles: str) -> None:
    """Point the current-user dependency at an account with these roles."""
    app.dependency_overrides[get_current_user] = lambda: _user(*roles)


def _role_fixture(role: str) -> Iterator[None]:
    """Sign in one role for a test, then restore the suite's default user."""
    previous = app.dependency_overrides[get_current_user]
    _act_as(role)
    try:
        yield
    finally:
        app.dependency_overrides[get_current_user] = previous


@pytest.fixture
def as_receptionist() -> Iterator[None]:
    """Sign in a front-desk user."""
    yield from _role_fixture("receptionist")


@pytest.fixture
def as_cashier() -> Iterator[None]:
    """Sign in a billing user."""
    yield from _role_fixture("cashier")


@pytest.fixture
def as_doctor() -> Iterator[None]:
    """Sign in a clinician."""
    yield from _role_fixture("doctor")


@pytest_asyncio.fixture
async def grant() -> AsyncGenerator[GrantFn, None]:
    """Insert role_permissions rows for the test facility."""

    async def _grant(
        role: str, permission: str, *, allowed: bool = True
    ) -> None:
        async with session_factory() as session:
            session.add(
                RolePermission(
                    facility_id=FACILITY_ID,
                    role=role,
                    permission=permission,
                    is_allowed=allowed,
                )
            )
            await session.commit()

    yield _grant


# ── The shipped matrix ──────────────────────────────────────────────────────


def test_front_desk_holds_no_clinical_permission() -> None:
    """Reception registers the visit; it does not read the consultation."""
    granted = permissions_for_roles(["receptionist"])

    assert Permission.CLINICAL_VIEW not in granted
    assert Permission.CLINICAL_CONSULT not in granted
    assert Permission.PATIENTS_REGISTER in granted
    assert Permission.ENCOUNTERS_CREATE in granted


def test_cashier_holds_no_clinical_permission() -> None:
    """A billing user has no business in the doctor's workspace."""
    granted = permissions_for_roles(["cashier"])

    assert Permission.CLINICAL_VIEW not in granted
    assert Permission.BILLING_PAYMENT in granted


def test_doctor_can_consult_and_dispensing_stays_with_pharmacy() -> None:
    """The clinician consults; dispensing stays with the pharmacist."""
    granted = permissions_for_roles(["doctor"])

    assert Permission.CLINICAL_CONSULT in granted
    assert Permission.LABORATORY_VIEW in granted
    assert Permission.PHARMACY_DISPENSE not in granted


def test_laboratory_staff_get_their_worklist_not_the_clinic() -> None:
    """Lab staff see their own work, never the clinical workspace."""
    granted = permissions_for_roles(["lab_tech"])

    assert Permission.LABORATORY_RESULT in granted
    assert Permission.CLINICAL_VIEW not in granted


def test_every_mapped_role_grants_at_least_one_permission() -> None:
    """An empty set renders a sidebar with one link and reads as broken."""
    for role, permissions in ROLE_PERMISSIONS.items():
        assert permissions, role


def test_administrators_hold_every_permission() -> None:
    """The escape hatch for a hospital that has locked itself out."""
    for role in ("admin", "super_admin", "facility_admin"):
        assert permissions_for_roles([role]) == ALL_PERMISSIONS


def test_unknown_role_falls_back_to_the_unclassified_baseline() -> None:
    """A role nobody has taught the system about must not blank the app."""
    assert permissions_for_roles(["cook"]) == UNCLASSIFIED_PERMISSIONS
    assert permissions_for_roles(["cook"]) == permissions_for_roles(["staff"])


def test_roles_are_matched_case_insensitively() -> None:
    """The staff record is free text, so a capitalised role still works."""
    assert permissions_for_roles(["Doctor"]) == permissions_for_roles(["doctor"])


def test_holding_several_roles_unions_their_permissions() -> None:
    """A nurse who is also a researcher keeps both sets."""
    granted = permissions_for_roles(["nurse", "research_coordinator"])

    assert Permission.TRIAGE_RECORD in granted
    assert Permission.TRIALS_VIEW in granted


def test_is_allowed_requires_all_or_any_as_asked() -> None:
    """any_of is the difference between a triage nurse writing and reading."""
    granted = frozenset({"triage.record"})

    assert is_allowed(granted, ("triage.record", "clinical.consult"), any_of=True)
    assert not is_allowed(granted, ("triage.record", "clinical.consult"))
    assert is_allowed(granted, ())
    assert not is_allowed(granted, ("clinical.consult",))


# ── Overrides ───────────────────────────────────────────────────────────────


async def test_a_facility_row_replaces_the_shipped_baseline(grant: GrantFn) -> None:
    """The hospital, not the release, decides what its roles may do."""
    await grant("receptionist", Permission.CLINICAL_VIEW.value)

    async with session_factory() as session:
        granted = await resolve_permissions(session, _user("receptionist"))

    assert Permission.CLINICAL_VIEW in granted


async def test_a_denial_row_takes_a_permission_away(grant: GrantFn) -> None:
    """is_allowed = FALSE is how a facility narrows an over-broad role."""
    await grant("doctor", Permission.CLINICAL_CONSULT.value, allowed=False)

    async with session_factory() as session:
        granted = await resolve_permissions(session, _user("doctor"))

    assert Permission.CLINICAL_CONSULT not in granted
    assert Permission.CLINICAL_VIEW in granted


async def test_an_administrator_cannot_be_narrowed(grant: GrantFn) -> None:
    """A stray deny row must not shut a hospital out of its own system."""
    await grant("admin", Permission.SETTINGS_MANAGE.value, allowed=False)

    async with session_factory() as session:
        granted = await resolve_permissions(session, _user("admin"))

    assert Permission.SETTINGS_MANAGE in granted


# ── The endpoints the matrix guards ─────────────────────────────────────────


async def test_receptionist_cannot_open_the_clinical_worklist(
    client: AsyncClient, as_receptionist: None
) -> None:
    """The reported bug: the front desk saw the doctor's queue."""
    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 403
    assert Permission.CLINICAL_VIEW.value in response.json()["detail"]


async def test_receptionist_cannot_call_the_next_patient(
    client: AsyncClient, as_receptionist: None
) -> None:
    """Starting a consultation is a clinical act, not a front-desk one."""
    response = await client.post("/api/v1/encounters/queue/call-next")

    assert response.status_code == 403


async def test_cashier_cannot_open_the_clinical_worklist(
    client: AsyncClient, as_cashier: None
) -> None:
    """Billing has no clinical workspace at all."""
    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 403


async def test_doctor_reaches_an_empty_but_permitted_worklist(
    client: AsyncClient, as_doctor: None
) -> None:
    """A clinician passes the gate; an empty day is not an error."""
    response = await client.get("/api/v1/encounters/worklist")

    assert response.status_code == 200
    assert response.json()["counts"]["total"] == 0


async def test_receptionist_cannot_write_a_consultation(
    client: AsyncClient, as_receptionist: None
) -> None:
    """Diagnoses, prescriptions and orders are the clinician's to write."""
    encounter_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/diagnoses",
        json={
            "encounter_id": str(encounter_id),
            "patient_id": str(uuid.uuid4()),
            "icd10_code": "J06.9",
            "icd10_description": "Acute upper respiratory infection",
            "diagnosis_type": "primary",
        },
    )

    assert response.status_code == 403


async def test_a_doctor_cannot_read_the_consultation_fee(
    client: AsyncClient, as_doctor: None
) -> None:
    """The quote carries the invoice and receipt, so it is a billing read."""
    response = await client.get(
        f"/api/v1/encounters/{uuid.uuid4()}/consultation-fee"
    )

    assert response.status_code == 403
    assert Permission.BILLING_VIEW.value in response.json()["detail"]


async def test_reception_can_still_read_the_consultation_fee(
    client: AsyncClient, as_receptionist: None
) -> None:
    """The desk collects the fee, so the gate must keep admitting it."""
    response = await client.get(
        f"/api/v1/encounters/{uuid.uuid4()}/consultation-fee"
    )

    # Past the permission gate, so the random id is simply not on file.
    assert response.status_code == 404


# ── The migration must not drift from the code ──────────────────────────────

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "029_role_permissions.py"
)


def _load_seed_migration():
    """Import migration 029 by path so its frozen matrix can be compared."""
    spec = importlib.util.spec_from_file_location("migration_029", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_migration_matches_the_shipped_matrix() -> None:
    """A frozen seed that drifts from the code silently changes access."""
    migration = _load_seed_migration()

    assert set(migration._ALL_PERMISSIONS) == set(ALL_PERMISSIONS)
    assert set(migration._ROLE_PERMISSIONS) == set(ROLE_PERMISSIONS)
    for role, permissions in migration._ROLE_PERMISSIONS.items():
        assert set(permissions) == set(ROLE_PERMISSIONS[role]), role
