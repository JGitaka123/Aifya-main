import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def patient_id(client: AsyncClient) -> str:
    """Create a test patient and return their ID."""
    response = await client.post("/api/v1/patients", json={
        "first_name": "Agnes",
        "last_name": "Wanjiru",
        "date_of_birth": "1988-07-22",
        "gender": "female",
        "phone_number": "0711222333",
    })
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_encounter(client: AsyncClient, patient_id: str) -> None:
    """Test creating a new OPD encounter."""
    response = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Persistent headache for 3 days",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_type"] == "opd"
    assert data["chief_complaint"] == "Persistent headache for 3 days"
    # New encounters enter the OPD queue as "waiting"; a doctor moves them
    # to "in_consultation" via /queue/call-next.
    assert data["status"] == "waiting"
    assert data["queue_number"] >= 1
    assert "id" in data


@pytest.mark.asyncio
async def test_create_encounter_missing_patient(client: AsyncClient) -> None:
    """Test encounter creation requires patient_id."""
    response = await client.post("/api/v1/encounters", json={
        "encounter_type": "opd",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_encounter(client: AsyncClient, patient_id: str) -> None:
    """Test fetching a single encounter."""
    create_resp = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Fever",
    })
    enc_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/encounters/{enc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == enc_id


@pytest.mark.asyncio
async def test_get_encounter_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent encounter."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/encounters/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_patient_queue(client: AsyncClient, patient_id: str) -> None:
    """Test fetching the OPD queue."""
    await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Cough",
    })

    response = await client.get("/api/v1/encounters/queue")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_add_vitals(client: AsyncClient, patient_id: str) -> None:
    """Test adding vital signs to an encounter."""
    enc_resp = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Routine checkup",
    })
    enc_id = enc_resp.json()["id"]

    response = await client.post(f"/api/v1/encounters/{enc_id}/vitals", json={
        "encounter_id": enc_id,
        "patient_id": patient_id,
        "temperature": 37.2,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "heart_rate": 72,
        "respiratory_rate": 18,
        "oxygen_saturation": 98,
        "weight_kg": 65.5,
        "height_cm": 165.0,
    })

    assert response.status_code == 201
    data = response.json()
    assert data["temperature"] == 37.2
    assert data["systolic_bp"] == 120
    assert data["oxygen_saturation"] == 98
    assert data["bmi"] is not None  # Should auto-calculate


@pytest.mark.asyncio
async def test_add_diagnosis(client: AsyncClient, patient_id: str) -> None:
    """Test adding a diagnosis to an encounter."""
    enc_resp = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Cough and fever",
    })
    enc_id = enc_resp.json()["id"]

    response = await client.post(f"/api/v1/encounters/{enc_id}/diagnoses", json={
        "encounter_id": enc_id,
        "patient_id": patient_id,
        "icd10_code": "J06.9",
        "icd10_description": "Acute upper respiratory infection, unspecified",
        "diagnosis_type": "primary",
        "certainty": "confirmed",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["icd10_code"] == "J06.9"
    assert data["diagnosis_type"] == "primary"
    assert data["certainty"] == "confirmed"


@pytest.mark.asyncio
async def test_add_prescription(client: AsyncClient, patient_id: str) -> None:
    """Test adding a prescription to an encounter."""
    enc_resp = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Malaria symptoms",
    })
    enc_id = enc_resp.json()["id"]

    response = await client.post(f"/api/v1/encounters/{enc_id}/prescriptions", json={
        "encounter_id": enc_id,
        "patient_id": patient_id,
        "drug_name": "Artemether-Lumefantrine",
        "generic_name": "AL",
        "dosage": "80/480mg",
        "frequency": "bd",
        "duration_days": 3,
        "quantity": 24,
        "route": "oral",
        "instructions": "Take with food. Complete full course.",
    })

    assert response.status_code == 201
    # Response envelope includes drug interaction check results; the
    # prescription is null only when blocked by a critical interaction.
    data = response.json()
    assert data["blocked"] is False
    assert isinstance(data["interactions"], list)
    prescription = data["prescription"]
    assert prescription is not None
    assert prescription["drug_name"] == "Artemether-Lumefantrine"
    assert prescription["dosage"] == "80/480mg"
    assert prescription["frequency"] == "bd"
    assert prescription["duration_days"] == 3
    assert prescription["status"] == "pending"


@pytest.mark.asyncio
async def test_create_lab_order(client: AsyncClient, patient_id: str) -> None:
    """Test ordering lab tests from an encounter."""
    enc_resp = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Suspected malaria",
    })
    enc_id = enc_resp.json()["id"]

    response = await client.post(f"/api/v1/encounters/{enc_id}/lab-orders", json={
        "encounter_id": enc_id,
        "patient_id": patient_id,
        "priority": "urgent",
        "tests": [
            {"test_name": "Malaria RDT", "test_code": "MAL-RDT"},
            {"test_name": "Complete Blood Count", "test_code": "CBC"},
        ],
        "clinical_info": "Fever x3 days, suspect P. falciparum",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ordered"
    assert data["order_number"].startswith("LAB-")
