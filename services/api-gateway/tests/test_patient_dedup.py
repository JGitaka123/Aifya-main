"""D7: duplicate-patient detection before registration."""

import pytest
from httpx import AsyncClient


def _patient(**overrides: object) -> dict:
    base = {
        "first_name": "Wanjala",
        "last_name": "Simiyu",
        "date_of_birth": "1988-03-12",
        "gender": "male",
        "national_id": "20304050",
        "phone_number": "0712000333",
    }
    base.update(overrides)
    return base


async def _register(client: AsyncClient, **overrides: object) -> dict:
    resp = await client.post("/api/v1/patients", json=_patient(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_duplicate_national_id_detected(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/api/v1/patients/check-duplicates",
        json={
            "first_name": "Wanjala",
            "last_name": "Simiyu",
            "date_of_birth": "1988-03-12",
            "national_id": "20304050",
            "phone_number": "0799999999",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_duplicates"] is True
    assert "national_id" in body["matches"][0]["match_reasons"]


@pytest.mark.asyncio
async def test_duplicate_name_dob_and_phone_detected(client: AsyncClient) -> None:
    """The QA case: a second 'Wanjala Simiyu' with the same phone number."""
    await _register(client)
    resp = await client.post(
        "/api/v1/patients/check-duplicates",
        json={
            "first_name": "wanjala",  # different case, still a match
            "last_name": "SIMIYU",
            "date_of_birth": "1988-03-12",
            "phone_number": "0712000333",
            "national_id": None,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_duplicates"] is True
    reasons = body["matches"][0]["match_reasons"]
    assert "phone_number" in reasons
    assert "name_dob" in reasons


@pytest.mark.asyncio
async def test_distinct_patient_not_flagged(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/api/v1/patients/check-duplicates",
        json={
            "first_name": "Grace",
            "last_name": "Achieng",
            "date_of_birth": "1995-07-01",
            "phone_number": "0701234567",
            "national_id": "31313131",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_duplicates"] is False
    assert body["matches"] == []
