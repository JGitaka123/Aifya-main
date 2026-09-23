import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

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


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    """Create an IPD encounter for a patient and return the encounter ID.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post("/api/v1/encounters", json={
        "patient_id": patient_id,
        "encounter_type": "ipd",
        "chief_complaint": "Severe pneumonia requiring admission",
    })
    assert response.status_code == 201
    return response.json()["id"]


async def _create_ward(
    client: AsyncClient,
    name: str = "General Ward A",
    code: str = "GWA",
    ward_type: str = "general",
) -> dict:
    """Create a test ward and return the response data.

    @param client: Async HTTP test client
    @param name: Ward name (unique per facility)
    @param code: Short ward code
    @param ward_type: Ward type enum value
    @returns Ward response dict with id, name, code, ward_type, total_beds
    """
    response = await client.post("/api/v1/ipd/wards", json={
        "name": name,
        "code": code,
        "ward_type": ward_type,
        "total_beds": 20,
    })
    assert response.status_code == 201
    return response.json()


async def _create_bed(client: AsyncClient, ward_id: str) -> dict:
    """Create a test bed in a ward and return the response data.

    @param client: Async HTTP test client
    @param ward_id: Ward UUID string
    @returns Bed response dict with id, bed_number, bed_type, ward_id
    """
    response = await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward_id,
        "bed_number": "A-101",
        "bed_type": "standard",
    })
    assert response.status_code == 201
    return response.json()


async def _create_admission(client: AsyncClient) -> dict:
    """Create a full admission (patient + encounter + ward + bed + admit).

    @param client: Async HTTP test client
    @returns Dict with admission data and supporting IDs
    """
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post("/api/v1/ipd/admissions", json={
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ward_id": ward["id"],
        "bed_id": bed["id"],
        "admission_diagnosis": "Pneumonia",
        "admitted_from": "emergency",
    })
    assert response.status_code == 201
    data = response.json()
    return {
        "admission": data,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ward_id": ward["id"],
        "bed_id": bed["id"],
    }


# ── Ward Board Summary ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ward_board_summary_empty(client: AsyncClient) -> None:
    """Test ward board summary returns zeroed stats when no data exists."""
    response = await client.get("/api/v1/ipd/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_beds" in data
    assert "occupied_beds" in data
    assert "available_beds" in data
    assert "active_admissions" in data


# ── Ward Management ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_wards_empty(client: AsyncClient) -> None:
    """Test listing wards returns empty list when none exist."""
    response = await client.get("/api/v1/ipd/wards")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_ward(client: AsyncClient) -> None:
    """Test creating a new ward with valid data."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "ICU Ward",
        "code": "ICU",
        "ward_type": "icu",
        "total_beds": 10,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "ICU Ward"
    assert data["code"] == "ICU"
    assert data["ward_type"] == "icu"
    assert data["total_beds"] == 10
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_ward_general(client: AsyncClient) -> None:
    """Test creating a general ward."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "General Ward B",
        "code": "GWB",
        "ward_type": "general",
        "total_beds": 30,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["ward_type"] == "general"


@pytest.mark.asyncio
async def test_create_ward_maternity(client: AsyncClient) -> None:
    """Test creating a maternity ward."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "Maternity Wing",
        "code": "MAT",
        "ward_type": "maternity",
        "total_beds": 15,
    })
    assert response.status_code == 201
    assert response.json()["ward_type"] == "maternity"


@pytest.mark.asyncio
async def test_create_ward_paediatric(client: AsyncClient) -> None:
    """Test creating a paediatric ward."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "Paediatric Ward",
        "code": "PAED",
        "ward_type": "paediatric",
        "total_beds": 12,
    })
    assert response.status_code == 201
    assert response.json()["ward_type"] == "paediatric"


@pytest.mark.asyncio
async def test_create_ward_isolation(client: AsyncClient) -> None:
    """Test creating an isolation ward."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "Isolation Rooms",
        "code": "ISO",
        "ward_type": "isolation",
        "total_beds": 5,
    })
    assert response.status_code == 201
    assert response.json()["ward_type"] == "isolation"


