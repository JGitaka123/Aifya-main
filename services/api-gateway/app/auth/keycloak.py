from time import monotonic
from typing import Any

import httpx
from jose import JWTError, jwt

from app.config import settings

_JWKS_CACHE_TTL_SECONDS = 300
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_fetched_at = 0.0


def _realm_url() -> str:
    return f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"


async def get_keycloak_public_keys(force_refresh: bool = False) -> dict[str, Any]:
    """
    Fetch and cache Keycloak realm public keys for JWT verification.

    @param force_refresh: Ignore the cache and fetch current keys
    @returns JWKS dict
    """
    global _jwks_cache, _jwks_cache_fetched_at
    cache_is_fresh = monotonic() - _jwks_cache_fetched_at < _JWKS_CACHE_TTL_SECONDS
    if not force_refresh and _jwks_cache is not None and cache_is_fresh:
        return _jwks_cache

    certs_url = f"{_realm_url()}/protocol/openid-connect/certs"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(certs_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_fetched_at = monotonic()
    except httpx.HTTPError as exc:
        raise JWTError("Unable to fetch Keycloak JWKS") from exc

    return _jwks_cache


def _select_jwk(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = jwks.get("keys", [])

    if kid:
        for key in keys:
            if isinstance(key, dict) and key.get("kid") == kid:
                return key
        raise JWTError("Token signing key not found")

    if len(keys) == 1 and isinstance(keys[0], dict):
        return keys[0]

    raise JWTError("Token signing key is ambiguous")


async def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a Keycloak JWT access token.

    @param token: Bearer token string
    @returns Decoded token payload
    @raises JWTError: If token is invalid or expired
    """
    jwks = await get_keycloak_public_keys()
    try:
        signing_key = _select_jwk(token, jwks)
    except JWTError as exc:
        if str(exc) != "Token signing key not found":
            raise
        jwks = await get_keycloak_public_keys(force_refresh=True)
        signing_key = _select_jwk(token, jwks)

    return jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.keycloak_client_id,
        issuer=_realm_url(),
    )


def invalidate_jwks_cache() -> None:
    """Clear the cached JWKS cache; call when Keycloak keys rotate."""
    global _jwks_cache, _jwks_cache_fetched_at
    _jwks_cache = None
    _jwks_cache_fetched_at = 0.0
