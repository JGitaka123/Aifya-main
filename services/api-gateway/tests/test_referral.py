import uuid

import pytest
from httpx import AsyncClient

from app.models.facility import Facility
from tests.conftest import session_factory as _session_factory

# -- Helpers ------------------------------------------------------------------


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Referral",
            "last_name": "TestPatient",
            "date_of_birth": "1975-08-20",
            "gender": "male",
            "phone_number": "0711300400",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_referral(client: AsyncClient, patient_id: str) -> dict[str, object]:
    """Create a referral and return the full response body.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Referral response dict
    """
    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "direction": "outgoing",
            "referral_type": "external",
            "referring_facility_name": "County Hospital",
            "receiving_facility_name": "National Hospital",
            "reason": "Advanced cardiac care",
            "urgency": "urgent",
            "clinical_notes": "Patient with unstable angina",
        },
    )
    assert response.status_code == 201
    return response.json()


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_referral_summary(client: AsyncClient) -> None:
    """Test fetching referral summary stats."""
    response = await client.get("/api/v1/referrals/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["total_referrals"] == 0
    assert data["outgoing"] == 0
    assert data["incoming"] == 0
    assert data["pending"] == 0


# -- Referrals: empty list ----------------------------------------------------


@pytest.mark.asyncio
async def test_list_referrals_empty(client: AsyncClient) -> None:
    """Test listing referrals returns empty when none exist."""
    response = await client.get("/api/v1/referrals")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# -- Referrals: create --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_referral(client: AsyncClient) -> None:
    """Test creating a patient referral."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "direction": "outgoing",
            "referral_type": "external",
            "referring_facility_name": "County Hospital",
            "receiving_facility_name": "National Hospital",
            "receiving_facility_mfl": "13023",
            "reason": "Advanced cardiac care",
            "urgency": "urgent",
            "clinical_notes": "Patient with unstable angina",
            "diagnosis": "Unstable angina",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["direction"] == "outgoing"
    assert data["referral_type"] == "external"
    assert data["referring_facility_name"] == "County Hospital"
    assert data["receiving_facility_name"] == "National Hospital"
    assert data["receiving_facility_mfl"] == "13023"
    assert data["reason"] == "Advanced cardiac care"
    assert data["urgency"] == "urgent"
    assert data["clinical_notes"] == "Patient with unstable angina"
    assert data["diagnosis"] == "Unstable angina"
    assert data["status"] == "draft"
    referral_number: str = data["referral_number"]  # type: ignore[assignment]
    assert referral_number.startswith("REF-")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_referral_missing_reason(client: AsyncClient) -> None:
    """Test that creating a referral without the required reason returns 422."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "direction": "outgoing",
            "referral_type": "external",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_referral_invalid_type(client: AsyncClient) -> None:
    """Test that an invalid referral_type value is rejected with 422."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "referral_type": "specialist",
            "reason": "Advanced cardiac care",
        },
    )

    assert response.status_code == 422


# -- Referrals: get detail ----------------------------------------------------


@pytest.mark.asyncio
async def test_get_referral(client: AsyncClient) -> None:
    """Test fetching a single referral by ID."""
    patient_id = await _create_patient(client)
    referral = await _create_referral(client, patient_id)
    referral_id: str = referral["id"]  # type: ignore[assignment]

    response = await client.get(f"/api/v1/referrals/{referral_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == referral_id
    assert data["reason"] == "Advanced cardiac care"
    assert data["referral_number"] == referral["referral_number"]


# -- Referrals: 404 -----------------------------------------------------------


@pytest.mark.asyncio
async def test_get_referral_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent referral."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/referrals/{fake_id}")

    assert response.status_code == 404


# -- Referrals: update status -------------------------------------------------


@pytest.mark.asyncio
async def test_update_referral_status(client: AsyncClient) -> None:
    """Test updating the status of a referral."""
    patient_id = await _create_patient(client)
    referral = await _create_referral(client, patient_id)
    referral_id: str = referral["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/referrals/{referral_id}/status",
        json={
            "status": "accepted",
            "response_notes": "Will review patient",
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == referral_id
    assert data["status"] == "accepted"
    assert data["response_notes"] == "Will review patient"
    # Accepting a referral stamps the response date
    assert data["response_date"] is not None


@pytest.mark.asyncio
async def test_update_referral_status_invalid_value(client: AsyncClient) -> None:
    """Test that an invalid status value is rejected with 422."""
    patient_id = await _create_patient(client)
    referral = await _create_referral(client, patient_id)
    referral_id: str = referral["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/referrals/{referral_id}/status",
        json={"status": "archived"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_referral_status_not_found(client: AsyncClient) -> None:
    """Test 404 when updating status of a non-existent referral."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/referrals/{fake_id}/status",
        json={"status": "accepted"},
    )

    assert response.status_code == 404


# -- Facility lookup ----------------------------------------------------------


async def _seed_facility(name: str, mfl_code: str | None) -> str:
    """Insert a facility into the register and return its ID.

    @param name: Facility name
    @param mfl_code: Kenya Master Facility List code
    @returns Facility UUID string
    """
    facility_id = uuid.uuid4()
    async with _session_factory() as session:
        session.add(
            Facility(
                id=facility_id,
                name=name,
                code=f"TST-{facility_id.hex[:8].upper()}",
                facility_type="hospital",
                keph_level="4",
                mfl_code=mfl_code,
                county="Nairobi",
                sub_county="Westlands",
                onboarding_status="approved",
            )
        )
        await session.commit()
    return str(facility_id)


@pytest.mark.asyncio
async def test_facility_lookup_finds_registered_facility(
    client: AsyncClient,
) -> None:
    """Test that a registered referral destination is found, with its MFL code."""
    name = f"Referral Target {uuid.uuid4().hex[:6]}"
    facility_id = await _seed_facility(name, "MFL-TEST-001")

    response = await client.get(
        "/api/v1/referrals/facility-lookup", params={"q": name[:20]}
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    items = data["items"]
    assert isinstance(items, list)
    match = next(item for item in items if item["id"] == facility_id)
    assert match["name"] == name
    assert match["mfl_code"] == "MFL-TEST-001"
    assert match["county"] == "Nairobi"


@pytest.mark.asyncio
async def test_facility_lookup_matches_mfl_code(client: AsyncClient) -> None:
    """Test that the register can be searched by MFL code."""
    name = f"MFL Search {uuid.uuid4().hex[:6]}"
    await _seed_facility(name, "MFL-TEST-002")

    response = await client.get(
        "/api/v1/referrals/facility-lookup", params={"q": "MFL-TEST-002"}
    )

    assert response.status_code == 200
    assert any(item["name"] == name for item in response.json()["items"])


@pytest.mark.asyncio
async def test_facility_lookup_unknown_returns_empty(client: AsyncClient) -> None:
    """Test that an unregistered destination comes back empty, not as an error."""
    response = await client.get(
        "/api/v1/referrals/facility-lookup",
        params={"q": f"Nonexistent {uuid.uuid4().hex}"},
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_facility_lookup_requires_minimum_query(client: AsyncClient) -> None:
    """Test that a one-letter query is rejected before it hits the register."""
    response = await client.get(
        "/api/v1/referrals/facility-lookup", params={"q": "K"}
    )

    assert response.status_code == 422
