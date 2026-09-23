"""Tier 4 clinical safety: paediatric weight-based dose guardrails (B) and
drug-interaction alert acknowledgement (A).

The blocking behaviour for critical allergies/interactions is covered by
test_prescription_blocking.py; these tests cover the non-blocking WARN paths.
"""

from datetime import date

import pytest
from httpx import AsyncClient


async def _create_patient(client: AsyncClient, dob: str, **extra: object) -> str:
    payload = {
        "first_name": "Dose",
        "last_name": "Check",
        "date_of_birth": dob,
        "gender": "male",
        "phone_number": "0700000005",
        **extra,
    }
    resp = await client.post("/api/v1/patients", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    resp = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Fever",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _record_weight(
    client: AsyncClient, encounter_id: str, patient_id: str, weight_kg: float
) -> None:
    resp = await client.post(
        f"/api/v1/encounters/{encounter_id}/vitals",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "weight_kg": weight_kg,
        },
    )
    assert resp.status_code in (200, 201), resp.text


def _rx(encounter_id: str, patient_id: str, drug: str, value: float, **extra: object) -> dict:
    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "drug_name": drug,
        "dosage": f"{value:g}mg",
        "dosage_value": value,
        "dosage_unit": "mg",
        "route": "oral",
        "frequency": "tds",
        "duration_days": 3,
        "quantity": 9,
        **extra,
    }


def _child_dob() -> str:
    """DOB making the patient ~4 years old today."""
    return date(date.today().year - 4, 1, 1).isoformat()


@pytest.mark.asyncio
async def test_paediatric_overdose_flagged(client: AsyncClient) -> None:
    """An adult paracetamol dose for a 15 kg child raises a dose-range WARN."""
    patient_id = await _create_patient(client, _child_dob())
    encounter_id = await _create_encounter(client, patient_id)
    await _record_weight(client, encounter_id, patient_id, 15.0)

    resp = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx(encounter_id, patient_id, "Paracetamol", 1000),  # 66 mg/kg
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # WARN, not blocked — the prescription still saves.
    assert body["blocked"] is False
    assert body["prescription"] is not None
    assert any(
        i.get("category") == "drug_dose" for i in (body["interactions"] or [])
    ), body["interactions"]


@pytest.mark.asyncio
async def test_paediatric_in_range_dose_not_flagged(client: AsyncClient) -> None:
    """An appropriate weight-based paracetamol dose raises no dose alert."""
    patient_id = await _create_patient(client, _child_dob())
    encounter_id = await _create_encounter(client, patient_id)
    await _record_weight(client, encounter_id, patient_id, 15.0)

    resp = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx(encounter_id, patient_id, "Paracetamol", 150),  # 10 mg/kg
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["blocked"] is False
    assert not any(
        i.get("category") == "drug_dose" for i in (body["interactions"] or [])
    ), body["interactions"]


@pytest.mark.asyncio
async def test_interacting_pair_warns_and_acknowledgement_recorded(
    client: AsyncClient,
) -> None:
    """Warfarin + aspirin raises a visible (non-blocking) interaction alert,
    and the clinician's acknowledgement is recorded on the prescription."""
    # Adult patient (aspirin is contraindicated under 16 — use an adult).
    patient_id = await _create_patient(client, "1970-01-01")
    encounter_id = await _create_encounter(client, patient_id)

    # Warfarin becomes an active medication.
    warfarin = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx(encounter_id, patient_id, "Warfarin", 5),
    )
    assert warfarin.status_code == 201, warfarin.text
    assert warfarin.json()["blocked"] is False

    # Prescribing aspirin now interacts with warfarin (high, WARN).
    resp = await client.post(
        f"/api/v1/encounters/{encounter_id}/prescriptions",
        json=_rx(
            encounter_id,
            patient_id,
            "Aspirin",
            75,
            acknowledged_alert_ids=["warfarin-aspirin"],
            override_reason="Cardiology advised dual therapy; monitoring INR.",
        ),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["blocked"] is False
    assert body["prescription"] is not None
    # The interaction alert fired and is visible.
    assert any(
        i.get("severity") == "high" and "warfarin" in str(i.get("interacting_drug", "")).lower()
        for i in (body["interactions"] or [])
    ), body["interactions"]
    # The acknowledgement is recorded on the saved prescription.
    assert body["prescription"]["acknowledged_alerts"] == ["warfarin-aspirin"]
    assert "INR" in (body["prescription"]["override_reason"] or "")
