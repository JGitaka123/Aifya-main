"""Facility onboarding (gated sign-up) + staff invite provisioning tests.

Keycloak I/O is faked so the flows are exercised without a live Keycloak.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.main import app
from app.utils.keycloak_admin import get_keycloak_admin_client


class _FakeAdminClient:
    """Records create_user calls; pretends to be a configured Keycloak admin."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.is_configured = True

    async def create_user(self, **kwargs) -> str:  # noqa: ANN003
        self.calls.append(kwargs)
        return str(uuid.uuid4())


@pytest.fixture
def fake_admin() -> _FakeAdminClient:
    fake = _FakeAdminClient()
    app.dependency_overrides[get_keycloak_admin_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_keycloak_admin_client, None)


def _signup_payload(**overrides: object) -> dict:
    base = {
        "facility_name": "QA Test Clinic",
        "facility_type": "clinic",
        "county": "Nairobi",
        "admin_first_name": "Grace",
        "admin_last_name": "Mwangi",
        "admin_email": "grace.admin@example.com",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_facility_signup_creates_pending(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/onboarding/facility-signup", json=_signup_payload()
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["onboarding_status"] == "pending"
    assert "pending review" in body["message"].lower()


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_name(client: AsyncClient) -> None:
    await client.post("/api/v1/onboarding/facility-signup", json=_signup_payload())
    dup = await client.post(
        "/api/v1/onboarding/facility-signup", json=_signup_payload()
    )
    assert dup.status_code == 400
    assert "already exists" in dup.text.lower()


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_mfl_code(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/onboarding/facility-signup",
        json=_signup_payload(mfl_code="099345"),
    )
    assert first.status_code == 201, first.text

    dup = await client.post(
        "/api/v1/onboarding/facility-signup",
        json=_signup_payload(facility_name="Second MFL Clinic", mfl_code="099345"),
    )
    assert dup.status_code == 400, dup.text
    assert "mfl code" in dup.text.lower()


@pytest.mark.asyncio
async def test_signup_rejects_non_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/onboarding/facility-signup",
        json=_signup_payload(admin_email="notanemail"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_pending_then_approve_provisions_admin(
    client: AsyncClient, fake_admin: _FakeAdminClient
) -> None:
    signup = await client.post(
        "/api/v1/onboarding/facility-signup",
        json=_signup_payload(facility_name="Approve Test Hospital"),
    )
    facility_id = signup.json()["facility_id"]

    # It shows up in the pending queue (admin-only; test user has 'admin').
    pending = await client.get("/api/v1/onboarding/pending")
    assert pending.status_code == 200
    assert any(f["id"] == facility_id for f in pending.json())

    # Approve → activates + provisions the facility-admin Keycloak user.
    approve = await client.post(
        f"/api/v1/onboarding/facilities/{facility_id}/approve"
    )
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["onboarding_status"] == "approved"
    assert body["admin_user_created"] is True
    assert len(fake_admin.calls) == 1
    assert fake_admin.calls[0]["roles"] == ["facility_admin"]
    assert fake_admin.calls[0]["facility_id"] == facility_id


@pytest.mark.asyncio
async def test_staff_invite_creates_user_and_staff(
    client: AsyncClient, fake_admin: _FakeAdminClient
) -> None:
    resp = await client.post(
        "/api/v1/onboarding/staff-invite",
        json={
            "email": "nurse.jane@example.com",
            "first_name": "Jane",
            "last_name": "Otieno",
            "role": "nurse",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "nurse"
    assert body["email"] == "nurse.jane@example.com"
    assert len(fake_admin.calls) == 1
    assert fake_admin.calls[0]["roles"] == ["nurse"]


@pytest.mark.asyncio
async def test_staff_invite_rejects_bad_role(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/onboarding/staff-invite",
        json={
            "email": "x@example.com",
            "first_name": "X",
            "last_name": "Y",
            "role": "wizard",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_staff_invite_503_when_provisioning_unconfigured(
    client: AsyncClient,
) -> None:
    """With no admin credentials configured, invite returns a clear 503."""
    resp = await client.post(
        "/api/v1/onboarding/staff-invite",
        json={
            "email": "z@example.com",
            "first_name": "Z",
            "last_name": "Q",
            "role": "doctor",
        },
    )
    assert resp.status_code == 503
