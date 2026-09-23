import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_patient(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test patient registration creates a patient and returns MRN."""
    response = await client.post("/api/v1/patients", json=sample_patient_data)

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Wanjiku"
    assert data["last_name"] == "Kamau"
    assert data["gender"] == "female"
    assert data["national_id"] == "29384756"
    assert data["phone_number"] == "0712345678"
    assert data["mrn"].startswith("MRN-")
    assert data["sha_number"] == "SHA-1234567"
    assert data["blood_group"] == "O+"
    assert data["allergies"] == ["Penicillin"]
    assert data["chronic_conditions"] == ["Hypertension"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_register_patient_minimal(client: AsyncClient) -> None:
    """Test patient registration with only required fields."""
    payload = {
        "first_name": "Otieno",
        "last_name": "Odhiambo",
        "date_of_birth": "1985-01-10",
        "gender": "male",
        "phone_number": "0798765432",
    }
    response = await client.post("/api/v1/patients", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Otieno"
    assert data["middle_name"] is None
    assert data["county"] is None


@pytest.mark.asyncio
async def test_register_patient_invalid_gender(client: AsyncClient) -> None:
    """Test validation rejects invalid gender values."""
    payload = {
        "first_name": "Test",
        "last_name": "User",
        "date_of_birth": "2000-01-01",
        "gender": "invalid",
        "phone_number": "0712345678",
    }
    response = await client.post("/api/v1/patients", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_patient_missing_required(client: AsyncClient) -> None:
    """Test validation rejects missing required fields."""
    payload = {"first_name": "Test"}
    response = await client.post("/api/v1/patients", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_patient(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test fetching a single patient by ID."""
    # Create
    create_response = await client.post("/api/v1/patients", json=sample_patient_data)
    patient_id = create_response.json()["id"]

    # Fetch
    response = await client.get(f"/api/v1/patients/{patient_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == patient_id
    assert data["first_name"] == "Wanjiku"


@pytest.mark.asyncio
async def test_get_patient_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent patient."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/patients/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_patients(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test listing patients with pagination."""
    # Create two patients
    await client.post("/api/v1/patients", json=sample_patient_data)
    patient2 = {**sample_patient_data, "first_name": "Akinyi", "national_id": "11111111"}
    await client.post("/api/v1/patients", json=patient2)

    # List all
    response = await client.get("/api/v1/patients")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_search_patients_by_name(
    client: AsyncClient, sample_patient_data: dict
) -> None:
    """Test searching patients by name."""
    await client.post("/api/v1/patients", json=sample_patient_data)

    response = await client.get("/api/v1/patients", params={"q": "Wanjiku"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["first_name"] == "Wanjiku"


@pytest.mark.asyncio
async def test_search_patients_by_national_id(
    client: AsyncClient, sample_patient_data: dict
) -> None:
    """Test searching patients by national ID."""
    await client.post("/api/v1/patients", json=sample_patient_data)

    response = await client.get("/api/v1/patients", params={"q": "29384756"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_search_patients_by_phone(
    client: AsyncClient, sample_patient_data: dict
) -> None:
    """Test searching patients by phone number."""
    await client.post("/api/v1/patients", json=sample_patient_data)

    response = await client.get("/api/v1/patients", params={"q": "0712345678"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_search_patients_no_results(client: AsyncClient) -> None:
    """Test search returns empty when no matches."""
    response = await client.get("/api/v1/patients", params={"q": "nonexistent"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test updating patient demographics."""
    # Create
    create_response = await client.post("/api/v1/patients", json=sample_patient_data)
    patient_id = create_response.json()["id"]

    # Update
    update_data = {
        "phone_number": "0787654321",
        "county": "Mombasa",
        "occupation": "Teacher",
    }
    response = await client.patch(f"/api/v1/patients/{patient_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["phone_number"] == "0787654321"
    assert data["county"] == "Mombasa"
    assert data["occupation"] == "Teacher"
    # Unchanged fields preserved
    assert data["first_name"] == "Wanjiku"
    assert data["sha_number"] == "SHA-1234567"


@pytest.mark.asyncio
async def test_update_patient_not_found(client: AsyncClient) -> None:
    """Test 404 when updating non-existent patient."""
    fake_id = str(uuid.uuid4())
    response = await client.patch(
        f"/api/v1/patients/{fake_id}", json={"first_name": "Test"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_idempotency_key(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test that idempotency key is accepted in the header."""
    response = await client.post(
        "/api/v1/patients",
        json=sample_patient_data,
        headers={"X-Idempotency-Key": "test-key-123"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, sample_patient_data: dict) -> None:
    """Test pagination parameters."""
    # Create 3 patients
    for i in range(3):
        payload = {
            **sample_patient_data,
            "first_name": f"Patient{i}",
            "national_id": f"ID{i}",
        }
        await client.post("/api/v1/patients", json=payload)

    # Page 1, size 2
    response = await client.get(
        "/api/v1/patients", params={"page": "1", "page_size": "2"}
    )
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1

    # Page 2, size 2
    response = await client.get(
        "/api/v1/patients", params={"page": "2", "page_size": "2"}
    )
    data = response.json()
    assert len(data["items"]) == 1
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint (no auth required)."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
