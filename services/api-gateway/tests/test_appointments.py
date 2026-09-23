import uuid

import pytest
from httpx import AsyncClient

DOCTOR_ID = "00000000-0000-0000-0000-000000000002"


async def _create_patient(client: AsyncClient) -> str:
    """
    Create a test patient and return the patient ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post("/api/v1/patients", json={
        "first_name": "Amina",
        "last_name": "Ochieng",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "phone_number": "0700000000",
    })
    assert response.status_code == 201
    return response.json()["id"]


async def _create_appointment(client: AsyncClient, patient_id: str) -> dict:
    """
    Create a test appointment and return the response data.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Appointment response dict
    """
    payload = {
        "patient_id": patient_id,
        "doctor_id": DOCTOR_ID,
        "appointment_date": "2026-05-01",
        "start_time": "09:00",
        "end_time": "09:30",
        "visit_reason": "Follow-up checkup",
        "appointment_type": "follow_up",
    }
    response = await client.post("/api/v1/appointments/", json=payload)
    assert response.status_code == 201
    return response.json()


# ── Summary ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_appointment_summary(client: AsyncClient) -> None:
    """Test appointment summary returns correct structure with zero counts."""
    response = await client.get("/api/v1/appointments/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_today"] == 0
    assert data["scheduled"] == 0
    assert data["confirmed"] == 0
    assert data["checked_in"] == 0
    assert data["completed_today"] == 0
    assert data["cancelled_today"] == 0
    assert data["no_show_today"] == 0


# ── List (empty) ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_appointments_empty(client: AsyncClient) -> None:
    """Test listing appointments when none exist."""
    response = await client.get("/api/v1/appointments/")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── Create ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_appointment(client: AsyncClient) -> None:
    """Test creating an appointment for an existing patient."""
    patient_id = await _create_patient(client)
    data = await _create_appointment(client, patient_id)

    assert data["patient_id"] == patient_id
    assert data["doctor_id"] == DOCTOR_ID
    assert data["appointment_date"] == "2026-05-01"
    assert data["start_time"] == "09:00:00"
    assert data["end_time"] == "09:30:00"
    assert data["visit_reason"] == "Follow-up checkup"
    assert data["appointment_type"] == "follow_up"
    assert data["status"] == "scheduled"
    assert data["priority"] == "routine"
    assert data["reminder_sent"] is False
    assert data["is_recurring"] is False
    assert "id" in data
    assert "appointment_number" in data
    assert "created_at" in data
    assert "booked_by" in data


# ── Get by ID ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_appointment(client: AsyncClient) -> None:
    """Test fetching a single appointment by ID."""
    patient_id = await _create_patient(client)
    created = await _create_appointment(client, patient_id)
    appointment_id = created["id"]

    response = await client.get(f"/api/v1/appointments/{appointment_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == appointment_id
    assert data["patient_id"] == patient_id
    assert data["doctor_id"] == DOCTOR_ID
    assert data["appointment_type"] == "follow_up"


# ── Get non-existent ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_appointment_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent appointment."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/appointments/{fake_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Appointment not found"


# ── Update (cancel) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_appointment_cancel(client: AsyncClient) -> None:
    """Test cancelling an appointment with a reason."""
    patient_id = await _create_patient(client)
    created = await _create_appointment(client, patient_id)
    appointment_id = created["id"]

    update_payload = {
        "status": "cancelled",
        "cancellation_reason": "Patient request",
    }
    response = await client.patch(
        f"/api/v1/appointments/{appointment_id}",
        json=update_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == appointment_id
    assert data["status"] == "cancelled"
    assert data["cancellation_reason"] == "Patient request"


# ── Check-in ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_in_appointment(client: AsyncClient) -> None:
    """Test checking in a patient for their appointment."""
    patient_id = await _create_patient(client)
    created = await _create_appointment(client, patient_id)
    appointment_id = created["id"]

    response = await client.post(
        f"/api/v1/appointments/{appointment_id}/check-in",
        json={"notes": "Patient arrived on time"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == appointment_id
    assert data["status"] == "checked_in"
    assert data["checked_in_at"] is not None


# ── Schedules (empty) ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_schedules_empty(client: AsyncClient) -> None:
    """Test listing doctor schedules when none exist."""
    response = await client.get("/api/v1/appointments/schedules")

    assert response.status_code == 200
    data = response.json()
    assert data == []


# ── Create Schedule ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_schedule(client: AsyncClient) -> None:
    """Test creating a doctor availability schedule."""
    payload = {
        "doctor_id": DOCTOR_ID,
        "day_of_week": 1,
        "start_time": "08:00",
        "end_time": "17:00",
        "slot_duration_minutes": 30,
    }
    response = await client.post("/api/v1/appointments/schedules", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["doctor_id"] == DOCTOR_ID
    assert data["day_of_week"] == 1
    assert data["start_time"] == "08:00:00"
    assert data["end_time"] == "17:00:00"
    assert data["slot_duration_minutes"] == 30
    assert data["is_active"] is True
    assert data["consultation_type"] == "general"
    assert "id" in data
    assert "created_at" in data
