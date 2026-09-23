"""Tests for platform Keycloak SSO token acceptance in the scribe backend."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt
from jose.backends import RSAKey
from jose.constants import ALGORITHMS

from app.auth import auth as auth_module
from app.auth.auth import _map_keycloak_roles, decode_keycloak_token
from app.models import UserRole

_RSA_PRIVATE_PEM = None
_JWKS = None


def _ensure_keypair() -> tuple[str, dict]:
    """Generate (once) an RSA keypair and matching JWKS for tests.

    @returns: Tuple of (private key PEM, JWKS dict)
    """
    global _RSA_PRIVATE_PEM, _JWKS
    if _RSA_PRIVATE_PEM is None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _RSA_PRIVATE_PEM = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        public_jwk = RSAKey(_RSA_PRIVATE_PEM, ALGORITHMS.RS256).public_key().to_dict()
        public_jwk["kid"] = "test-key"
        public_jwk["use"] = "sig"
        _JWKS = {"keys": [public_jwk]}
    return _RSA_PRIVATE_PEM, _JWKS


def _make_keycloak_token(
    roles: list[str],
    facility_id: str = "00000000-0000-0000-0000-000000000001",
    issuer: str | None = None,
) -> str:
    """Sign a Keycloak-shaped RS256 token with the test keypair.

    @param roles: Realm roles to embed
    @param facility_id: facility_id claim
    @param issuer: Override issuer (defaults to the configured realm URL)
    @returns: Signed JWT string
    """
    private_pem, _ = _ensure_keypair()
    settings = auth_module.settings
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "kc-user-1",
        "iss": issuer
        or f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}",
        "aud": settings.keycloak_audience,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "name": "Dr Test",
        "facility_id": facility_id,
        "realm_access": {"roles": roles},
    }
    return jose_jwt.encode(
        claims, private_pem, algorithm="RS256", headers={"kid": "test-key"}
    )


@pytest.fixture(autouse=True)
def _keycloak_test_config(monkeypatch: pytest.MonkeyPatch):
    """Point the auth module at a fake Keycloak and stub the JWKS fetch."""
    _, jwks = _ensure_keypair()
    monkeypatch.setattr(auth_module.settings, "keycloak_url", "http://keycloak.test")
    monkeypatch.setattr(auth_module.settings, "keycloak_realm", "aifya")
    monkeypatch.setattr(auth_module, "_keycloak_jwks_cache", None)

    async def fake_jwks(force_refresh: bool = False) -> dict:
        return jwks

    monkeypatch.setattr(auth_module, "_get_keycloak_jwks", fake_jwks)
    yield


@pytest.mark.asyncio
async def test_keycloak_doctor_token_maps_to_clinician() -> None:
    """A platform doctor token is accepted and mapped to the clinician role."""
    token = _make_keycloak_token(["doctor"])
    payload = await decode_keycloak_token(token)
    assert payload["sub"] == "kc-user-1"
    assert payload["role"] == UserRole.CLINICIAN.value
    assert payload["type"] == "access"
    assert payload["facility_id"] == "00000000-0000-0000-0000-000000000001"
    assert payload["auth_source"] == "keycloak"


@pytest.mark.asyncio
async def test_keycloak_admin_precedence_over_clinician() -> None:
    """facility_admin outranks doctor when both roles are present."""
    token = _make_keycloak_token(["doctor", "facility_admin"])
    payload = await decode_keycloak_token(token)
    assert payload["role"] == UserRole.FACILITY_ADMIN.value


@pytest.mark.asyncio
async def test_keycloak_unmapped_role_rejected() -> None:
    """A token whose roles map to nothing is rejected."""
    from jose import JWTError

    token = _make_keycloak_token(["lab_tech"])
    with pytest.raises(JWTError):
        await decode_keycloak_token(token)


@pytest.mark.asyncio
async def test_keycloak_wrong_issuer_rejected() -> None:
    """A token from a different issuer must not validate."""
    from jose import JWTError

    token = _make_keycloak_token(["doctor"], issuer="http://evil.example/realms/aifya")
    with pytest.raises(JWTError):
        await decode_keycloak_token(token)


def test_role_mapping_table() -> None:
    """Spot-check the role precedence mapping."""
    assert (
        _map_keycloak_roles({"realm_access": {"roles": ["cashier"]}})
        == UserRole.BILLING_ADMIN
    )
    assert (
        _map_keycloak_roles({"realm_access": {"roles": ["nurse"]}})
        == UserRole.CLINICIAN
    )
    assert _map_keycloak_roles({"realm_access": {"roles": []}}) is None
