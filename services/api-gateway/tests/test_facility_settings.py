"""Settings -> Facility: partial updates must survive real form input.

The facility form submits every text input, including the ones the operator
left blank. A blank is a legitimate value -- it means "clear this field" -- so
the endpoint has to accept it rather than answering with a 422 the operator
cannot act on. These tests pin that behaviour, including the case where the
JSON body never arrives at all.
"""

import pytest
from httpx import AsyncClient

from app.models.facility import Facility
from tests.conftest import FACILITY_ID, session_factory

#: Exactly what the Settings -> Facility form posts, blanks and all.
FORM_PAYLOAD = {
    "name": "Aifya Test Hospital",
    "facility_type": "hospital",
    "keph_level": "",
    "mfl_code": "",
    "county": "Nairobi",
    "sub_county": "",
    "ward": "",
    "phone": "",
    "email": "",
    "website": "",
    "timezone": "Africa/Nairobi",
    "currency": "KES",
    "physical_address": "",
}


async def _seed_facility(**overrides: object) -> None:
    """
    Create the facility row the test JWT points at.

    @param overrides: Column values to override on the seeded row
    """
    async with session_factory() as db:
        values: dict[str, object] = {
            "id": FACILITY_ID,
            "name": "Aifya Test Hospital",
            "code": "AIFYA-TEST",
            "facility_type": "hospital",
            "timezone": "Africa/Nairobi",
            "currency": "KES",
            "onboarding_status": "approved",
            "is_active": True,
        }
        values.update(overrides)
        db.add(Facility(**values))
        await db.commit()


@pytest.mark.asyncio
async def test_blank_form_values_clear_optional_fields(
    client: AsyncClient,
) -> None:
    """A blank optional input clears the column instead of returning 422."""
    await _seed_facility(phone="0700000000", email="desk@aifya.health")

    response = await client.patch("/api/v1/facility", json=FORM_PAYLOAD)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phone"] is None
    assert body["email"] is None
    assert body["keph_level"] is None
    assert body["county"] == "Nairobi"


@pytest.mark.asyncio
async def test_blank_numeric_field_is_accepted(client: AsyncClient) -> None:
    """A cleared latitude box is a clear, not a bad float."""
    await _seed_facility()

    response = await client.patch(
        "/api/v1/facility", json={"name": "Aifya Test Hospital", "latitude": ""}
    )

    assert response.status_code == 200, response.text
    assert response.json()["latitude"] is None


@pytest.mark.asyncio
async def test_partial_update_leaves_other_fields_alone(
    client: AsyncClient,
) -> None:
    """A field the operator did not touch is not blanked out."""
    await _seed_facility(county="Kiambu", phone="0700000000")

    response = await client.patch(
        "/api/v1/facility", json={"county": "Nairobi"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["county"] == "Nairobi"
    assert body["phone"] == "0700000000"
    assert body["name"] == "Aifya Test Hospital"


@pytest.mark.asyncio
async def test_blank_identity_field_is_rejected_with_a_reason(
    client: AsyncClient,
) -> None:
    """A blank name is refused by name, not swallowed or saved as empty."""
    await _seed_facility()

    response = await client.patch("/api/v1/facility", json={"name": "   "})

    assert response.status_code == 422
    assert "name" in response.text


@pytest.mark.asyncio
async def test_missing_body_explains_itself(client: AsyncClient) -> None:
    """A dropped payload is reported plainly instead of as a bare 422."""
    await _seed_facility()

    response = await client.patch("/api/v1/facility")

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
