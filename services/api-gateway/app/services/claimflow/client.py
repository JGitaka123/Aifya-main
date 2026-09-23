"""Client for the ClaimFlow validator service (SHA claim rule engine).

Builds the rule-engine request payload from an InsuranceClaim and related
records, calls the stateless validator over HTTP, and returns a normalized
result. Infrastructure failures never hard-block the caller — an
unreachable validator yields decision ``UNAVAILABLE`` so the claim flow
can decide policy (warn vs. proceed).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.models.facility import Facility
from app.models.insurance import InsuranceClaim, InsuranceScheme
from app.models.patient import Patient

_logger = logging.getLogger(__name__)

# SHA claim types the rule engine understands, keyed off encounter/scheme.
_DEFAULT_CLAIM_TYPE = "OUTPATIENT"


@dataclass
class ClaimValidationResult:
    """Normalized outcome of a ClaimFlow validation."""

    decision: str  # PASSED | WARNING | FAILED | UNAVAILABLE
    total_rules: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    fix_report_markdown: str = ""
    rulepack_version: str | None = None

    @property
    def blocking(self) -> bool:
        """Whether this result should block submission (a hard failure)."""
        return self.decision == "FAILED"


class ClaimFlowClient:
    """Thin HTTP client for the ClaimFlow validator service."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._base_url = (base_url or settings.claimflow_validator_url).rstrip("/")
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        """Whether a validator URL is configured."""
        return bool(self._base_url)

    def build_payload(
        self,
        claim: InsuranceClaim,
        patient: Patient | None,
        scheme: InsuranceScheme | None,
        facility: Facility | None,
    ) -> dict[str, Any]:
        """
        Map platform records into the rule engine's request shape.

        Only the structured claim/line/registry data the platform has today
        is populated; document/OCR-dependent rules degrade to INCOMPLETE in
        the engine until the ml-service pipeline is wired.

        @param claim: The claim being validated
        @param patient: The claim's patient
        @param scheme: The insurance scheme (SHA)
        @param facility: The facility
        @returns JSON-serializable request body for POST /validate
        """
        items: list[dict[str, Any]] = claim.claim_items or []
        lines = [
            {
                "id": str(i),
                "shaServiceCode": item.get("code"),
                "description": item.get("service"),
                "quantity": item.get("quantity", 1),
                "unitPrice": item.get("amount"),
                "totalAmount": item.get("amount"),
            }
            for i, item in enumerate(items)
            if isinstance(item, dict)
        ]
        diagnoses: list[str] = claim.diagnosis_codes or []
        primary_dx = diagnoses[0] if diagnoses else None

        return {
            "claim": {
                "id": str(claim.id),
                "claimType": _DEFAULT_CLAIM_TYPE,
                "tenantId": str(claim.facility_id),
                "facilityId": str(claim.facility_id),
                "patientShaId": claim.member_number,
                "patientName": (
                    f"{patient.first_name} {patient.last_name}".strip()
                    if patient
                    else ""
                ),
                "primaryDiagnosisCode": primary_dx,
                "totalAmount": claim.claim_amount,
                "lines": lines,
            },
            "facilityContext": {
                "facilityId": str(claim.facility_id),
                "facilityCode": getattr(facility, "code", None) if facility else None,
                "facilityName": getattr(facility, "name", None) if facility else None,
                "facilityTier": getattr(facility, "keph_level", None) if facility else None,
            },
            # Structured lookups the platform can supply today. Tariff/ICD
            # reference data is passed through when available (empty is safe —
            # the engine marks those rules INCOMPLETE, never crashes).
            "tariffs": [],
            "registryResults": {"available": False},
            "locale": "en",
        }

    async def validate(
        self,
        claim: InsuranceClaim,
        patient: Patient | None,
        scheme: InsuranceScheme | None,
        facility: Facility | None,
        auth_token: str | None = None,
    ) -> ClaimValidationResult:
        """
        Validate a claim via the ClaimFlow service.

        @param claim: Claim to validate
        @param patient: Claim patient
        @param scheme: Insurance scheme
        @param facility: Facility
        @param auth_token: Bearer token to forward for Keycloak verification
        @returns Normalized validation result (UNAVAILABLE if the service fails)
        """
        if not self.configured:
            return ClaimValidationResult(decision="UNAVAILABLE")

        payload = self.build_payload(claim, patient, scheme, facility)
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.post(
                    f"{self._base_url}/validate", json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            _logger.warning("claimflow.validate_failed claim=%s error=%s", claim.id, exc)
            return ClaimValidationResult(decision="UNAVAILABLE")

        return ClaimValidationResult(
            decision=data.get("decision", "UNAVAILABLE"),
            total_rules=data.get("totalRules", 0),
            findings=data.get("results", []),
            fix_report_markdown=data.get("fixReportMarkdown", ""),
            rulepack_version=data.get("rulepackVersion"),
        )
