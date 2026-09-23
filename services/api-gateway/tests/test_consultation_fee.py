"""Tests for consultation-fee resolution (fee taken at reception)."""

import pytest
from httpx import AsyncClient

from app.services.consultation_fee import (
    DEFAULT_CONSULTATION_FEE_CENTS,
    resolve_consultation_fee_cents,
)

DEPARTMENT = "11111111-1111-1111-1111-111111111111"
DOCTOR = "22222222-2222-2222-2222-222222222222"
OTHER_DOCTOR = "33333333-3333-3333-3333-333333333333"


def test_defaults_when_nothing_is_configured() -> None:
    """A facility with no settings charges the built-in default."""
    assert resolve_consultation_fee_cents({}) == DEFAULT_CONSULTATION_FEE_CENTS


def test_legacy_facility_default_is_honoured() -> None:
    """The pre-existing consultation_fee_cents key still works."""
    assert resolve_consultation_fee_cents({"consultation_fee_cents": 50000}) == 50000


def test_new_default_wins_over_legacy_key() -> None:
    """consultation_fees.default_cents supersedes the legacy key."""
    settings = {
        "consultation_fee_cents": 50000,
        "consultation_fees": {"default_cents": 75000},
    }
    assert resolve_consultation_fee_cents(settings) == 75000


def test_department_override_applies() -> None:
    """A department-specific fee overrides the facility default."""
    settings = {
        "consultation_fees": {
            "default_cents": 100000,
            "by_department": {DEPARTMENT: 150000},
        }
    }
    assert (
        resolve_consultation_fee_cents(settings, department_id=DEPARTMENT)
        == 150000
    )


def test_doctor_override_beats_department() -> None:
    """Directing a patient to a named doctor uses that doctor's fee."""
    settings = {
        "consultation_fees": {
            "default_cents": 100000,
            "by_department": {DEPARTMENT: 150000},
            "by_doctor": {DOCTOR: 200000},
        }
    }
    assert (
        resolve_consultation_fee_cents(
            settings, department_id=DEPARTMENT, doctor_id=DOCTOR
        )
        == 200000
    )


def test_unknown_doctor_falls_back_to_department() -> None:
    """A doctor with no override inherits the department fee."""
    settings = {
        "consultation_fees": {
            "default_cents": 100000,
            "by_department": {DEPARTMENT: 150000},
            "by_doctor": {DOCTOR: 200000},
        }
    }
    assert (
        resolve_consultation_fee_cents(
            settings, department_id=DEPARTMENT, doctor_id=OTHER_DOCTOR
        )
        == 150000
    )


def test_zero_fee_disables_collection() -> None:
    """A zero fee means no consultation invoice is raised."""
    assert resolve_consultation_fee_cents({"consultation_fees": {"default_cents": 0}}) == 0


def test_explicit_zero_override_is_not_skipped() -> None:
    """A 0 override for one department must not collapse to the default."""
    settings = {
        "consultation_fees": {
            "default_cents": 100000,
            "by_department": {DEPARTMENT: 0},
        }
    }
    assert (
        resolve_consultation_fee_cents(settings, department_id=DEPARTMENT) == 0
    )


def test_invalid_values_fall_back_to_default() -> None:
    """Garbage in settings must not break the front desk."""
    settings = {"consultation_fees": {"default_cents": "free"}}
    assert resolve_consultation_fee_cents(settings) == DEFAULT_CONSULTATION_FEE_CENTS


def test_non_dict_block_is_ignored() -> None:
    """A malformed consultation_fees block is ignored, not fatal."""
    assert (
        resolve_consultation_fee_cents({"consultation_fees": "nope"})
        == DEFAULT_CONSULTATION_FEE_CENTS
    )


# ── Editing the fee at the desk ─────────────────────────────────────────────


async def _patient(client: AsyncClient) -> str:
    """
    Create a test patient.

    @param client: Async HTTP test client
    @returns Patient UUID
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Fee",
            "last_name": "Editor",
            "date_of_birth": "1991-02-03",
            "gender": "female",
            "phone_number": "0722111222",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _encounter(client: AsyncClient, patient_id: str) -> str:
    """
    Create a test OPD encounter.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID
    @returns Encounter UUID
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Fee edit test",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_consultation_fee_can_be_edited(client: AsyncClient) -> None:
    """Correcting the fee re-prices the visit and keeps a receipt to print."""
    encounter_id = await _encounter(client, await _patient(client))
    before = await client.get(f"/api/v1/encounters/{encounter_id}/consultation-fee")
    assert before.status_code == 200
    assert before.json()["fee_cents"] == DEFAULT_CONSULTATION_FEE_CENTS

    response = await client.patch(
        f"/api/v1/encounters/{encounter_id}/consultation-fee",
        json={"amount_cents": 75000},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["fee_cents"] == 75000
    assert data["balance_cents"] == 75000
    assert data["paid"] is False
    assert data["invoice_number"]
    assert data["receipt_url"]


@pytest.mark.asyncio
async def test_edited_fee_is_what_the_patient_pays(client: AsyncClient) -> None:
    """The reception desk collects the edited fee, not the configured one."""
    encounter_id = await _encounter(client, await _patient(client))
    await client.patch(
        f"/api/v1/encounters/{encounter_id}/consultation-fee",
        json={"amount_cents": 40000},
    )

    payment = await client.post(
        f"/api/v1/encounters/{encounter_id}/consultation-payment",
        json={"payment_method": "cash"},
    )

    assert payment.status_code == 201
    body = payment.json()
    assert body["fee_cents"] == 40000
    assert body["paid_cents"] == 40000
    assert body["balance_cents"] == 0
    assert body["receipt_url"]


@pytest.mark.asyncio
async def test_fee_below_collected_amount_is_rejected(client: AsyncClient) -> None:
    """A fee cannot drop below money already taken for the visit."""
    encounter_id = await _encounter(client, await _patient(client))
    started = await client.post(
        f"/api/v1/encounters/{encounter_id}/consultation-payment",
        json={"payment_method": "cash", "amount_cents": 30000},
    )
    assert started.status_code == 201

    response = await client.patch(
        f"/api/v1/encounters/{encounter_id}/consultation-fee",
        json={"amount_cents": 10000},
    )

    assert response.status_code == 400
    assert "already collected" in response.json()["detail"]


@pytest.mark.asyncio
async def test_fee_must_be_positive(client: AsyncClient) -> None:
    """Validation rejects a zero or negative fee."""
    encounter_id = await _encounter(client, await _patient(client))

    response = await client.patch(
        f"/api/v1/encounters/{encounter_id}/consultation-fee",
        json={"amount_cents": 0},
    )

    assert response.status_code == 422