@pytest.mark.asyncio
async def test_create_ward_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid ward type."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "Bad Ward",
        "code": "BAD",
        "ward_type": "invalid_type",
        "total_beds": 10,
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ward_missing_name(client: AsyncClient) -> None:
    """Test validation rejects missing required name field."""
    response = await client.post("/api/v1/ipd/wards", json={
        "code": "NON",
        "ward_type": "general",
        "total_beds": 10,
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ward_missing_code(client: AsyncClient) -> None:
    """Test validation rejects missing required code field."""
    response = await client.post("/api/v1/ipd/wards", json={
        "name": "No Code Ward",
        "ward_type": "general",
        "total_beds": 10,
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_wards_after_creation(client: AsyncClient) -> None:
    """Test listing wards returns created wards."""
    await client.post("/api/v1/ipd/wards", json={
        "name": "Ward 1",
        "code": "W1",
        "ward_type": "general",
        "total_beds": 20,
    })
    await client.post("/api/v1/ipd/wards", json={
        "name": "Ward 2",
        "code": "W2",
        "ward_type": "icu",
        "total_beds": 8,
    })

    response = await client.get("/api/v1/ipd/wards")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


# ── Bed Management ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_beds_empty(client: AsyncClient) -> None:
    """Test listing beds returns empty list when none exist."""
    response = await client.get("/api/v1/ipd/beds")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_bed_standard(client: AsyncClient) -> None:
    """Test creating a standard bed in a ward."""
    ward = await _create_ward(client)

    response = await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "B-001",
        "bed_type": "standard",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["bed_number"] == "B-001"
    assert data["bed_type"] == "standard"
    assert data["ward_id"] == ward["id"]
    assert data["status"] == "available"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_bed_hdu(client: AsyncClient) -> None:
    """Test creating an HDU bed."""
    ward = await _create_ward(client)

    response = await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "B-002",
        "bed_type": "hdu",
    })
    assert response.status_code == 201
    assert response.json()["bed_type"] == "hdu"


@pytest.mark.asyncio
async def test_create_bed_icu(client: AsyncClient) -> None:
    """Test creating an ICU bed."""
    ward = await _create_ward(client)

    response = await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "ICU-001",
        "bed_type": "icu",
    })
    assert response.status_code == 201
    assert response.json()["bed_type"] == "icu"


@pytest.mark.asyncio
async def test_create_bed_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid bed type."""
    ward = await _create_ward(client)

    response = await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "X-001",
        "bed_type": "waterbed",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_bed_missing_ward(client: AsyncClient) -> None:
    """Test validation rejects bed creation without ward_id."""
    response = await client.post("/api/v1/ipd/beds", json={
        "bed_number": "B-001",
        "bed_type": "standard",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_beds_after_creation(client: AsyncClient) -> None:
    """Test listing beds returns created beds."""
    ward = await _create_ward(client)
    await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "C-001",
        "bed_type": "standard",
    })
    await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward["id"],
        "bed_number": "C-002",
        "bed_type": "hdu",
    })

    response = await client.get("/api/v1/ipd/beds")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_beds_filter_by_ward(client: AsyncClient) -> None:
    """Test filtering beds by ward_id query parameter."""
    ward1 = await _create_ward(client)
    ward2_resp = await client.post("/api/v1/ipd/wards", json={
        "name": "Ward 2",
        "code": "W2",
        "ward_type": "icu",
        "total_beds": 5,
    })
    ward2 = ward2_resp.json()

    await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward1["id"],
        "bed_number": "W1-001",
        "bed_type": "standard",
    })
    await client.post("/api/v1/ipd/beds", json={
        "ward_id": ward2["id"],
        "bed_number": "W2-001",
        "bed_type": "icu",
    })

    response = await client.get("/api/v1/ipd/beds", params={"ward_id": ward1["id"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ward_id"] == ward1["id"]


# ── Admissions ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_admissions_empty(client: AsyncClient) -> None:
    """Test listing admissions returns empty when none exist."""
    response = await client.get("/api/v1/ipd/admissions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_admit_patient(client: AsyncClient) -> None:
    """Test full admission flow: create patient, encounter, ward, bed, then admit."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post("/api/v1/ipd/admissions", json={
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ward_id": ward["id"],
        "bed_id": bed["id"],
        "admission_diagnosis": "Pneumonia",
        "admitted_from": "emergency",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_id"] == encounter_id
    assert data["ward_id"] == ward["id"]
    assert data["bed_id"] == bed["id"]
    assert data["admission_diagnosis"] == "Pneumonia"
    assert data["admitted_from"] == "emergency"
    assert data["status"] == "admitted"
    assert data["admission_number"].startswith("IP-")
    assert "id" in data
    assert "admitted_at" in data


