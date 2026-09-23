from datetime import datetime, timedelta
from typing import Optional, Any, Dict

import httpx
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from structlog import get_logger

from app.config import get_settings
from app.models import UserRole

logger = get_logger(__name__)
settings = get_settings()

# Keycloak realm-role → scribe role mapping, checked in precedence order.
_KEYCLOAK_ROLE_PRECEDENCE: list[tuple[str, UserRole]] = [
    ("super_admin", UserRole.SUPERADMIN),
    ("facility_admin", UserRole.FACILITY_ADMIN),
    ("admin", UserRole.FACILITY_ADMIN),
    ("billing_clerk", UserRole.BILLING_ADMIN),
    ("cashier", UserRole.BILLING_ADMIN),
    ("doctor", UserRole.CLINICIAN),
    ("clinical_officer", UserRole.CLINICIAN),
    ("nurse", UserRole.CLINICIAN),
    ("midwife", UserRole.CLINICIAN),
]

_keycloak_jwks_cache: Optional[Dict[str, Any]] = None


async def _get_keycloak_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch and cache the Keycloak realm JWKS for RS256 verification.

    @param force_refresh: Ignore the cache and refetch (key rotation).
    @returns: JWKS dict usable by jose.jwt.decode.
    """
    global _keycloak_jwks_cache
    if _keycloak_jwks_cache is not None and not force_refresh:
        return _keycloak_jwks_cache

    certs_url = (
        f"{settings.keycloak_url.rstrip('/')}/realms/"
        f"{settings.keycloak_realm}/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(certs_url)
        response.raise_for_status()
        _keycloak_jwks_cache = response.json()
        return _keycloak_jwks_cache


def _map_keycloak_roles(payload: Dict[str, Any]) -> Optional[UserRole]:
    """Map Keycloak realm/client roles onto a scribe UserRole.

    @param payload: Decoded Keycloak token payload.
    @returns: Highest-precedence mapped role, or None if nothing maps.
    """
    roles: set[str] = set(payload.get("realm_access", {}).get("roles", []))
    for client_access in payload.get("resource_access", {}).values():
        roles.update(client_access.get("roles", []))

    for keycloak_role, scribe_role in _KEYCLOAK_ROLE_PRECEDENCE:
        if keycloak_role in roles:
            return scribe_role
    return None


async def decode_keycloak_token(token: str) -> Dict[str, Any]:
    """Validate a platform Keycloak RS256 token and adapt its claims to
    the payload shape the scribe app expects.

    @param token: Raw RS256 JWT issued by the Aifya Keycloak realm.
    @returns: Scribe-shaped payload (sub, role, type, facility_id).
    @raises JWTError: If the signature/issuer/audience is invalid or no
        Keycloak role maps to a scribe role.
    """
    issuer = (
        f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"
    )
    jwks = await _get_keycloak_jwks()
    try:
        payload: Dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=issuer,
        )
    except JWTError:
        # Retry once with fresh keys in case Keycloak rotated them.
        jwks = await _get_keycloak_jwks(force_refresh=True)
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_audience,
            issuer=issuer,
        )

    role = _map_keycloak_roles(payload)
    if role is None:
        raise JWTError("No Keycloak role maps to a scribe role")

    return {
        "sub": payload["sub"],
        "role": role.value,
        "type": "access",
        "facility_id": payload.get("facility_id"),
        "name": payload.get("name"),
        "auth_source": "keycloak",
    }

# Use bcrypt with salt rounds=12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# OAuth2 scheme for dependency injection in FastAPI routers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_str}/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(
    subject: str,
    role: str,
    facility_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived access token with specific scopes/roles.

    @param subject: User ID to encode as the JWT subject claim.
    @param role: User role string (e.g. 'clinician', 'superadmin').
    @param facility_id: Optional facility ID for multi-tenancy filtering.
    @param expires_delta: Optional custom expiration duration.
    @returns: Encoded JWT access token string.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    if facility_id:
        to_encode["facility_id"] = facility_id

    encoded_jwt: str = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token.

    @param subject: User ID to encode as the JWT subject claim.
    @returns: Encoded JWT refresh token string.
    """
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    encoded_jwt: str = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

async def get_current_user_token_payload(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Validate an access token from the request and return the decoded payload.

    Only tokens with type='access' (or legacy tokens without a type claim) are
    accepted. Refresh tokens are explicitly rejected to prevent token-type
    confusion attacks.

    @param token: Bearer token extracted via OAuth2 scheme.
    @returns: Decoded JWT payload dictionary.
    @raises HTTPException: 401 if the token is invalid, expired, or is a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Platform SSO: RS256 tokens from the Aifya Keycloak realm are
        # accepted when Keycloak is configured; local HS256 tokens keep
        # working unchanged.
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "RS256":
            if not settings.keycloak_url:
                logger.warning("keycloak_token_but_sso_disabled")
                raise credentials_exception
            return await decode_keycloak_token(token)

        payload: Dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Reject refresh tokens used as access tokens
        token_type: str = payload.get("type", "access")
        if token_type != "access":
            logger.warning("wrong_token_type", expected="access", got=token_type, user_id=user_id)
            raise credentials_exception

        return payload
    except JWTError as e:
        logger.warning("invalid_token", error=str(e))
        raise credentials_exception


async def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token, ensuring it has type='refresh'.

    @param token: Raw JWT refresh token string.
    @returns: Decoded JWT payload dictionary.
    @raises HTTPException: 401 if the token is invalid, expired, or not a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: Dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        token_type: str = payload.get("type", "")
        if token_type != "refresh":
            logger.warning("wrong_token_type", expected="refresh", got=token_type, user_id=user_id)
            raise credentials_exception

        return payload
    except JWTError as e:
        logger.warning("invalid_refresh_token", error=str(e))
        raise credentials_exception

class RoleChecker:
    """
    Dependency injection class to enforce proper Role Based Access Control (RBAC) matrix.
    Usage: Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))
    """
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(self, payload: Dict[str, Any] = Depends(get_current_user_token_payload)):
        role_str = payload.get("role")
        if not role_str:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role claim missing in token")
            
        try:
            user_role = UserRole(role_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role in token")

        if user_role not in self.allowed_roles:
            logger.warning("auth_forbidden", user_id=payload.get("sub"), attempted_role=user_role, required_roles=[r.value for r in self.allowed_roles])
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")
            
        return payload
