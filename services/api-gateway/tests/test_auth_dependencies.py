import base64
import json
import time
import uuid
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from starlette.requests import Request

from app.auth import keycloak
from app.auth.dependencies import CurrentUser, get_current_user
from app.middleware.facility_context import set_facility_context

USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FACILITY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ISSUER = "http://keycloak.test/realms/aifya"
CLIENT_ID = "aifya-api"


def _request(cookie_token: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie_token:
        headers.append((b"cookie", f"access_token={cookie_token}".encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
        }
    )


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sub": str(USER_ID),
        "facility_id": str(FACILITY_ID),
        "email": "clinician@aifya.health",
        "name": "Aifya Clinician",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": ["doctor", "nurse"]},
        "resource_access": {CLIENT_ID: {"roles": ["doctor", "ward_admin"]}},
    }
    payload.update(overrides)
    return payload


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unsigned_token(payload: dict[str, Any]) -> str:
    header = {"alg": "none", "kid": "test-key", "typ": "JWT"}
    return ".".join(
        [
            _b64url(json.dumps(header).encode()),
            _b64url(json.dumps(payload).encode()),
            "",
        ]
    )


def _rsa_keypair(kid: str) -> tuple[bytes, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_numbers = private_key.public_key().public_numbers()

    def encode_int(value: int) -> str:
        return _b64url(value.to_bytes((value.bit_length() + 7) // 8, "big"))

    return private_pem, {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": encode_int(public_numbers.n),
        "e": encode_int(public_numbers.e),
    }


def _set_keycloak_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keycloak.settings, "keycloak_url", "http://keycloak.test")
    monkeypatch.setattr(keycloak.settings, "keycloak_realm", "aifya")
    monkeypatch.setattr(keycloak.settings, "keycloak_client_id", CLIENT_ID)


@pytest.mark.asyncio
async def test_decode_token_rejects_unsigned_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_keycloak_settings(monkeypatch)
    _private_pem, public_jwk = _rsa_keypair("test-key")

    async def fake_jwks() -> dict[str, Any]:
        return {"keys": [public_jwk]}

    monkeypatch.setattr(keycloak, "get_keycloak_public_keys", fake_jwks)

    with pytest.raises(JWTError):
        await keycloak.decode_token(_unsigned_token(_payload()))


@pytest.mark.asyncio
async def test_decode_token_rejects_forged_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_keycloak_settings(monkeypatch)
    _, trusted_public_jwk = _rsa_keypair("test-key")
    attacker_private_pem, _attacker_public_jwk = _rsa_keypair("test-key")

    async def fake_jwks() -> dict[str, Any]:
        return {"keys": [trusted_public_jwk]}

    monkeypatch.setattr(keycloak, "get_keycloak_public_keys", fake_jwks)
    forged_token = jwt.encode(
        _payload(),
        attacker_private_pem,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    with pytest.raises(JWTError):
        await keycloak.decode_token(forged_token)


@pytest.mark.asyncio
async def test_decode_token_refreshes_jwks_on_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_keycloak_settings(monkeypatch)
    _, old_public_jwk = _rsa_keypair("old-key")
    new_private_pem, new_public_jwk = _rsa_keypair("new-key")
    calls: list[bool] = []

    async def fake_jwks(force_refresh: bool = False) -> dict[str, Any]:
        calls.append(force_refresh)
        return {"keys": [new_public_jwk if force_refresh else old_public_jwk]}

    monkeypatch.setattr(keycloak, "get_keycloak_public_keys", fake_jwks)
    token = jwt.encode(
        _payload(),
        new_private_pem,
        algorithm="RS256",
        headers={"kid": "new-key"},
    )

    payload = await keycloak.decode_token(token)

    assert payload["sub"] == str(USER_ID)
    assert calls == [False, True]


@pytest.mark.asyncio
async def test_get_current_user_builds_user_from_verified_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_decode_token(token: str) -> dict[str, Any]:
        assert token == "verified-token"
        return _payload()

    monkeypatch.setattr("app.auth.dependencies.decode_token", fake_decode_token)

    user = await get_current_user(
        _request(),
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="verified-token"),
    )

    assert user == CurrentUser(
        user_id=USER_ID,
        facility_id=FACILITY_ID,
        email="clinician@aifya.health",
        roles=["doctor", "nurse", "ward_admin"],
        name="Aifya Clinician",
    )


@pytest.mark.asyncio
async def test_get_current_user_accepts_cookie_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_decode_token(token: str) -> dict[str, Any]:
        assert token == "cookie-token"
        return _payload(realm_access={"roles": ["doctor"]}, resource_access={})

    monkeypatch.setattr("app.auth.dependencies.decode_token", fake_decode_token)

    user = await get_current_user(_request("cookie-token"), None)

    assert user.user_id == USER_ID
    assert user.facility_id == FACILITY_ID
    assert user.roles == ["doctor"]


@pytest.mark.asyncio
async def test_get_current_user_does_not_default_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_decode_token(_token: str) -> dict[str, Any]:
        return _payload(realm_access={}, resource_access={})

    monkeypatch.setattr("app.auth.dependencies.decode_token", fake_decode_token)

    user = await get_current_user(
        _request(),
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="verified-token"),
    )

    assert user.roles == []


@pytest.mark.asyncio
async def test_get_current_user_sets_facility_context_on_live_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        pass

    seen: dict[str, Any] = {}

    async def fake_decode_token(_token: str) -> dict[str, Any]:
        return _payload()

    async def fake_set_facility_context(session: FakeSession, facility_id: str) -> None:
        seen["session"] = session
        seen["facility_id"] = facility_id

    monkeypatch.setattr("app.auth.dependencies.AsyncSession", FakeSession)
    monkeypatch.setattr("app.auth.dependencies.decode_token", fake_decode_token)
    monkeypatch.setattr(
        "app.auth.dependencies.set_facility_context",
        fake_set_facility_context,
    )

    request = _request()
    request.state.db = FakeSession()

    user = await get_current_user(
        request,
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="verified-token"),
    )

    assert seen == {"session": request.state.db, "facility_id": str(FACILITY_ID)}
    assert request.state.current_user is user
    assert request.state.facility_id == FACILITY_ID


@pytest.mark.asyncio
async def test_set_facility_context_records_sqlite_session_info() -> None:
    class FakeDialect:
        name = "sqlite"

    class FakeBind:
        dialect = FakeDialect()

    class FakeSession:
        info: dict[str, str]

        def __init__(self) -> None:
            self.info = {}

        def get_bind(self) -> FakeBind:
            return FakeBind()

        async def execute(self, *_args: Any, **_kwargs: Any) -> None:
            raise AssertionError(
                "SQLite sessions should not execute PostgreSQL RLS SQL"
            )

    session = FakeSession()

    await set_facility_context(session, str(FACILITY_ID))  # type: ignore[arg-type]

    assert session.info["facility_id"] == str(FACILITY_ID)
