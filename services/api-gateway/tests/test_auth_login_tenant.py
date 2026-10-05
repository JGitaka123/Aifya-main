"""Sign-in must bind a person to exactly one facility - the one on their staff row.

auth_accounts carries a facility, but only so that row level security has a
bootstrap tenant to read the staff record under: the login has to know which
hospital to look in before it can look at all. The binding that decides which
hospital a token can see is the facility on the staff record itself.

That distinction is easy to lose, and losing it is quiet. A staff row in another
facility is invisible under RLS, so a drift looks identical to a deleted record,
and both used to surface as one blanket refusal that told the hospital nothing
about which record to go and fix.

These tests stub the database, so they need no schema and no Postgres.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.routers import auth_session
from app.routers.auth_session import (
    _BINDING_MESSAGES,
    _binding_detail,
    _facility_matches,
    _resolve_tenant,
)

#: The two real facilities this was written against: mku and kenyatta.
FACILITY_ID = uuid.UUID("8f289f05-a5c3-487b-8684-3bf6931d1c4a")
OTHER_FACILITY_ID = uuid.UUID("2b0b3fba-f1ad-48f2-919d-ac98c630db35")
STAFF_ID = uuid.UUID("baffb1fa-42b9-4c7b-a825-629fa37eb49f")

#: Facility ids the binding asked the session to publish as the tenant.
_CONTEXT_CALLS: list[str] = []


class FakeSession:
    """Stand-in for AsyncSession that answers get(Model, pk) from a dict."""

    def __init__(self, rows: dict[tuple[str, uuid.UUID], object]) -> None:
        self.rows = rows
        self.asked: list[tuple[str, uuid.UUID]] = []

    async def get(self, model: type, ident: uuid.UUID):
        self.asked.append((model.__name__, ident))
        return self.rows.get((model.__name__, ident))


@pytest.fixture(autouse=True)
def _stub_facility_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Capture the tenant instead of running SQL against a session."""
    _CONTEXT_CALLS.clear()

    async def fake_set_context(
        _db: object, facility_id: str, **_kwargs: object
    ) -> None:
        _CONTEXT_CALLS.append(facility_id)

    monkeypatch.setattr(
        auth_session, "set_facility_context", fake_set_context
    )


def _account(
    facility_id: uuid.UUID = FACILITY_ID, staff_id: uuid.UUID = STAFF_ID
) -> object:
    return SimpleNamespace(facility_id=facility_id, staff_id=staff_id)


def _staff(
    facility_id: uuid.UUID = FACILITY_ID,
    *,
    is_active: bool = True,
    is_deleted: bool = False,
) -> object:
    return SimpleNamespace(
        id=STAFF_ID,
        facility_id=facility_id,
        is_active=is_active,
        is_deleted=is_deleted,
    )


def _facility(
    facility_id: uuid.UUID = FACILITY_ID,
    *,
    is_active: bool = True,
    name: str = "Nairobi General Hospital",
    code: str = "NGH",
) -> object:
    return SimpleNamespace(
        id=facility_id, is_active=is_active, name=name, code=code
    )


def _rows(staff: object | None, facility: object | None):
    rows: dict[tuple[str, uuid.UUID], object] = {}
    if staff is not None:
        rows[("Staff", STAFF_ID)] = staff
    if facility is not None:
        rows[("Facility", FACILITY_ID)] = facility
    return rows


async def test_a_doctor_is_bound_to_the_facility_on_their_staff_record() -> None:
    """The staff row decides the tenant, and the account only bootstraps it."""
    session = FakeSession(_rows(_staff(), _facility()))

    staff, facility, reason = await _resolve_tenant(session, _account())

    assert reason is None
    assert staff is not None and facility is not None
    # The bootstrap tenant is published from the account, because the staff row
    # cannot be read until some tenant is set.
    assert _CONTEXT_CALLS == [str(FACILITY_ID)]
    # But the facility the caller issues the token for is read back off the
    # staff record, not copied from the account.
    assert ("Facility", FACILITY_ID) in session.asked
    assert staff.facility_id == facility.id


async def test_a_staff_row_in_another_facility_refuses_the_binding() -> None:
    """Account says one hospital, staff record says another: do not guess."""
    session = FakeSession(_rows(_staff(OTHER_FACILITY_ID), None))

    staff, facility, reason = await _resolve_tenant(session, _account())

    assert (staff, facility) == (None, None)
    assert reason == "facility_mismatch"


async def test_a_staff_row_outside_the_tenant_reads_as_unbound() -> None:
    """Under RLS another facility's staff row is invisible, not merely absent."""
    session = FakeSession({})

    staff, facility, reason = await _resolve_tenant(session, _account())

    assert (staff, facility) == (None, None)
    assert reason == "no_staff"


async def test_a_soft_deleted_staff_row_cannot_sign_in() -> None:
    """A record retired in HR must stop authenticating immediately."""
    session = FakeSession(_rows(_staff(is_deleted=True), None))

    assert (await _resolve_tenant(session, _account()))[2] == "no_staff"


async def test_an_inactive_staff_row_cannot_sign_in() -> None:
    """Suspending someone is how a hospital takes access away."""
    session = FakeSession(_rows(_staff(is_active=False), None))

    assert (await _resolve_tenant(session, _account()))[2] == "inactive_staff"


async def test_a_missing_facility_cannot_bind() -> None:
    """A staff row pointing at no facility has no tenant to scope to."""
    session = FakeSession(_rows(_staff(), None))

    assert (await _resolve_tenant(session, _account()))[2] == "no_facility"


async def test_a_suspended_facility_cannot_bind() -> None:
    """An unapproved or switched-off hospital must not mint tokens."""
    session = FakeSession(_rows(_staff(), _facility(is_active=False)))

    assert (await _resolve_tenant(session, _account()))[2] == "inactive_facility"


def test_every_refusal_names_the_record_to_fix() -> None:
    """One blanket 'not active at an approved facility' helps nobody."""
    messages = {_binding_detail(reason) for reason in _BINDING_MESSAGES}

    assert len(messages) == len(_BINDING_MESSAGES)


def test_an_unrecognised_reason_still_refuses_safely() -> None:
    """A reason added later must not accidentally explain nothing."""
    generic = "Your account is not active at an approved facility."

    assert _binding_detail(None) == generic
    assert _binding_detail("invented_later") == generic


def test_the_hospital_named_at_sign_in_must_be_the_one_on_the_record() -> None:
    """A correct password at the wrong hospital must not start a session."""
    assert _facility_matches("Nairobi General Hospital", _facility()) is True
    assert _facility_matches("Kenyatta National Hospital", _facility()) is False


def test_the_hospital_name_is_matched_leniently() -> None:
    """Casing, padding and punctuation belong to the typist, not the hospital."""
    for typed in (
        "nairobi general hospital",
        "  Nairobi   General   Hospital  ",
        "Nairobi General Hospital.",
        "NAIROBI-GENERAL-HOSPITAL",
    ):
        assert _facility_matches(typed, _facility()) is True


def test_the_short_facility_code_is_accepted() -> None:
    """Staff know their hospital by its code as often as by its full name."""
    assert _facility_matches("ngh", _facility()) is True


def test_a_blank_hospital_name_never_matches() -> None:
    """A blank box must not fall through as a match."""
    assert _facility_matches("", _facility()) is False
    assert _facility_matches("   ", _facility()) is False


def test_a_facility_without_a_code_still_matches_on_its_name() -> None:
    """The code is a convenience, not a requirement."""
    facility = _facility(code="")
    assert _facility_matches(facility.name, facility) is True
