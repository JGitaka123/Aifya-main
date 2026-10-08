"""Give a staff member a login, change it, or take it away.

The ``staff`` table says who someone is and what they may do; the platform
level ``auth_accounts`` table says whether they can sign in at all. "Only
employees HR has added and activated may log in" therefore spans both tables,
and keeping them in step is this module's whole job - so the HR and payroll
routers cannot drift apart on it.

Deactivating a staff member flips the login off with them. The account row is
kept rather than deleted: a returning employee is re-activated instead of
re-created, and the audit trail keeps its references.

Under ``AUTH_PROVIDER=internal`` the login is an ``auth_accounts`` row created
here. Under ``AUTH_PROVIDER=keycloak`` the credential lives in the realm, so
this module writes it there through the Keycloak Admin API: staff invitations
go through ``onboarding_service.invite_staff``, and HR issuing or resetting a
password goes through ``set_keycloak_staff_password``.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth_account import AuthAccount
from app.models.staff import Staff
from app.utils.keycloak_admin import (
    KeycloakAdminError,
    get_keycloak_admin_client,
)
from app.utils.passwords import hash_password

#: Shortest password HR may set on a colleague's account. The login form
#: accepts whatever is stored, so this is the only place a weak initial
#: password can be stopped.
MIN_PASSWORD_LENGTH = 8


class StaffAccessError(ValueError):
    """A login could not be created or changed, with a message for the UI."""


def _clean_email(email: str) -> str:
    """Lower-case and trim an address so lookups match the unique index."""
    return email.strip().lower()


def _check_password(password: str) -> None:
    """
    Reject a password too short to be worth hashing.

    @param password: Plaintext password from the request body
    @raises StaffAccessError: When it does not meet the minimum length
    """
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise StaffAccessError(
            "The password must be at least "
            f"{MIN_PASSWORD_LENGTH} characters long."
        )


async def find_login(
    db: AsyncSession, staff_id: uuid.UUID
) -> AuthAccount | None:
    """
    Read the login bound to a staff member, if there is one.

    @param db: Database session
    @param staff_id: Staff UUID
    @returns The auth account, or None when this person cannot sign in
    """
    return (
        await db.execute(
            select(AuthAccount).where(AuthAccount.staff_id == staff_id)
        )
    ).scalar_one_or_none()


async def staff_with_login_ids(
    db: AsyncSession, staff_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """
    Which of these staff members have a login at all.

    The directory listing marks who can sign in, which is otherwise a
    per-row query; one IN(...) keeps the list endpoint a single round trip.

    @param db: Database session
    @param staff_ids: Staff UUIDs to test
    @returns The subset that has an auth account
    """
    if not staff_ids:
        return set()
    rows = await db.execute(
        select(AuthAccount.staff_id).where(
            AuthAccount.staff_id.in_(staff_ids)
        )
    )
    return {row for row in rows.scalars()}


async def _reject_duplicate_email(
    db: AsyncSession, staff: Staff, email: str
) -> None:
    """
    Refuse an address another staff member already signs in with.

    ``auth_accounts`` is not facility-scoped (login looks an email up across
    every facility), so the address has to be unique system-wide. Checking
    here turns a database error into a sentence HR can act on.

    @param db: Database session
    @param staff: Staff member the login belongs to
    @param email: Address the login would use
    @raises StaffAccessError: When another staff record owns the address
    """
    existing = (
        await db.execute(
            select(AuthAccount).where(
                func.lower(AuthAccount.email) == _clean_email(email)
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.staff_id != staff.id:
        raise StaffAccessError(
            f"{email} is already the sign-in address for another staff "
            "record. Use a different email address."
        )


async def provision_login(
    db: AsyncSession,
    *,
    staff: Staff,
    password: str,
    actor_id: uuid.UUID | None = None,
) -> AuthAccount:
    """
    Create the login for a staff member, or reset the existing one.

    Idempotent on purpose: HR filling the same form twice, or re-inviting
    someone who never signed in, updates the password on the account that is
    already there instead of failing on the unique index.

    @param db: Database session
    @param staff: Staff member the login belongs to
    @param password: Initial (or replacement) plaintext password
    @param actor_id: HR user performing the change, for the audit columns
    @returns The created or updated auth account
    @raises StaffAccessError: When the password is weak or the email is taken
    """
    _check_password(password)
    await _reject_duplicate_email(db, staff, staff.email)

    account = await find_login(db, staff.id)
    if account is None:
        account = AuthAccount(
            staff_id=staff.id,
            facility_id=staff.facility_id,
            email=_clean_email(staff.email),
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(account)
    else:
        account.email = _clean_email(staff.email)
        account.facility_id = staff.facility_id
        account.password_hash = hash_password(password)
        account.is_active = True

    await db.flush()
    _ = actor_id  # auth_accounts has no created_by/updated_by columns
    return account


async def set_login_password(
    db: AsyncSession, *, staff: Staff, password: str
) -> AuthAccount:
    """
    Reset the password of an existing login.

    @param db: Database session
    @param staff: Staff member whose password is being reset
    @param password: New plaintext password
    @returns The updated auth account
    @raises StaffAccessError: When the password is weak or no login exists
    """
    _check_password(password)
    account = await find_login(db, staff.id)
    if account is None:
        raise StaffAccessError(
            "This staff member does not have a system login yet. "
            "Create one first, then set the password."
        )
    account.password_hash = hash_password(password)
    account.is_active = True
    await db.flush()
    return account


async def set_login_active(
    db: AsyncSession, *, staff: Staff, is_active: bool
) -> None:
    """
    Follow a staff activation change onto their login.

    A staff member with no login is left alone: deactivating them is still a
    valid HR action even though they never had credentials.

    @param db: Database session
    @param staff: Staff member whose login should follow their active state
    @param is_active: The new staff active state
    """
    account = await find_login(db, staff.id)
    if account is None or account.is_active == is_active:
        return
    account.is_active = is_active
    await db.flush()


async def set_keycloak_staff_password(
    db: AsyncSession,
    *,
    staff: Staff,
    password: str,
    temporary: bool = False,
) -> None:
    """
    Set a staff member's Keycloak password.

    Under ``AUTH_PROVIDER=keycloak`` the credential lives in the realm rather
    than in ``auth_accounts``, so this is the Keycloak counterpart of
    ``provision_login``. It is how HR gives a registered employee their first
    way in, and how a forgotten password is replaced.

    A staff row can exist with no realm account behind it: "Add Employee"
    writes the directory row with a placeholder id. So when the email has no
    Keycloak user the account is created here and the real id is written back,
    which is what lets HR register someone and hand them a login in one step.

    @param db: Database session
    @param staff: Staff member the credential belongs to
    @param password: New plaintext password
    @param temporary: Force the change at next sign-in
    @raises StaffAccessError: When provisioning is unconfigured or refuses
    """
    _check_password(password)
    client = get_keycloak_admin_client()
    if not client.is_configured:
        raise StaffAccessError(
            "User provisioning is not configured (Keycloak admin credentials "
            "missing)."
        )
    try:
        user_id = await client.find_user_id(email=staff.email)
        if user_id is None:
            user_id = await client.create_user(
                email=staff.email,
                first_name=staff.first_name,
                last_name=staff.last_name,
                facility_id=str(staff.facility_id),
                roles=[staff.role],
                temporary_password=password,
                force_password_change=temporary,
                send_invite_email=False,
            )
        else:
            await client.set_user_password(
                user_id=user_id,
                password=password,
                temporary=temporary,
            )
        if str(staff.keycloak_user_id) != user_id:
            staff.keycloak_user_id = uuid.UUID(user_id)
            await db.flush()
    except KeycloakAdminError as exc:
        raise StaffAccessError(str(exc)) from exc


async def provision_staff_login(
    db: AsyncSession,
    *,
    staff: Staff,
    password: str,
    actor_id: uuid.UUID | None = None,
    temporary: bool = False,
) -> None:
    """
    Create or reset a staff member's login under the active auth provider.

    Callers should not need to know where the credential lives. Under
    ``internal`` this writes the ``auth_accounts`` row; under ``keycloak`` it
    writes the realm. Routing every "give this person a password" through one
    function is what keeps the payroll Add Employee form and the HR password
    dialog from drifting apart on which store they update.

    @param db: Database session
    @param staff: Staff member the login belongs to
    @param password: Plaintext password to set
    @param actor_id: HR user performing the change (internal mode audit)
    @param temporary: Force a change at next sign-in (keycloak mode)
    @raises StaffAccessError: When the password is weak or provisioning fails
    """
    if settings.auth_provider == "keycloak":
        await set_keycloak_staff_password(
            db, staff=staff, password=password, temporary=temporary
        )
        return
    await provision_login(db, staff=staff, password=password, actor_id=actor_id)
