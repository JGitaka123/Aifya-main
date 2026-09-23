"""
Auth dependencies for the Knowledge RAG service.
Reuses Keycloak JWT validation from the api-gateway pattern.
Extracts facility_id for multi-tenant query isolation.
"""

import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer(auto_error=False)

_jwks_cache: dict[str, dict] | None = None


async def _get_keycloak_public_key() -> dict:
    """
    Fetch Keycloak JWKS for RS256 token verification.
    Cached after first fetch.

    @returns JWKS dict for jose.jwt.decode
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def _decode_token(token: str) -> dict:
    """
    Decode and validate the bearer token.

    ``AUTH_PROVIDER=internal`` (the default, and what the api-gateway uses)
    verifies the shared HS256 secret; ``keycloak`` verifies an RS256 token
    against the realm JWKS. These must stay in step with the api-gateway,
    otherwise every request the web proxy forwards is rejected as invalid.

    @param token: Raw JWT string
    @returns Decoded payload dict
    @raises JWTError: If token is invalid
    @raises httpx.HTTPError: If the Keycloak JWKS endpoint is unreachable
    """
    if settings.auth_provider == "internal":
        from app.auth.internal_tokens import decode_internal_token

        return decode_internal_token(token, settings.secret_key)

    jwks = await _get_keycloak_public_key()
    return jwt.decode(
        token,
        jwks,
        algorithms=[settings.jwt_algorithm],
        audience="account",
        options={"verify_aud": False},
    )


@dataclass(frozen=True)
class CurrentUser:
    """
    Authenticated user extracted from Keycloak JWT.
    Contains facility_id for multi-tenant query scoping.
    """

    user_id: uuid.UUID
    facility_id: uuid.UUID
    email: str
    roles: list[str]
    name: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """
    FastAPI dependency: extract and validate the current user from JWT.
    Every database/Qdrant query MUST use the returned facility_id.

    @param credentials: Bearer token from Authorization header
    @returns CurrentUser with user_id, facility_id, roles
    @raises HTTPException 401: If token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await _decode_token(credentials.credentials)
    except (JWTError, httpx.HTTPError) as exc:
        logger.warning("auth_token_invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str or not isinstance(user_id_str, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    facility_id_str = payload.get("facility_id")
    if not facility_id_str or not isinstance(facility_id_str, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing facility_id claim",
        )

    realm_access = payload.get("realm_access", {})
    roles: list[str] = []
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles", [])  # type: ignore[assignment]

    return CurrentUser(
        user_id=uuid.UUID(str(user_id_str)),
        facility_id=uuid.UUID(str(facility_id_str)),
        email=str(payload.get("email", "")),
        roles=roles,
        name=str(payload.get("name", payload.get("preferred_username", ""))),
    )


def require_roles(*required_roles: str):
    """
    Factory for role-based access control dependency.
    Usage: Depends(require_roles("doctor", "admin"))

    @param required_roles: One or more role names — user must have at least one
    @returns Dependency function that validates roles
    """

    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        """
        Check that the current user has at least one of the required roles.

        @param current_user: Authenticated user
        @returns CurrentUser if authorized
        @raises HTTPException 403: If user lacks required roles
        """
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker
