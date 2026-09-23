import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_trials_summary_empty(client: AsyncClient) -> None:
    """Test trials summary with no data."""
    response = await client.get("/api/v1/trials/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_trials"] == 0
    assert data["recruiting_trials"] == 0
    assert data["active_trials"] == 0
    assert data["total_participants"] == 0
    assert data["serious_adverse_events"] == 0
    assert data["pending_ai_screenings"] == 0


@pytest.mark.asyncio
async def test_list_trials_empty(client: AsyncClient) -> None:
    """Test listing trials when none exist."""
    response = await client.get("/api/v1/trials")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.fixture
def sample_trial_data() -> dict:
    """Sample clinical trial creation payload."""
    return {
        "title": "A Phase III Randomized Study of Antimalarial Combination Therapy",
        "short_title": "REACT-Malaria Phase III",
        "phase": "III",
        "study_type": "interventional",
        "therapeutic_area": "Infectious Disease",
        "sponsor": "Kenya Medical Research Institute",
        "protocol_version": "3.0",
        "protocol_date": "2026-01-15",
        "inclusion_criteria": {
            "age_min": 18,
            "age_max": 65,
            "conditions": ["malaria", "P. falciparum"],
            "criteria": [
                "Confirmed P. falciparum malaria",
                "Age 18-65 years",
                "Informed consent provided",
            ],
        },
        "exclusion_criteria": {
            "criteria": [
                "Severe malaria requiring IV treatment",
                "Known allergy to artemisinin",
                "Pregnancy or breastfeeding",
                "Participation in another trial within 30 days",
            ],
        },
        "target_enrollment": 500,
        "irb_approval_number": "IRB-2026-0042",
        "irb_approval_date": "2026-01-10",
        "ethics_committee": "KEMRI Ethics Review Committee",
        "nacosti_permit": "NACOSTI/P/26/0234",
        "start_date": "2026-02-01",
        "end_date": "2027-12-31",
    }


@pytest.mark.asyncio
async def test_create_trial(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test creating a clinical trial."""
    response = await client.post("/api/v1/trials", json=sample_trial_data)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_trial_data["title"]
    assert data["trial_code"].startswith("TRL-")
    assert data["phase"] == "III"
    assert data["study_type"] == "interventional"
    assert data["sponsor"] == "Kenya Medical Research Institute"
    assert data["status"] == "setup"
    assert data["target_enrollment"] == 500
    assert data["irb_approval_number"] == "IRB-2026-0042"
    assert data["nacosti_permit"] == "NACOSTI/P/26/0234"
    assert data["inclusion_criteria"]["age_min"] == 18
    assert "id" in data


@pytest.mark.asyncio
async def test_create_trial_minimal(client: AsyncClient) -> None:
    """Test creating a trial with only required fields."""
    payload = {
        "title": "Basic Observational Study",
        "study_type": "observational",
        "sponsor": "County Hospital",
        "protocol_version": "1.0",
        "protocol_date": "2026-03-01",
        "inclusion_criteria": {"criteria": ["All adults"]},
        "exclusion_criteria": {"criteria": []},
    }
    response = await client.post("/api/v1/trials", json=payload)
    assert response.status_code == 201
    assert response.json()["study_type"] == "observational"


@pytest.mark.asyncio
async def test_create_trial_invalid_phase(client: AsyncClient) -> None:
    """Test validation rejects invalid phase."""
    payload = {
        "title": "Invalid Trial",
        "study_type": "interventional",
        "sponsor": "Test",
        "protocol_version": "1.0",
        "protocol_date": "2026-01-01",
        "phase": "V",  # Invalid
        "inclusion_criteria": {"criteria": []},
        "exclusion_criteria": {"criteria": []},
    }
    response = await client.post("/api/v1/trials", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_trial(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test fetching a single trial."""
    create_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/trials/{trial_id}")
    assert response.status_code == 200
    assert response.json()["id"] == trial_id
    assert response.json()["title"] == sample_trial_data["title"]


@pytest.mark.asyncio
async def test_get_trial_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent trial."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/trials/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_trial(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test updating a trial."""
    create_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = create_resp.json()["id"]

    response = await client.patch(f"/api/v1/trials/{trial_id}", json={
        "target_enrollment": 750,
        "protocol_version": "3.1",
    })
    assert response.status_code == 200
    assert response.json()["target_enrollment"] == 750
    assert response.json()["protocol_version"] == "3.1"
    # Unchanged fields preserved
    assert response.json()["title"] == sample_trial_data["title"]


@pytest.mark.asyncio
async def test_update_trial_status(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test trial status transitions."""
    create_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "setup"

    # Transition to recruiting
    response = await client.post(f"/api/v1/trials/{trial_id}/status", json={
        "status": "recruiting",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "recruiting"

    # Transition to active
    response = await client.post(f"/api/v1/trials/{trial_id}/status", json={
        "status": "active",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_list_trials_with_filter(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test filtering trials by status."""
    await client.post("/api/v1/trials", json=sample_trial_data)

    # Filter by setup status
    response = await client.get("/api/v1/trials", params={"status": "setup"})
    assert response.status_code == 200
    assert response.json()["total"] == 1

    # Filter by recruiting (none yet)
    response = await client.get("/api/v1/trials", params={"status": "recruiting"})
    assert response.json()["total"] == 0


# ── Participant Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enroll_participant(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test enrolling a patient as a trial participant."""
    # Create trial
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    # Create patient
    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "Grace",
        "last_name": "Achieng",
        "date_of_birth": "1992-08-20",
        "gender": "female",
        "phone_number": "0733333333",
    })
    patient_id = patient_resp.json()["id"]

    # Enroll
    response = await client.post(f"/api/v1/trials/{trial_id}/participants", json={
        "patient_id": patient_id,
        "randomization_arm": "Treatment A",
        "consent_version": "3.0",
        "consent_witness": "Dr. Wambua",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["participant_number"].startswith("P-")
    assert data["status"] == "screened"
    assert data["randomization_arm"] == "Treatment A"
    assert data["consent_version"] == "3.0"
    assert data["screening_date"] is not None


@pytest.mark.asyncio
async def test_list_participants(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test listing trial participants."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    response = await client.get(f"/api/v1/trials/{trial_id}/participants")
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_update_participant_status_enrolled(
    client: AsyncClient, sample_trial_data: dict
) -> None:
    """Test transitioning participant to enrolled sets enrollment_date."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "Peter",
        "last_name": "Oloo",
        "date_of_birth": "1985-11-05",
        "gender": "male",
        "phone_number": "0744444444",
    })
    patient_id = patient_resp.json()["id"]

    enroll_resp = await client.post(f"/api/v1/trials/{trial_id}/participants", json={
        "patient_id": patient_id,
    })
    participant_id = enroll_resp.json()["id"]

    # Enroll the participant
    response = await client.patch(
        f"/api/v1/trials/{trial_id}/participants/{participant_id}/status",
        json={"status": "enrolled"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "enrolled"
    assert data["enrollment_date"] is not None


# ── Adverse Event Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_report_adverse_event(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test reporting an adverse event."""
    # Setup trial + participant
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "Mary",
        "last_name": "Njoroge",
        "date_of_birth": "1990-04-15",
        "gender": "female",
        "phone_number": "0755555555",
    })
    patient_id = patient_resp.json()["id"]

    enroll_resp = await client.post(f"/api/v1/trials/{trial_id}/participants", json={
        "patient_id": patient_id,
    })
    participant_id = enroll_resp.json()["id"]

    # Report AE
    response = await client.post(f"/api/v1/trials/{trial_id}/adverse-events", json={
        "participant_id": participant_id,
        "ae_term": "Headache and mild nausea",
        "severity": "mild",
        "is_serious": False,
        "relatedness": "possible",
        "onset_date": "2026-03-15",
        "ctcae_grade": 1,
    })

    assert response.status_code == 201
    data = response.json()
    assert data["ae_term"] == "Headache and mild nausea"
    assert data["severity"] == "mild"
    assert data["is_serious"] is False
    assert data["relatedness"] == "possible"
    assert data["ctcae_grade"] == 1
    assert data["sae_aware_date"] is None  # Not an SAE


@pytest.mark.asyncio
async def test_report_serious_adverse_event(
    client: AsyncClient, sample_trial_data: dict
) -> None:
    """Test SAE reporting sets sae_aware_date automatically."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    patient_resp = await client.post("/api/v1/patients", json={
        "first_name": "David",
        "last_name": "Kibet",
        "date_of_birth": "1978-09-22",
        "gender": "male",
        "phone_number": "0766666666",
    })

    enroll_resp = await client.post(f"/api/v1/trials/{trial_id}/participants", json={
        "patient_id": patient_resp.json()["id"],
    })
    participant_id = enroll_resp.json()["id"]

    # Report SAE
    response = await client.post(f"/api/v1/trials/{trial_id}/adverse-events", json={
        "participant_id": participant_id,
        "ae_term": "Severe hepatotoxicity requiring hospitalization",
        "severity": "severe",
        "is_serious": True,
        "seriousness_criteria": {
            "hospitalization": True,
            "life_threatening": False,
            "disability": False,
            "death": False,
        },
        "relatedness": "probable",
        "onset_date": "2026-04-01",
        "ctcae_grade": 4,
    })

    assert response.status_code == 201
    data = response.json()
    assert data["is_serious"] is True
    assert data["sae_aware_date"] is not None  # Auto-set for SAEs
    assert data["ctcae_grade"] == 4


@pytest.mark.asyncio
async def test_list_adverse_events(client: AsyncClient, sample_trial_data: dict) -> None:
    """Test listing adverse events for a trial."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    response = await client.get(f"/api/v1/trials/{trial_id}/adverse-events")
    assert response.status_code == 200
    assert response.json()["total"] == 0


# ── Visit Schedule Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_visit_schedule(
    client: AsyncClient, sample_trial_data: dict
) -> None:
    """Test creating a visit schedule entry."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    response = await client.post(f"/api/v1/trials/{trial_id}/visit-schedule", json={
        "visit_code": "V1",
        "visit_name": "Screening Visit",
        "day_from_enrollment": 0,
        "window_before_days": 0,
        "window_after_days": 3,
        "required_assessments": [
            {"type": "vitals", "name": "Blood Pressure"},
            {"type": "lab", "name": "CBC"},
        ],
        "is_mandatory": True,
        "sort_order": 1,
    })

    assert response.status_code == 201
    data = response.json()
    assert data["visit_code"] == "V1"
    assert data["visit_name"] == "Screening Visit"
    assert data["day_from_enrollment"] == 0
    assert len(data["required_assessments"]) == 2


@pytest.mark.asyncio
async def test_get_visit_schedule(
    client: AsyncClient, sample_trial_data: dict
) -> None:
    """Test retrieving visit schedule for a trial."""
    trial_resp = await client.post("/api/v1/trials", json=sample_trial_data)
    trial_id = trial_resp.json()["id"]

    # Create multiple visits
    for i, (code, name, day) in enumerate([
        ("SCR", "Screening", -7),
        ("BL", "Baseline", 0),
        ("W4", "Week 4", 28),
        ("W12", "Week 12", 84),
    ]):
        await client.post(f"/api/v1/trials/{trial_id}/visit-schedule", json={
            "visit_code": code,
            "visit_name": name,
            "day_from_enrollment": day,
            "sort_order": i,
        })

    response = await client.get(f"/api/v1/trials/{trial_id}/visit-schedule")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    assert data[0]["visit_code"] == "SCR"  # Sorted by sort_order


# ── Summary Integration ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_reflects_data(
    client: AsyncClient, sample_trial_data: dict
) -> None:
    """Test that summary counts reflect created data."""
    # Create trial
    await client.post("/api/v1/trials", json=sample_trial_data)

    response = await client.get("/api/v1/trials/summary")
    data = response.json()
    assert data["total_trials"] == 1
    # Status is 'setup' by default, not 'recruiting' or 'active'
    assert data["recruiting_trials"] == 0
    assert data["active_trials"] == 0
