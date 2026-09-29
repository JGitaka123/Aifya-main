import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.middleware.facility_context import set_facility_context

security = HTTPBearer(auto_error=False)
security_dependency = Depends(security)


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    facility_id: uuid.UUID
    email: str
    roles: list[str]
    name: str


def _auth_error(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None:
        return credentials.credentials

    cookie_token = request.cookies.get("access_token")
    if cookie_token and cookie_token.lower().startswith("bearer "):
        return cookie_token[7:].strip()
    return cookie_token


def _claim_as_uuid(payload: Mapping[str, object], claim: str) -> uuid.UUID:
    value = payload.get(claim)
    if not value:
        raise ValueError(f"Missing required claim: {claim}")
    return uuid.UUID(str(value))


def _claim_roles(payload: Mapping[str, object]) -> list[str]:
    roles: list[str] = []

    realm_access = payload.get("realm_access")
    if isinstance(realm_access, Mapping):
        realm_roles = realm_access.get("roles")
        if isinstance(realm_roles, list):
            roles.extend(str(role) for role in realm_roles if role)

    resource_access = payload.get("resource_access")
    if isinstance(resource_access, Mapping):
        client_access = resource_access.get(settings.keycloak_client_id)
        if isinstance(client_access, Mapping):
            client_roles = client_access.get("roles")
            if isinstance(client_roles, list):
                roles.extend(str(role) for role in client_roles if role)

    return list(dict.fromkeys(roles))


def _current_user_from_payload(payload: Mapping[str, object]) -> CurrentUser:
    return CurrentUser(
        user_id=_claim_as_uuid(payload, "sub"),
        facility_id=_claim_as_uuid(payload, "facility_id"),
        email=str(payload.get("email") or ""),
        roles=_claim_roles(payload),
        name=str(payload.get("name") or payload.get("preferred_username") or ""),
    )


def _beta_current_user() -> CurrentUser:
    """
    Build the configured public beta user.

    @returns Facility-scoped beta user for unauthenticated beta access
    """
    return CurrentUser(
        user_id=uuid.UUID(settings.beta_user_id),
        facility_id=uuid.UUID(settings.beta_facility_id),
        email=settings.beta_user_email,
        roles=settings.beta_user_role_list,
        name=settings.beta_user_name,
    )


async def _set_request_facility_context(
    request: Request,
    current_user: CurrentUser,
) -> None:
    request.state.current_user = current_user
    request.state.facility_id = current_user.facility_id

    db = getattr(request.state, "db", None)
    if isinstance(db, AsyncSession):
        await set_facility_context(
            db,
            str(current_user.facility_id),
            user_id=current_user.user_id,
            email=current_user.email,
            roles=current_user.roles,
        )


#: Why a Keycloak sign-in could not be tied to a staff record. The identity
#: provider proves who someone is; the staff record says where they work and
#: what they may do, so a token with no staff record behind it has no tenant,
#: no department and no role the hospital has actually assigned.
_KEYCLOAK_BINDING_MESSAGES: dict[str, str] = {
    "no_staff": (
        "Your sign-in is not linked to a staff record at this facility. "
        "Ask an administrator to check your account."
    ),
    "inactive_staff": (
        "Your staff record is not active. Ask an administrator to re-enable it."
    ),
}


async def _linked_staff(
    facility_id: uuid.UUID,
    keycloak_user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, str | None]:
    """
    Find the Aifya staff record a Keycloak sign-in belongs to.

    The two identifiers are deliberately different. Keycloak owns the login and
    the database owns the clinical record, and ``staff.keycloak_user_id`` is the
    only join between them. Nothing upstream of this performs that join, so
    without it every later use of the user id - doctor assignment, the
    department-scoped queue, per-person permission grants and the clinical audit
    trail - would be keyed on a value no staff row carries.

    ``staff`` is row level security scoped, so the tenant is published to the
    session before the read. A lookup that skipped that step would return no row
    and read as "unlinked account" rather than as a bug.

    The session is opened here rather than shared with the request: which of
    FastAPI's dependencies is resolved first decides whether the request already
    has one, and a security decision should not depend on that ordering.

    @param facility_id: Facility claim from the access token
    @param keycloak_user_id: ``sub`` claim from the access token
    @returns Tuple of (staff UUID, refusal reason); reason is None when found
    """
    from app.database import async_session
    from app.models.staff import Staff

    async with async_session() as db:
        await set_facility_context(db, str(facility_id))
        result = await db.execute(
            select(Staff).where(
                Staff.facility_id == facility_id,
                Staff.keycloak_user_id == keycloak_user_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        staff = result.scalars().first()
        if staff is None:
            return None, "no_staff"
        if not staff.is_active:
            return None, "inactive_staff"
        # Read inside the session: the row is detached once it closes.
        return staff.id, None


def _keycloak_binding_detail(reason: str | None) -> str:
    """
    Explain, in the hospital's terms, which record to go and fix.

    @param reason: Refusal reason, or None
    @returns Human-readable refusal message
    """
    return _KEYCLOAK_BINDING_MESSAGES.get(
        reason or "", "Your sign-in is not linked to a staff record at this "
        "facility. Ask an administrator to check your account."
    )


async def _bind_keycloak_identity(current_user: CurrentUser) -> CurrentUser:
    """
    Re-key a Keycloak-derived user onto the staff record it belongs to.

    Refuses rather than falling back to the provider's own id. A wrong user id
    is quiet: the row saves, the queue just never shows the patient, and the
    audit trail names a user that does not exist. A refusal is loud and says
    which record to fix, which is the better failure for a clinical system.

    @param current_user: User built from the Keycloak token
    @returns The same user, keyed on their staff record
    @raises HTTPException 403: When no active staff record is linked
    """
    staff_id, reason = await _linked_staff(
        current_user.facility_id, current_user.user_id
    )
    if staff_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_keycloak_binding_detail(reason),
        )
    return replace(current_user, user_id=staff_id)


#: Why an internal sign-in that was valid when it was issued is refused now.
#: HR owns the employee record, so switching that record off has to stop the
#: session in flight, not only the next sign-in.
_INTERNAL_REVOKED_MESSAGE = (
    "Your Aifya access has been switched off. Please contact HR/Admin "
    "to have it restored."
)


async def _assert_internal_account_active(current_user: CurrentUser) -> None:
    """
    Re-check the employee record behind an internal sign-in.

    A signed, unexpired token says who signed in - it does not say whether HR
    still wants them in. Deactivating an employee flips ``staff.is_active``, so
    this reads that row on every request and refuses the moment it is switched
    off. Without it a deactivated employee keeps working until their 12-hour
    token expires.

    The session is opened here rather than shared with the request so the
    security decision never depends on FastAPI dependency ordering, matching
    how _linked_staff handles the Keycloak path.

    @param current_user: User built from the internal token
    @raises HTTPException 403: When the staff record is gone or switched off
    """
    from app.database import async_session
    from app.models.staff import Staff

    async with async_session() as db:
        await set_facility_context(db, str(current_user.facility_id))
        staff = await db.get(Staff, current_user.user_id)

    if staff is None or staff.is_deleted or not staff.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_INTERNAL_REVOKED_MESSAGE,
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = security_dependency,
) -> CurrentUser:
    cached_user = getattr(request.state, "current_user", None)
    if isinstance(cached_user, CurrentUser):
        return cached_user

    if settings.beta_public_access:
        current_user = _beta_current_user()
        await _set_request_facility_context(request, current_user)
        return current_user

    token = _extract_token(request, credentials)
    if token is None:
        raise _auth_error("Missing authentication token")

    try:
        if settings.auth_provider == "internal":
            from app.auth.internal_tokens import (
                decode_token as decode_internal_token,
            )

            payload = decode_internal_token(token)
            current_user = _current_user_from_payload(payload)
            # The token proves who signed in, not that HR still wants them in.
            # Re-read the employee record so deactivation stops an in-flight
            # session at once rather than when the token expires.
            await _assert_internal_account_active(current_user)
        else:
            from app.auth.keycloak import decode_token as decode_keycloak_token

            payload = await decode_keycloak_token(token)
            current_user = _current_user_from_payload(payload)
            # The token names a Keycloak user; every clinical table names a
            # staff record. Re-key before anything downstream reads the id.
            current_user = await _bind_keycloak_identity(current_user)
    except (JWTError, ValueError, TypeError):
        raise _auth_error() from None

    await _set_request_facility_context(request, current_user)
    return current_user


current_user_dependency = Depends(get_current_user)


def require_roles(*required_roles: str):
    """
    Build a dependency that admits the named roles, and every administrator.

    Role names are compared case-insensitively, so ``Lab_Tech`` on a staff
    record and ``lab_tech`` in a token are the same role. Administrator roles
    always pass: an administrator owns every module, and without that bypass a
    ``super_admin`` was refused by the endpoints that name ``admin`` and
    ``facility_admin`` - the platform owner was locked out of more of the
    hospital than a nurse was.

    Vendor-only endpoints, which no hospital administrator may reach, use
    ``require_platform_roles`` instead; that gate has no bypass.

    @param required_roles: Role names the endpoint belongs to
    @returns A FastAPI dependency returning the authenticated user
    """
    from app.auth.permissions import SUPERUSER_ROLES, normalise_role

    wanted = {normalise_role(role) for role in required_roles}

    async def role_checker(
        current_user: CurrentUser = current_user_dependency,
    ) -> CurrentUser:
        held = {normalise_role(role) for role in current_user.roles}
        if held & wanted or held & SUPERUSER_ROLES:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {', '.join(required_roles)}",
        )

    return role_checker


