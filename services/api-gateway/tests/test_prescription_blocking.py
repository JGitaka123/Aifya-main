"""Tests for critical-interaction prescription blocking.

CLAUDE.md clinical safety: drug interaction checks MUST run before
prescription save and MUST block on critical interactions — and the
clinician must receive the alert list, not a server error.
"""

import pytest
from httpx import AsyncClient


async def _create_allergic_patient(client: AsyncClient) -> str:
    """Create a patient with a documented penicillin allergy.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Allergy",
            "last_name": "Blocker",
            "date_of_birth": "1970-01-01",
            "gender": "male",
            "phone_number": "0700000004",
            "allergies": ["Penicillin"],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    """Create an OPD encounter.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Sore throat",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _rx_payload(encounter_id: str, patient_id: str, drug_name: str) -> dict:
    """Build a prescription payload.

    @param encounter_id: Encounter UUID string
    @param patient_id: Patient UUID string
    @param drug_name: Drug to prescribe
    @returns Prescription request body
    """
    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "drug_name": drug_name,
        "dosage": "500mg",
        "route": "oral",
        "frequency": "tds",
        "duration_days": 5,
        "quantity": 15,
    }


@pytest.mark.asyncio
async def test_critical_allergy_blocks_with_alerts(client: AsyncClient) -> None:
    """Prescribing a penicillin-class drug to a penicillin-allergic patient
    must return a structured blocked response, not a server error."""
    patient_id = await _create_allergic_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx_payload(encounter_id, patient_id, "Amoxicillin 500mg"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["blocked"] is True
    assert body["prescription"] is None
    assert len(body["interactions"]) >= 1
    assert any(i["severity"] == "critical" for i in body["interactions"])


@pytest.mark.asyncio
async def test_blocked_prescription_is_not_persisted(client: AsyncClient) -> None:
    """A blocked prescription must not appear on the encounter."""
    patient_id = await _create_allergic_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    blocked = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx_payload(encounter_id, patient_id, "Amoxicillin 500mg"),
    )
    assert blocked.json()["blocked"] is True

    listing = await client.get(f"/api/v1/encounters/{encounter_id}/prescriptions")
    assert listing.status_code == 200
    items = listing.json()
    drugs = [p["drug_name"] for p in (items if isinstance(items, list) else items.get("items", []))]
    assert "Amoxicillin 500mg" not in drugs


@pytest.mark.asyncio
async def test_safe_prescription_not_blocked(client: AsyncClient) -> None:
    """A drug with no interaction for this patient saves normally."""
    patient_id = await _create_allergic_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx_payload(encounter_id, patient_id, "Paracetamol 500mg"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["blocked"] is False
    assert body["prescription"] is not None
    assert body["prescription"]["drug_name"] == "Paracetamol 500mg"


@pytest.mark.asyncio
async def test_cds_failure_blocks_prescription_creation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed CDS check must fail closed without persisting a prescription."""
    async def fail_cds(**_kwargs: object) -> None:
        raise RuntimeError("CDS unavailable")

    monkeypatch.setattr(
        "app.services.prescription_service.evaluate_prescription", fail_cds
    )
    patient_id = await _create_allergic_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx_payload(encounter_id, patient_id, "Paracetamol 500mg"),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["blocked"] is True
    assert body["prescription"] is None
    assert body["interactions"][0]["severity"] == "critical"
    assert "could not verify" in body["interactions"][0]["description"]

    listing = await client.get(f"/api/v1/encounters/{encounter_id}/prescriptions")
    assert listing.status_code == 200
    assert listing.json() == []
