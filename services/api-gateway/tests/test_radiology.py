import uuid

import pytest
from httpx import AsyncClient


# -- Helpers ------------------------------------------------------------------


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Radiology",
            "last_name": "TestPatient",
            "date_of_birth": "1985-03-10",
            "gender": "female",
            "phone_number": "0711100100",
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
            "chief_complaint": "Chest pain on exertion",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_imaging_order(
    client: AsyncClient,
    patient_id: str,
    encounter_id: str,
) -> dict[str, object]:
    """Create an imaging order and return the full response body.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @param encounter_id: Encounter UUID string
    @returns Order response dict
    """
    response = await client.post(
        "/api/v1/radiology/orders",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "modality": "xray",
            "body_part": "chest",
            "study_description": "Chest X-ray PA and lateral",
            "clinical_indication": "Rule out pneumonia",
            "priority": "routine",
        },
    )
    assert response.status_code == 201
    return response.json()


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_radiology_summary(client: AsyncClient) -> None:
    """Test fetching radiology summary stats."""
    response = await client.get("/api/v1/radiology/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Worklist -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_radiology_worklist_empty(client: AsyncClient) -> None:
    """Test radiology worklist returns empty when no orders exist."""
    response = await client.get("/api/v1/radiology/worklist")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Orders: create -----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_imaging_order(client: AsyncClient) -> None:
    """Test creating an imaging order with patient and encounter."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        "/api/v1/radiology/orders",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "modality": "xray",
            "body_part": "chest",
            "study_description": "Chest X-ray PA and lateral",
            "clinical_indication": "Rule out pneumonia",
            "priority": "routine",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_id"] == encounter_id
    assert data["modality"] == "xray"
    assert data["body_part"] == "chest"
    assert data["study_description"] == "Chest X-ray PA and lateral"
    assert data["clinical_indication"] == "Rule out pneumonia"
    assert data["priority"] == "routine"
    assert data["order_number"].startswith("IMG-")
    assert data["status"] == "ordered"
    assert "id" in data
    assert "created_at" in data


# -- Orders: get detail -------------------------------------------------------


@pytest.mark.asyncio
async def test_get_imaging_order(client: AsyncClient) -> None:
    """Test fetching a single imaging order by ID."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    order = await _create_imaging_order(client, patient_id, encounter_id)
    order_id: str = order["id"]  # type: ignore[assignment]

    response = await client.get(f"/api/v1/radiology/orders/{order_id}")

    assert response.status_code == 200
    # Detail endpoint wraps the order with its result and patient info.
    data: dict[str, object] = response.json()
    order_data: dict[str, object] = data["order"]  # type: ignore[assignment]
    assert order_data["id"] == order_id
    assert order_data["modality"] == "xray"
    assert data["result"] is None  # No report entered yet


# -- Orders: 404 --------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_imaging_order_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent imaging order."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/radiology/orders/{fake_id}")

    assert response.status_code == 404


# -- Orders: schedule ---------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_imaging_order(client: AsyncClient) -> None:
    """Test scheduling an imaging order with datetime and room."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    order = await _create_imaging_order(client, patient_id, encounter_id)
    order_id: str = order["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/radiology/orders/{order_id}/schedule",
        json={
            "scheduled_at": "2026-07-10T10:00:00",
            "room": "Radiology Room 1",
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == order_id
    assert data["scheduled_at"] is not None
    assert data["room"] == "Radiology Room 1"


# -- Orders: perform ----------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_imaging_order(client: AsyncClient) -> None:
    """Test marking an imaging order as performed."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    order = await _create_imaging_order(client, patient_id, encounter_id)
    order_id: str = order["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/radiology/orders/{order_id}/perform",
        json={
            "accession_number": "ACC-2026-001",
            "notes": "PA and lateral views obtained",
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == order_id
    assert data["accession_number"] == "ACC-2026-001"