def require_platform_roles(*required_roles: str):
    """
    Build a dependency that admits only the named roles, with no exceptions.

    ``require_roles`` lets an administrator through anywhere; this gate does
    not, because the endpoints it guards act on the platform rather than on one
    hospital - issuing licences, publishing application updates, approving a
    facility's onboarding. A ``facility_admin`` holds every permission inside
    their own facility and none of these.

    @param required_roles: Role names the endpoint is restricted to
    @returns A FastAPI dependency returning the authenticated user
    """
    from app.auth.permissions import normalise_role

    wanted = {normalise_role(role) for role in required_roles}

    async def role_checker(
        current_user: CurrentUser = current_user_dependency,
    ) -> CurrentUser:
        held = {normalise_role(role) for role in current_user.roles}
        if not (held & wanted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker


async def require_patient_read(
    current_user: CurrentUser = current_user_dependency,
) -> CurrentUser:
    """
    Gate reads of patient PII / FHIR resources (Kenya DPA minimum-necessary).

    When ``PATIENT_READ_ROLES`` is unset the facility has not opted into
    role-restricted reads, so any authenticated facility user is allowed
    (unchanged behaviour). When it is set, the caller must hold at least
    one of the configured roles.

    @param current_user: Authenticated user from JWT
    @returns The current user when permitted
    @raises HTTPException 403: If read gating is enabled and the user lacks a role
    """
    allowed = settings.patient_read_role_list
    if not allowed:
        return current_user
    if not any(role in current_user.roles for role in allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not permitted to read patient records at this facility",
        )
    return current_user
