import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_insurance_summary(client: AsyncClient) -> None:
    """Test insurance summary returns correct structure."""
    response = await client.get("/api/v1/insurance/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_claims"] == 0
    assert data["pending_claims"] == 0
    assert data["submitted_claims"] == 0
    assert data["approved_claims"] == 0
    assert data["rejected_claims"] == 0
    assert data["total_claim_value"] == 0
    assert data["active_schemes"] == 0
    assert data["preauth_pending"] == 0


@pytest.mark.asyncio
async def test_list_schemes_empty(client: AsyncClient) -> None:
    """Test listing schemes when none exist."""
    response = await client.get("/api/v1/insurance/schemes")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_scheme(client: AsyncClient) -> None:
    """Test creating an insurance scheme."""
    payload = {
        "name": "SHA National Scheme",
        "scheme_type": "sha",
        "contact_person": "Dr. Omondi",
        "phone": "+254712345678",
        "email": "sha@health.go.ke",
        "rebate_percentage": 15,
        "notes": "Government SHA scheme",
    }
    response = await client.post("/api/v1/insurance/schemes", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "SHA National Scheme"
    assert data["scheme_type"] == "sha"
    assert data["scheme_code"].startswith("SCH-")
    assert data["contact_person"] == "Dr. Omondi"
    assert data["rebate_percentage"] == 15
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_scheme_validates_type(client: AsyncClient) -> None:
    """Test that invalid scheme type is rejected."""
    payload = {
        "name": "Bad Scheme",
        "scheme_type": "invalid_type",
    }
    response = await client.post("/api/v1/insurance/schemes", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_schemes_after_creation(client: AsyncClient) -> None:
    """Test listing schemes returns created schemes."""
    await client.post("/api/v1/insurance/schemes", json={
        "name": "Private Insurer A",
        "scheme_type": "private",
    })
    await client.post("/api/v1/insurance/schemes", json={
        "name": "Corporate Plan B",
        "scheme_type": "corporate",
    })

    response = await client.get("/api/v1/insurance/schemes")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_create_claim(client: AsyncClient) -> None:
    """Test creating an insurance claim requires patient and scheme."""
    # Create a scheme first
    scheme_resp = await client.post("/api/v1/insurance/schemes", json={
        "name": "Test SHA",
        "scheme_type": "sha",
    })
    scheme_id = scheme_resp.json()["id"]

    # Create a patient
    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1988-06-20",
        "gender": "female",
        "phone_number": "0711111111",
    })
    patient_id = patient_resp.json()["id"]

    # Create claim
    claim_payload = {
        "patient_id": patient_id,
        "scheme_id": scheme_id,
        "member_number": "SHA-001234",
        "claim_amount": 150000,  # KES 1,500.00 in cents
        "diagnosis_codes": ["J06.9"],
        "notes": "OPD consultation and lab tests",
    }
    response = await client.post("/api/v1/insurance/claims", json=claim_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["claim_number"].startswith("CLM-")
    assert data["member_number"] == "SHA-001234"
    assert data["claim_amount"] == 150000
    assert data["status"] == "draft"
    assert data["approved_amount"] == 0
    assert data["paid_amount"] == 0


@pytest.mark.asyncio
async def test_list_claims_empty(client: AsyncClient) -> None:
    """Test listing claims when none exist."""
    response = await client.get("/api/v1/insurance/claims")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_claim_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent claim."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/insurance/claims/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_claim_status(client: AsyncClient) -> None:
    """Test updating claim status through the workflow."""
    # Setup: create scheme + patient + claim
    scheme_resp = await client.post("/api/v1/insurance/schemes", json={
        "name": "Corp Insurance",
        "scheme_type": "corporate",
    })
    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "John",
        "last_name": "Mutua",
        "date_of_birth": "1975-03-12",
        "gender": "male",
        "phone_number": "0722222222",
    })
    claim_resp = await client.post("/api/v1/insurance/claims", json={
        "patient_id": patient_resp.json()["id"],
        "scheme_id": scheme_resp.json()["id"],
        "member_number": "CORP-5678",
        "claim_amount": 500000,
    })
    claim_id = claim_resp.json()["id"]

    # Submit the claim
    response = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/status",
        json={"status": "submitted"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    assert response.json()["submitted_date"] is not None

    # Approve the claim
    response = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/status",
        json={"status": "approved", "approved_amount": 480000},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["approved_amount"] == 480000
    assert response.json()["processed_date"] is not None


@pytest.mark.asyncio
async def test_update_claim_status_not_found(client: AsyncClient) -> None:
    """Test 404 when updating non-existent claim status."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/insurance/claims/{fake_id}/status",
        json={"status": "submitted"},
    )
    assert response.status_code == 404
