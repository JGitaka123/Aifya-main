import uuid

import pytest
from httpx import AsyncClient

LEAD_SURGEON_ID = "00000000-0000-0000-0000-000000000002"


# -- Helpers ------------------------------------------------------------------


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Theatre",
            "last_name": "TestPatient",
            "date_of_birth": "1992-11-05",
            "gender": "male",
            "phone_number": "0711200300",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    """Create a test encounter and return its ID.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Acute abdominal pain, right lower quadrant",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_theatre(client: AsyncClient) -> str:
    """Create a theatre and return its ID.

    @param client: Async HTTP test client
    @returns Theatre UUID string
    """
    response = await client.post(
        "/api/v1/theatre/theatres",
        json={
            "name": "OR-1",
            "theatre_type": "general",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_case(
    client: AsyncClient,
    patient_id: str,
    encounter_id: str,
    theatre_id: str,
) -> dict[str, object]:
    """Schedule a theatre case and return the full response body.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @param encounter_id: Encounter UUID string
    @param theatre_id: Theatre UUID string
    @returns Case response dict
    """
    response = await client.post(
        "/api/v1/theatre/cases",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "theatre_id": theatre_id,
            "procedure_name": "Appendectomy",
            "priority": "emergency",
            "anaesthesia_type": "general",
            "scheduled_date": "2026-05-01T10:00:00Z",
            "estimated_duration_min": 90,
            "lead_surgeon_id": LEAD_SURGEON_ID,
        },
    )
    assert response.status_code == 201
    return response.json()


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_theatre_summary(client: AsyncClient) -> None:
    """Test fetching theatre summary stats."""
    response = await client.get("/api/v1/theatre/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["total_theatres"] == 0
    assert data["scheduled_today"] == 0
    assert data["emergency_cases"] == 0


# -- Theatres: empty list -----------------------------------------------------


@pytest.mark.asyncio
async def test_list_theatres_empty(client: AsyncClient) -> None:
    """Test listing theatres returns empty when none exist."""
    response = await client.get("/api/v1/theatre/theatres")

    assert response.status_code == 200
    data: list[object] = response.json()
    assert data == []


# -- Theatres: create ---------------------------------------------------------


@pytest.mark.asyncio
async def test_create_theatre(client: AsyncClient) -> None:
    """Test creating a theatre room."""
    response = await client.post(
        "/api/v1/theatre/theatres",
        json={
            "name": "OR-1",
            "theatre_type": "general",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["name"] == "OR-1"
    assert data["theatre_type"] == "general"
    assert data["status"] == "available"
    assert str(data["code"]).startswith("OT-")
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_theatre_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects an invalid theatre type."""
    response = await client.post(
        "/api/v1/theatre/theatres",
        json={
            "name": "OR-X",
            "theatre_type": "veterinary",
        },
    )

    assert response.status_code == 422


# -- Cases: empty list --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_cases_empty(client: AsyncClient) -> None:
    """Test listing theatre cases returns empty when none exist."""
    response = await client.get("/api/v1/theatre/cases")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["total"] == 0
    assert data["items"] == []


# -- Cases: schedule ----------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_case(client: AsyncClient) -> None:
    """Test scheduling a theatre case with patient, encounter, and theatre."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    theatre_id = await _create_theatre(client)

    response = await client.post(
        "/api/v1/theatre/cases",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "theatre_id": theatre_id,
            "procedure_name": "Appendectomy",
            "priority": "emergency",
            "anaesthesia_type": "general",
            "scheduled_date": "2026-05-01T10:00:00Z",
            "estimated_duration_min": 90,
            "lead_surgeon_id": LEAD_SURGEON_ID,
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_id"] == encounter_id
    assert data["theatre_id"] == theatre_id
    assert data["procedure_name"] == "Appendectomy"
    assert data["priority"] == "emergency"
    assert data["anaesthesia_type"] == "general"
    assert str(data["scheduled_date"]).startswith("2026-05-01")
    assert data["estimated_duration_min"] == 90
    assert data["lead_surgeon_id"] == LEAD_SURGEON_ID
    assert data["status"] == "scheduled"
    assert str(data["case_number"]).startswith("SC-")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_schedule_case_invalid_priority(client: AsyncClient) -> None:
    """Test validation rejects an invalid case priority."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/theatre/cases",
        json={
            "patient_id": patient_id,
            "procedure_name": "Appendectomy",
            "priority": "routine",
            "scheduled_date": "2026-05-01T10:00:00Z",
            "lead_surgeon_id": LEAD_SURGEON_ID,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_schedule_case_missing_surgeon(client: AsyncClient) -> None:
    """Test validation rejects a case without the required lead surgeon."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/theatre/cases",
        json={
            "patient_id": patient_id,
            "procedure_name": "Appendectomy",
            "scheduled_date": "2026-05-01T10:00:00Z",
        },
    )

    assert response.status_code == 422


# -- Cases: get detail --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_case(client: AsyncClient) -> None:
    """Test fetching a single theatre case by ID."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    theatre_id = await _create_theatre(client)
    case = await _create_case(client, patient_id, encounter_id, theatre_id)
    case_id: str = case["id"]  # type: ignore[assignment]

    response = await client.get(f"/api/v1/theatre/cases/{case_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == case_id
    assert data["procedure_name"] == "Appendectomy"


# -- Cases: 404 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_case_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent theatre case."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/theatre/cases/{fake_id}")

    assert response.status_code == 404


# -- Cases: operative notes ---------------------------------------------------


@pytest.mark.asyncio
async def test_add_operative_notes(client: AsyncClient) -> None:
    """Test adding operative notes to a theatre case."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    theatre_id = await _create_theatre(client)
    case = await _create_case(client, patient_id, encounter_id, theatre_id)
    case_id: str = case["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/theatre/cases/{case_id}/operative-notes",
        json={
            "operative_findings": "Inflamed appendix with localized peritonitis",
            "operative_notes": "Laparoscopic appendectomy performed without incident",
            "complications": "None",
            "blood_loss_ml": 50,
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["operative_findings"] == "Inflamed appendix with localized peritonitis"
    assert data["complications"] == "None"
    assert data["blood_loss_ml"] == 50
