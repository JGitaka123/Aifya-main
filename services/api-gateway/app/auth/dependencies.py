import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
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
        await set_facility_context(db, str(current_user.facility_id))


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
        else:
            from app.auth.keycloak import decode_token as decode_keycloak_token

            payload = await decode_keycloak_token(token)
        current_user = _current_user_from_payload(payload)
    except (JWTError, ValueError, TypeError):
        raise _auth_error() from None

    await _set_request_facility_context(request, current_user)
    return current_user


current_user_dependency = Depends(get_current_user)


def require_roles(*required_roles: str):
    async def role_checker(
        current_user: CurrentUser = current_user_dependency,
    ) -> CurrentUser:
        if not any(role in current_user.roles for role in required_roles):
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
