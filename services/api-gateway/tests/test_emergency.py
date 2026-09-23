import uuid

import pytest
from httpx import AsyncClient


async def _create_patient(client: AsyncClient) -> str:
    """Helper to create a patient and return the patient ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    payload = {
        "first_name": "James",
        "last_name": "Mwangi",
        "date_of_birth": "1970-01-01",
        "gender": "male",
        "phone_number": "0700000000",
    }
    response = await client.post("/api/v1/patients", json=payload)
    assert response.status_code == 201
    data: dict[str, str] = response.json()
    return data["id"]


async def _create_emergency_visit(client: AsyncClient, patient_id: str) -> dict[str, object]:
    """Helper to register an emergency visit and return the response data.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Emergency visit response dict
    """
    payload = {
        "patient_id": patient_id,
        "chief_complaint": "Chest pain",
        "arrival_mode": "ambulance",
        "notes": "Acute chest pain, diaphoresis",
    }
    response = await client.post("/api/v1/emergency/visits", json=payload)
    assert response.status_code == 201
    data: dict[str, object] = response.json()
    return data


# ── Summary ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_emergency_summary(client: AsyncClient) -> None:
    """Test GET /emergency/summary returns department stats."""
    response = await client.get("/api/v1/emergency/summary")
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert "total_today" in data
    assert "awaiting_triage" in data
    assert "in_treatment" in data
    assert "discharged_today" in data


# ── Queue ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_emergency_queue_empty(client: AsyncClient) -> None:
    """Test GET /emergency/queue returns empty list when no visits exist."""
    response = await client.get("/api/v1/emergency/queue")
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── Register Visit ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_emergency_visit(client: AsyncClient) -> None:
    """Test POST /emergency/visits creates a new emergency visit."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)

    assert "id" in visit
    assert visit["patient_id"] == patient_id
    assert visit["chief_complaint"] == "Chest pain"
    assert visit["arrival_mode"] == "ambulance"
    assert visit["notes"] == "Acute chest pain, diaphoresis"
    assert visit["status"] == "arrived"
    assert visit["visit_number"].startswith("ER-")
    assert "created_at" in visit


# ── Visit Detail ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_emergency_visit(client: AsyncClient) -> None:
    """Test GET /emergency/visits/{id} returns the visit detail."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)
    visit_id: str = str(visit["id"])

    response = await client.get(f"/api/v1/emergency/visits/{visit_id}")
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == visit_id
    assert data["chief_complaint"] == "Chest pain"
    assert data["patient_id"] == patient_id


@pytest.mark.asyncio
async def test_get_emergency_visit_not_found(client: AsyncClient) -> None:
    """Test GET /emergency/visits/{fake_id} returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/emergency/visits/{fake_id}")
    assert response.status_code == 404
    data: dict[str, object] = response.json()
    assert data["detail"] == "Emergency visit not found"


# ── Triage ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_triage_emergency_visit(client: AsyncClient) -> None:
    """Test POST /emergency/visits/{id}/triage performs SATS triage."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)
    visit_id: str = str(visit["id"])

    triage_payload: dict[str, object] = {
        "triage_category": "urgent",
        "triage_score": 3,
        "triage_vitals": {
            "bp": "140/90",
            "hr": 110,
            "rr": 22,
            "temp": 37.8,
            "spo2": 95,
        },
    }
    response = await client.post(
        f"/api/v1/emergency/visits/{visit_id}/triage",
        json=triage_payload,
    )
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == visit_id
    assert data["triage_category"] == "urgent"
    assert data["triage_color"] == "orange"
    assert data["triage_score"] == 3
    assert data["status"] == "triaged"


# ── Assign Doctor ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_doctor_to_emergency_visit(client: AsyncClient) -> None:
    """Test POST /emergency/visits/{id}/assign-doctor assigns a doctor."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)
    visit_id: str = str(visit["id"])

    assign_payload: dict[str, str] = {
        "doctor_id": "00000000-0000-0000-0000-000000000002",
    }
    response = await client.post(
        f"/api/v1/emergency/visits/{visit_id}/assign-doctor",
        json=assign_payload,
    )
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == visit_id
    assert data["assigned_doctor_id"] == "00000000-0000-0000-0000-000000000002"
    assert data["status"] == "in_treatment"


# ── Disposition ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_disposition(client: AsyncClient) -> None:
    """Test POST /emergency/visits/{id}/disposition records patient disposition."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)
    visit_id: str = str(visit["id"])

    disposition_payload: dict[str, str] = {
        "disposition": "admit",
        "disposition_notes": "Admit to cardiology ward",
    }
    response = await client.post(
        f"/api/v1/emergency/visits/{visit_id}/disposition",
        json=disposition_payload,
    )
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == visit_id
    assert data["disposition"] == "admit"
    assert data["disposition_notes"] == "Admit to cardiology ward"
    assert data["status"] == "admitted"


# ── Queue After Registration ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_includes_registered_visit(client: AsyncClient) -> None:
    """Test GET /emergency/queue includes a newly registered visit."""
    patient_id = await _create_patient(client)
    visit = await _create_emergency_visit(client, patient_id)

    response = await client.get("/api/v1/emergency/queue")
    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["total"] == 1
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["id"] == visit["id"]
