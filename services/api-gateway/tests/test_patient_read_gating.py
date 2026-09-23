"""Tests for config-driven patient PII read gating (Kenya DPA)."""

import pytest
from httpx import AsyncClient

from app.config import settings


async def _create_patient(client: AsyncClient) -> str:
    """Register a patient and return its id."""
    resp = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Read",
            "last_name": "Gate",
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "phone_number": "0722111222",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_reads_open_when_unset(client: AsyncClient) -> None:
    """With PATIENT_READ_ROLES unset, any authenticated user may read."""
    patient_id = await _create_patient(client)
    resp = await client.get(f"/api/v1/patients/{patient_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_allowed_with_matching_role(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user holding a configured role may still read."""
    patient_id = await _create_patient(client)
    # Test user has roles ["admin", "doctor"].
    monkeypatch.setattr(settings, "patient_read_roles", "doctor,records")
    resp = await client.get(f"/api/v1/patients/{patient_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_read_blocked_without_matching_role(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A user lacking every configured role is denied patient reads."""
    patient_id = await _create_patient(client)
    monkeypatch.setattr(settings, "patient_read_roles", "records,cashier")
    resp = await client.get(f"/api/v1/patients/{patient_id}")
    assert resp.status_code == 403

    listing = await client.get("/api/v1/patients")
    assert listing.status_code == 403
