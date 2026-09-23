"""Tests for ClaimFlow validation + SHA submission of insurance claims."""

import pytest
from httpx import AsyncClient

from app.services import insurance_service as ins_mod
from app.services.claimflow.client import ClaimValidationResult


async def _draft_claim(client: AsyncClient) -> str:
    """Create a scheme, patient, and a draft SHA claim; return claim id."""
    scheme = await client.post(
        "/api/v1/insurance/schemes",
        json={"name": "SHA", "scheme_type": "sha"},
    )
    patient = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Claim",
            "last_name": "Flow",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone_number": "0722000000",
        },
    )
    claim = await client.post(
        "/api/v1/insurance/claims",
        json={
            "patient_id": patient.json()["id"],
            "scheme_id": scheme.json()["id"],
            "member_number": "CR000000001-1",
            "claim_amount": 120000,
            "claim_items": [{"service": "Consultation", "code": "SHA-001", "amount": 120000}],
            "diagnosis_codes": ["1A00"],
        },
    )
    assert claim.status_code == 201
    return claim.json()["id"]


@pytest.mark.asyncio
async def test_validate_unavailable_when_validator_unconfigured(
    client: AsyncClient,
) -> None:
    """With no validator URL, validation returns UNAVAILABLE and is stored."""
    claim_id = await _draft_claim(client)
    resp = await client.post(f"/api/v1/insurance/claims/{claim_id}/validate")
    assert resp.status_code == 200
    assert resp.json()["decision"] == "UNAVAILABLE"

    detail = await client.get(f"/api/v1/insurance/claims/{claim_id}")
    assert detail.json()["validation_decision"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_submit_blocked_before_validation(client: AsyncClient) -> None:
    """A claim cannot be submitted before it is validated."""
    claim_id = await _draft_claim(client)
    resp = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/submit", json={"force": False}
    )
    assert resp.status_code == 409
    assert "must be validated" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_succeeds_after_validation_mock_sha(
    client: AsyncClient,
) -> None:
    """After validation, submission (mock SHA) sets status + mock reference."""
    claim_id = await _draft_claim(client)
    await client.post(f"/api/v1/insurance/claims/{claim_id}/validate")

    resp = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/submit", json={"force": False}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["claim"]["status"] == "submitted"
    assert body["claim"]["sha_reference"].startswith("MOCK-SHA-")


@pytest.mark.asyncio
async def test_failed_validation_blocks_submit_unless_forced(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A FAILED validation blocks submission; force overrides and audits it."""

    async def _fake_validate(self, **kwargs):
        return ClaimValidationResult(
            decision="FAILED",
            total_rules=121,
            findings=[{"ruleId": "IDN-001", "result": "FAIL"}],
            fix_report_markdown="# Fix report\n- IDN-001 failed",
            rulepack_version="1.0.0",
        )

    monkeypatch.setattr(ins_mod.ClaimFlowClient, "validate", _fake_validate)

    claim_id = await _draft_claim(client)
    val = await client.post(f"/api/v1/insurance/claims/{claim_id}/validate")
    assert val.json()["decision"] == "FAILED"

    blocked = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/submit", json={"force": False}
    )
    assert blocked.status_code == 409

    forced = await client.post(
        f"/api/v1/insurance/claims/{claim_id}/submit", json={"force": True}
    )
    assert forced.status_code == 200
    assert forced.json()["accepted"] is True
    assert "override" in forced.json()["claim"]["notes"].lower()