@pytest.mark.asyncio
async def test_admit_patient_missing_fields(client: AsyncClient) -> None:
    """Test validation rejects admission with missing required fields."""
    response = await client.post("/api/v1/ipd/admissions", json={
        "admission_diagnosis": "Pneumonia",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admit_patient_invalid_source(client: AsyncClient) -> None:
    """Test validation rejects an invalid admitted_from value."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post("/api/v1/ipd/admissions", json={
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ward_id": ward["id"],
        "bed_id": bed["id"],
        "admitted_from": "walk_in",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admit_patient_with_idempotency_key(client: AsyncClient) -> None:
    """Test admission accepts X-Idempotency-Key header."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "ward_id": ward["id"],
            "bed_id": bed["id"],
            "admission_diagnosis": "Malaria",
            "admitted_from": "emergency",
        },
        headers={"X-Idempotency-Key": "ipd-admit-001"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_admission_detail(client: AsyncClient) -> None:
    """Test fetching a single admission by ID."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admission_id
    assert data["patient_id"] == result["patient_id"]
    assert data["admission_diagnosis"] == "Pneumonia"


@pytest.mark.asyncio
async def test_get_admission_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent admission."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/ipd/admissions/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_admissions_after_admit(client: AsyncClient) -> None:
    """Test listing admissions includes the newly created admission."""
    await _create_admission(client)

    response = await client.get("/api/v1/ipd/admissions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


# ── Nursing Notes ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_nursing_note_observation(client: AsyncClient) -> None:
    """Test adding an observation nursing note to an admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "observation",
        "content": "Patient alert and oriented. Temp 38.2C. Lungs: bilateral crackles.",
        "shift": "morning",
        "severity": "warning",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["note_type"] == "observation"
    assert "bilateral crackles" in data["content"]
    assert data["shift"] == "morning"
    assert data["severity"] == "warning"
    assert "id" in data


@pytest.mark.asyncio
async def test_add_nursing_note_medication(client: AsyncClient) -> None:
    """Test adding a medication nursing note."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "medication",
        "content": "Administered IV ceftriaxone 2g as prescribed. Tolerated well.",
    })
    assert response.status_code == 201
    assert response.json()["note_type"] == "medication"


@pytest.mark.asyncio
async def test_add_nursing_note_shift_handover(client: AsyncClient) -> None:
    """Test adding a shift handover nursing note."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "shift_handover",
        "content": "Fever subsiding. Appetite improving. SpO2 96% on room air.",
        "shift": "night",
    })
    assert response.status_code == 201
    assert response.json()["note_type"] == "shift_handover"


@pytest.mark.asyncio
async def test_add_nursing_note_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid note type."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "invalid_type",
        "content": "Some note",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_nursing_note_missing_content(client: AsyncClient) -> None:
    """Test validation rejects nursing note without content."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "observation",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_nursing_notes_empty(client: AsyncClient) -> None:
    """Test listing notes returns empty list when none exist for admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_nursing_notes_after_creation(client: AsyncClient) -> None:
    """Test listing notes returns all notes for an admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "observation",
        "content": "Initial assessment: vitals stable.",
    })
    await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "medication",
        "content": "IV fluids started.",
    })
    await client.post(f"/api/v1/ipd/admissions/{admission_id}/notes", json={
        "note_type": "procedure",
        "content": "Wound dressing changed. Patient resting comfortably.",
    })

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


# ── Discharge ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discharge_patient_recovered(client: AsyncClient) -> None:
    """Test normal (recovered) discharge flow frees the bed."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "recovered",
            "discharge_diagnosis": "Resolved pneumonia",
            "discharge_summary": "Recovered from pneumonia after 5-day IV antibiotics.",
            "follow_up_plan": "Review in OPD after 7 days.",
            "discharge_medications": "Oral amoxicillin 500mg TDS x 5 days.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admission_id
    assert data["status"] == "discharged"
    assert data["discharge_type"] == "recovered"
    assert data["discharged_at"] is not None

    # Bed should be released for cleaning after discharge
    beds_response = await client.get(
        "/api/v1/ipd/beds", params={"ward_id": result["ward_id"]}
    )
    assert beds_response.status_code == 200
    bed = beds_response.json()[0]
    assert bed["status"] == "cleaning"
    assert bed["current_patient_id"] is None


