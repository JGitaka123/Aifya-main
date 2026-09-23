"""Issue and verify Aifya-internal HS256 tokens.

Used when AUTH_PROVIDER=internal so the branded Aifya login/registration
forms can authenticate directly against Aifya's own database without a
Keycloak server. Tokens carry the same claims the rest of the API expects
(sub, facility_id, email, realm_access.roles) so existing role checks and
tenant scoping keep working unchanged.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = 12 * 60
REFRESH_TOKEN_TTL_DAYS = 30


def _issue(
    *,
    subject: UUID,
    facility_id: UUID,
    email: str,
    name: str,
    roles: list[str],
    token_type: str,
) -> str:
    now = datetime.now(timezone.utc)
    if token_type == "refresh":
        ttl = timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    else:
        ttl = timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)
    roles = list(roles)
    claims: dict[str, Any] = {
        "sub": str(subject),
        "facility_id": str(facility_id),
        "email": email,
        "name": name,
        "roles": roles,
        "realm_access": {"roles": roles},
        "provider": "internal",
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(claims, settings.secret_key, algorithm=_ALGORITHM)


def issue_access_token(
    *, subject: UUID, facility_id: UUID, email: str, name: str, roles: list[str]
) -> str:
    """Issue a short-lived access token for an internal account."""
    return _issue(
        subject=subject,
        facility_id=facility_id,
        email=email,
        name=name,
        roles=roles,
        token_type="access",
    )


def issue_refresh_token(
    *, subject: UUID, facility_id: UUID, email: str, name: str, roles: list[str]
) -> str:
    """Issue a long-lived refresh token for an internal account."""
    return _issue(
        subject=subject,
        facility_id=facility_id,
        email=email,
        name=name,
        roles=roles,
        token_type="refresh",
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Verify an internal token signature/expiry.

    @param token: JWT to verify
    @param expected_type: "access" or "refresh"
    @returns Verified claims
    @raises JWTError: Invalid signature, expired, or wrong provider/type
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[_ALGORITHM],
        options={"verify_aud": False},
    )
    if payload.get("provider") != "internal":
        raise JWTError("Not an internal token")
    if payload.get("typ") != expected_type:
        raise JWTError("Expected " + expected_type + " token")
    return payload
