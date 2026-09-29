"""A Keycloak login must resolve to a staff record, not to the provider's id.

The identity provider and the database name the same person two different ways.
Keycloak owns the login and carries its own user id; Aifya owns the clinical
record and keys every table - encounters, queues, audit rows, per-person
permission grants - on ``staff.id``. ``staff.keycloak_user_id`` is the only
join between the two, and until this was added nothing in the sign-in path
performed it.

The failure that motivated this is quiet, which is why it is worth pinning
down. A token carrying an unjoined id still authenticates, still passes every
role check, and still saves - it simply attributes the work to a user that does
not exist, so the clinician's own queue stays empty and the audit trail names
nobody. Refusing instead is the whole point.

These tests stub the database, so they need no schema and no Postgres.
"""

import uuid
from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app import database as database_module
from app.auth import dependencies
from app.auth.dependencies import (
    _KEYCLOAK_BINDING_MESSAGES,
    CurrentUser,
    _bind_keycloak_identity,
    _keycloak_binding_detail,
)

#: The real facility this was written against: mku hospital.
FACILITY_ID = uuid.UUID("8f289f05-a5c3-487b-8684-3bf6931d1c4a")
#: The staff record, and the Keycloak user it is linked to. Deliberately
#: different values: that difference is the entire subject of this module.
STAFF_ID = uuid.UUID("baffb1fa-42b9-4c7b-a825-629fa37eb49f")
KEYCLOAK_ID = uuid.UUID("82cda2c4-65b0-4dbd-887e-1f07e7ddf4e5")


@dataclass
class FakeStaff:
    """The two staff columns the lookup reads."""

    id: uuid.UUID
    is_active: bool


#: Rows the fake session will hand back: zero or one staff record.
_ROWS: list[FakeStaff] = []
#: Tenants the lookup published to the session before reading staff.
_CONTEXT_CALLS: list[str] = []


class FakeResult:
    """The slice of SQLAlchemy's Result the lookup actually uses."""

    def __init__(self, staff: FakeStaff | None) -> None:
        self._staff = staff

    def scalars(self) -> "FakeResult":
        return self

    def first(self) -> FakeStaff | None:
        return self._staff


class FakeSession:
    """Stand-in for AsyncSession that answers execute() from a fixed row."""

    def __init__(self, staff: FakeStaff | None) -> None:
        self._staff = staff

    async def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self._staff)

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def _stub_identity_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the lookup's session and tenant publication with fakes."""

    def fake_session_factory() -> FakeSession:
        return FakeSession(_ROWS[0] if _ROWS else None)

    async def fake_set_context(
        _db: object, facility_id: str, **_kwargs: object
    ) -> None:
        _CONTEXT_CALLS.append(facility_id)

    _ROWS.clear()
    _CONTEXT_CALLS.clear()
    monkeypatch.setattr(database_module, "async_session", fake_session_factory)
    monkeypatch.setattr(dependencies, "set_facility_context", fake_set_context)


def _token_user() -> CurrentUser:
    """The user as built from the Keycloak token, before binding."""
    return CurrentUser(
        user_id=KEYCLOAK_ID,
        facility_id=FACILITY_ID,
        email="johnmaina234@gmail.com",
        roles=["doctor"],
        name="John Maina",
    )


async def test_a_keycloak_login_is_rekeyed_onto_the_staff_record() -> None:
    """Clinically, everything keys on staff.id, so the token id is replaced."""
    _ROWS.append(FakeStaff(STAFF_ID, True))

    bound = await _bind_keycloak_identity(_token_user())

    assert bound.user_id == STAFF_ID
    assert bound.user_id != KEYCLOAK_ID


async def test_binding_preserves_the_rest_of_the_token_identity() -> None:
    """Only the id changes; the rest still comes from the token."""
    _ROWS.append(FakeStaff(STAFF_ID, True))

    bound = await _bind_keycloak_identity(_token_user())

    assert bound.facility_id == FACILITY_ID
    assert bound.roles == ["doctor"]
    assert bound.email == "johnmaina234@gmail.com"
    assert bound.name == "John Maina"


async def test_binding_does_not_mutate_the_user_it_was_given() -> None:
    """CurrentUser is frozen, so the caller's object is left alone."""
    _ROWS.append(FakeStaff(STAFF_ID, True))
    original = _token_user()

    await _bind_keycloak_identity(original)

    assert original.user_id == KEYCLOAK_ID


async def test_the_staff_lookup_runs_under_the_token_facility() -> None:
    """staff is RLS scoped: without a tenant every login looks unlinked."""
    _ROWS.append(FakeStaff(STAFF_ID, True))

    await _bind_keycloak_identity(_token_user())

    assert _CONTEXT_CALLS == [str(FACILITY_ID)]


async def test_a_login_with_no_staff_record_is_refused() -> None:
    """A provider account with no staff row has no tenant to work in."""
    with pytest.raises(HTTPException) as raised:
        await _bind_keycloak_identity(_token_user())

    assert raised.value.status_code == 403
    assert "not linked to a staff record" in str(raised.value.detail)


async def test_an_inactive_staff_record_is_refused() -> None:
    """Suspending someone in HR must take their access away at once."""
    _ROWS.append(FakeStaff(STAFF_ID, False))

    with pytest.raises(HTTPException) as raised:
        await _bind_keycloak_identity(_token_user())

    assert raised.value.status_code == 403
    assert "not active" in str(raised.value.detail)


async def test_a_refusal_never_falls_back_to_the_provider_id() -> None:
    """The old behaviour was to carry on with the Keycloak id. It must not."""
    with pytest.raises(HTTPException) as raised:
        await _bind_keycloak_identity(_token_user())

    assert str(KEYCLOAK_ID) not in str(raised.value.detail)


def test_every_refusal_names_the_record_to_fix() -> None:
    """One blanket refusal helps nobody; each reason must read differently."""
    messages = {
        _keycloak_binding_detail(reason) for reason in _KEYCLOAK_BINDING_MESSAGES
    }

    assert len(messages) == len(_KEYCLOAK_BINDING_MESSAGES)


def test_an_unrecognised_reason_still_refuses_safely() -> None:
    """A reason added later must not accidentally explain nothing."""
    generic = (
        "Your sign-in is not linked to a staff record at this facility. "
        "Ask an administrator to check your account."
    )

    assert _keycloak_binding_detail(None) == generic
    assert _keycloak_binding_detail("invented_later") == generic