@pytest.mark.asyncio
async def test_discharge_patient_dama(client: AsyncClient) -> None:
    """Test discharge against medical advice (DAMA)."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "dama",
            "discharge_summary": "Patient insisted on leaving. Risks explained.",
            "follow_up_plan": "Urgent: Return immediately if symptoms worsen.",
        },
    )
    assert response.status_code == 200
    assert response.json()["discharge_type"] == "dama"


@pytest.mark.asyncio
async def test_discharge_patient_deceased(client: AsyncClient) -> None:
    """Test discharge type deceased."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "deceased",
            "discharge_summary": "Succumbed to complications. Time of death 14:30.",
        },
    )
    assert response.status_code == 200
    assert response.json()["discharge_type"] == "deceased"


@pytest.mark.asyncio
async def test_discharge_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid discharge type."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "invalid",
            "discharge_summary": "Test",
            "follow_up_plan": "Test",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_discharge_not_found(client: AsyncClient) -> None:
    """Test 404 when discharging non-existent admission."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/ipd/admissions/{fake_id}/discharge",
        json={
            "discharge_type": "recovered",
            "discharge_summary": "Test discharge",
            "follow_up_plan": "Follow up in 7 days",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_discharge_missing_type(client: AsyncClient) -> None:
    """Test validation rejects discharge without required discharge_type."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_summary": "Summary without a discharge type.",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transfer_inpatient_to_emergency(client: AsyncClient) -> None:
    '''Test a worsening inpatient can be transferred to the Emergency Room.'''
    result = await _create_admission(client)
    admission_id = result['admission']['id']

    response = await client.post(
        f'/api/v1/ipd/admissions/{admission_id}/transfer-to-emergency',
        json={
            'reason': 'Sudden severe chest pain and difficulty breathing',
            'notes': 'Patient deteriorated on the ward; urgent review needed.',
        },
    )
    assert response.status_code == 200
    visit = response.json()
    assert visit['id']
    assert visit['patient_id'] == result['patient_id']
    assert visit['arrival_mode'] == 'referral'
    assert visit['chief_complaint'] == 'Sudden severe chest pain and difficulty breathing'
    assert visit['visit_number'].startswith('ER-')
    assert visit['status'] == 'arrived'

    # The IPD admission is closed as transferred and the bed is freed.
    detail = await client.get(f'/api/v1/ipd/admissions/{admission_id}')
    assert detail.status_code == 200
    admission = detail.json()
    assert admission['status'] == 'transferred'
    assert admission['discharge_type'] == 'transferred'
    assert admission['discharged_at'] is not None

    beds = await client.get(
        '/api/v1/ipd/beds', params={'ward_id': result['ward_id']}
    )
    assert beds.status_code == 200
    bed = beds.json()[0]
    assert bed['status'] == 'cleaning'
    assert bed['current_patient_id'] is None

    # The patient shows up in the emergency queue awaiting triage.
    queue = await client.get('/api/v1/emergency/queue')
    assert queue.status_code == 200
    item_ids = [item['id'] for item in queue.json()['items']]
    assert visit['id'] in item_ids


@pytest.mark.asyncio
async def test_transfer_inpatient_to_emergency_missing_reason(
    client: AsyncClient,
) -> None:
    '''Test validation rejects a transfer without a reason.'''
    result = await _create_admission(client)
    admission_id = result['admission']['id']

    response = await client.post(
        f'/api/v1/ipd/admissions/{admission_id}/transfer-to-emergency',
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transfer_inpatient_to_emergency_after_discharge(
    client: AsyncClient,
) -> None:
    '''Test transfer is rejected once the admission is no longer active.'''
    result = await _create_admission(client)
    admission_id = result['admission']['id']

    discharged = await client.post(
        f'/api/v1/ipd/admissions/{admission_id}/discharge',
        json={'discharge_type': 'recovered'},
    )
    assert discharged.status_code == 200

    response = await client.post(
        f'/api/v1/ipd/admissions/{admission_id}/transfer-to-emergency',
        json={'reason': 'Patient deteriorated after discharge.'},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_transfer_inpatient_to_emergency_not_found(
    client: AsyncClient,
) -> None:
    '''Test 404 when transferring a non-existent admission.'''
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f'/api/v1/ipd/admissions/{fake_id}/transfer-to-emergency',
        json={'reason': 'Patient deteriorated.'},
    )
    assert response.status_code == 404


# ── Ward Board Summary After Activity ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ward_board_summary_reflects_admission(client: AsyncClient) -> None:
    """Test ward board summary updates after admission."""
    await _create_admission(client)

    response = await client.get("/api/v1/ipd/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["active_admissions"] >= 1
    assert data["occupied_beds"] >= 1
