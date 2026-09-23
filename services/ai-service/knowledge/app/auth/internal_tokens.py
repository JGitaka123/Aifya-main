"""Verify Aifya-internal HS256 tokens.

Mirrors ``services/api-gateway/app/auth/internal_tokens.py``. The web app's
``/api/knowledge`` proxy forwards the httpOnly ``access_token`` cookie as a
Bearer header, and that token is minted by the api-gateway when
``AUTH_PROVIDER=internal`` (the default). The knowledge service therefore has
to verify the same HS256 signature with the same ``SECRET_KEY`` instead of a
Keycloak RS256 realm key, or every proxied upload returns 401.
"""

from typing import Any

from jose import JWTError, jwt

_ALGORITHM = "HS256"


def decode_internal_token(token: str, secret_key: str) -> dict[str, Any]:
    """
    Verify the signature and expiry of an Aifya-internal access token.

    @param token: Raw JWT from the Authorization header
    @param secret_key: Shared HS256 signing secret (api-gateway SECRET_KEY)
    @returns Verified claims
    @raises JWTError: Bad signature/expiry, blank secret, or wrong provider/type
    """
    if not secret_key:
        raise JWTError(
            "SECRET_KEY is not configured, cannot verify internal tokens"
        )

    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[_ALGORITHM],
        options={"verify_aud": False},
    )
    if payload.get("provider") != "internal":
        raise JWTError("Not an internal token")
    if payload.get("typ") != "access":
        raise JWTError("Expected an access token")
    return payload
