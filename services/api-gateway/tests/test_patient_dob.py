"""D8: date-of-birth validation on patient registration."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _payload(dob: str) -> dict:
    return {
        "first_name": "Dob",
        "last_name": "Check",
        "date_of_birth": dob,
        "gender": "male",
        "phone_number": "0722000111",
    }


@pytest.mark.asyncio
async def test_future_dob_rejected(client: AsyncClient) -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = await client.post("/api/v1/patients", json=_payload(tomorrow))
    assert resp.status_code == 422
    assert "future" in resp.text.lower()


@pytest.mark.asyncio
async def test_implausibly_old_dob_rejected(client: AsyncClient) -> None:
    ancient = date(date.today().year - 121, 1, 1).isoformat()
    resp = await client.post("/api/v1/patients", json=_payload(ancient))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_valid_dob_accepted(client: AsyncClient) -> None:
    dob = date(1990, 5, 15).isoformat()
    resp = await client.post("/api/v1/patients", json=_payload(dob))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_today_dob_accepted(client: AsyncClient) -> None:
    """A newborn registered on the day of birth is valid."""
    resp = await client.post("/api/v1/patients", json=_payload(date.today().isoformat()))
    assert resp.status_code == 201
