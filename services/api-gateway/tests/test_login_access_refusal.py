"""Nobody signs in unless HR registered them, and the refusal has to say so.

An unregistered address, a switched-off account and a mistyped password look the
same to the person typing, but they are three different problems: two of them
are HR's to fix and one is theirs. The workflow only works if a new hire is sent
to HR rather than told, wrongly, that their password is wrong.

The distinction is also a line worth holding. The account's own state is
reported only after the password proves the caller owns it, so the sign-in form
cannot be used to interrogate addresses somebody happens to be guessing at.
"""

from types import SimpleNamespace

from app.routers.auth_session import _LOGIN_REFUSALS, _login_refusal
from app.utils.passwords import hash_password

PASSWORD = "NursePass123"


def _account(*, is_active: bool = True, password: str = PASSWORD) -> object:
    """An auth account stub holding a real hash of the given password."""
    return SimpleNamespace(
        is_active=is_active, password_hash=hash_password(password)
    )


def test_an_address_nobody_registered_is_named_as_unregistered() -> None:
    """HR creates the account; until it exists there is nothing to sign in to."""
    assert _login_refusal(None, PASSWORD) == "not_registered"


def test_a_mistyped_password_stays_generic() -> None:
    """The one refusal the person can fix themselves names no reason."""
    assert _login_refusal(_account(), "WrongPass123") == "invalid_credentials"


def test_a_switched_off_account_is_reported_once_the_password_proves_it() -> None:
    """A leaver who still knows their password is told to see HR, not to retry."""
    assert _login_refusal(_account(is_active=False), PASSWORD) == "access_revoked"


def test_the_account_state_is_not_revealed_to_a_wrong_password() -> None:
    """Otherwise the form answers questions about any address somebody types."""
    refusal = _login_refusal(_account(is_active=False), "WrongPass123")

    assert refusal == "invalid_credentials"


def test_correct_credentials_for_a_live_account_are_not_refused() -> None:
    """The check must not refuse the sign-in it is there to allow."""
    assert _login_refusal(_account(), PASSWORD) is None


def test_only_the_credential_failure_uses_the_generic_message() -> None:
    """Both HR refusals must name HR; a bad password must not."""
    assert "HR" in _LOGIN_REFUSALS["not_registered"][1]
    assert "HR" in _LOGIN_REFUSALS["access_revoked"][1]
    assert "HR" not in _LOGIN_REFUSALS["invalid_credentials"][1]

    # Being unregistered is not a credentials problem, so it must not answer 401.
    assert _LOGIN_REFUSALS["not_registered"][0] == 403
    assert _LOGIN_REFUSALS["access_revoked"][0] == 403
    assert _LOGIN_REFUSALS["invalid_credentials"][0] == 401
