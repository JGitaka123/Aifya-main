import uuid

import pytest
from httpx import AsyncClient

# Dentist UUID used for visits/plans (no staff FK validation in the service layer).
DENTIST_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000002"))


# -- Helpers ------------------------------------------------------------------


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Dental",
            "last_name": "TestPatient",
            "date_of_birth": "2000-02-14",
            "gender": "female",
            "phone_number": "0711400500",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_visit(client: AsyncClient, patient_id: str) -> dict[str, object]:
    """Create a dental visit and return the full response body.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Visit response dict
    """
    response = await client.post(
        "/api/v1/dental/visits",
        json={
            "patient_id": patient_id,
            "dentist_id": DENTIST_ID,
            "chief_complaint": "Routine checkup",
            "procedures": {"performed": ["examination", "cleaning"], "teeth": [11, 12]},
            "notes": "Routine dental checkup",
        },
    )
    assert response.status_code == 201
    return response.json()


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dental_summary(client: AsyncClient) -> None:
    """Test fetching dental summary stats."""
    response = await client.get("/api/v1/dental/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["total_patients"] == 0
    assert data["today_visits"] == 0
    assert data["pending_treatments"] == 0
    assert data["completed_today"] == 0


# -- Visits: empty list -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_visits_empty(client: AsyncClient) -> None:
    """Test listing dental visits returns empty when none exist."""
    response = await client.get("/api/v1/dental/visits")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# -- Charts: get/create -------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dental_chart(client: AsyncClient) -> None:
    """Test getting or creating a dental chart for a patient."""
    patient_id = await _create_patient(client)

    response = await client.get(f"/api/v1/dental/charts/{patient_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    # A fresh chart starts with no charted teeth
    assert data["teeth"] == {}


# -- Charts: update -----------------------------------------------------------


@pytest.mark.asyncio
async def test_update_dental_chart(client: AsyncClient) -> None:
    """Test updating a dental chart with tooth status data."""
    patient_id = await _create_patient(client)

    # Ensure chart exists
    await client.get(f"/api/v1/dental/charts/{patient_id}")

    teeth: dict[str, object] = {
        "11": {"status": "caries", "notes": "Occlusal caries"},
    }
    response = await client.put(
        f"/api/v1/dental/charts/{patient_id}",
        json={
            "teeth": teeth,
            "periodontal_status": "gingivitis",
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["teeth"] == teeth
    assert data["periodontal_status"] == "gingivitis"


# -- Visits: create -----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_visit(client: AsyncClient) -> None:
    """Test creating a dental visit record."""
    patient_id = await _create_patient(client)

    procedures: dict[str, object] = {
        "performed": ["examination", "cleaning"],
        "teeth": [11, 12],
    }
    response = await client.post(
        "/api/v1/dental/visits",
        json={
            "patient_id": patient_id,
            "dentist_id": DENTIST_ID,
            "chief_complaint": "Routine checkup",
            "examination_findings": "No acute pathology",
            "procedures": procedures,
            "diagnosis": "Healthy dentition",
            "notes": "Routine dental checkup",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["dentist_id"] == DENTIST_ID
    assert data["chief_complaint"] == "Routine checkup"
    assert data["examination_findings"] == "No acute pathology"
    assert data["procedures"] == procedures
    assert data["diagnosis"] == "Healthy dentition"
    assert data["notes"] == "Routine dental checkup"
    assert data["status"] == "scheduled"
    visit_number: str = data["visit_number"]  # type: ignore[assignment]
    assert visit_number.startswith("DV-")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_visit_missing_required_fields(client: AsyncClient) -> None:
    """Test that creating a visit without patient_id/dentist_id returns 422."""
    response = await client.post(
        "/api/v1/dental/visits",
        json={"notes": "Missing required identifiers"},
    )

    assert response.status_code == 422


# -- Visits: get detail -------------------------------------------------------


@pytest.mark.asyncio
async def test_get_visit(client: AsyncClient) -> None:
    """Test fetching a single dental visit by ID."""
    patient_id = await _create_patient(client)
    visit = await _create_visit(client, patient_id)
    visit_id: str = visit["id"]  # type: ignore[assignment]

    response = await client.get(f"/api/v1/dental/visits/{visit_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == visit_id
    assert data["visit_number"] == visit["visit_number"]
    assert data["notes"] == "Routine dental checkup"


# -- Visits: 404 --------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_visit_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent dental visit."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/dental/visits/{fake_id}")

    assert response.status_code == 404


# -- Treatment Plans: empty list ----------------------------------------------


@pytest.mark.asyncio
async def test_list_treatment_plans_empty(client: AsyncClient) -> None:
    """Test listing dental treatment plans returns empty when none exist."""
    response = await client.get("/api/v1/dental/treatment-plans")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# -- Treatment Plans: create --------------------------------------------------


@pytest.mark.asyncio
async def test_create_treatment_plan(client: AsyncClient) -> None:
    """Test creating a dental treatment plan."""
    patient_id = await _create_patient(client)

    plan_items: dict[str, object] = {
        "items": [
            {
                "procedure": "filling",
                "tooth": 11,
                "estimated_cost": 250000,
            },
        ],
    }
    response = await client.post(
        "/api/v1/dental/treatment-plans",
        json={
            "patient_id": patient_id,
            "dentist_id": DENTIST_ID,
            "diagnosis": "Occlusal caries on 11",
            "plan_items": plan_items,
            "total_estimated_cost": 250000,
            "notes": "Composite filling recommended",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["dentist_id"] == DENTIST_ID
    assert data["diagnosis"] == "Occlusal caries on 11"
    assert data["plan_items"] == plan_items
    assert data["total_estimated_cost"] == 250000
    assert data["status"] == "draft"
    assert data["notes"] == "Composite filling recommended"
    plan_number: str = data["plan_number"]  # type: ignore[assignment]
    assert plan_number.startswith("DP-")
    assert "id" in data
    assert "created_at" in data
