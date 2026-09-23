"""
SHA (Social Health Authority) e-claims submission client.

Submits validated claims to the SHA / AfyaLink e-claims API and polls
claim status. Submission is idempotent per claim number (the client sends
an idempotency key), retries transient failures with backoff, and — when
SHA_ECLAIMS_URL is not configured — returns a clearly-labelled mock
reference so the flow is testable without live credentials.

Real credentials/spec are required to point this at production; the
request/response mapping below follows the documented AfyaLink e-claims
envelope and can be adjusted when the sandbox is available.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from structlog import get_logger

from app.config import settings

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5


@dataclass
class ShaSubmissionResult:
    """Outcome of an e-claims submission attempt."""

    accepted: bool
    sha_reference: str | None
    status: str  # submitted | rejected | error | mock
    message: str = ""
    mock: bool = False


class ShaSubmissionClient:
    """HTTP client for SHA e-claims submission + status polling."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base_url = (base_url or settings.sha_eclaims_url).rstrip("/")
        self._api_key = api_key or settings.sha_eclaims_api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        """Whether a live SHA e-claims endpoint is configured."""
        return bool(self._base_url)

    def _headers(self, idempotency_key: str) -> dict[str, str]:
        """Build request headers including auth + idempotency."""
        headers = {"Idempotency-Key": idempotency_key}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def submit(
        self,
        claim_number: str,
        member_number: str,
        amount_cents: int,
        diagnosis_codes: list[str],
        items: list[dict],
    ) -> ShaSubmissionResult:
        """
        Submit a claim to SHA e-claims. Idempotent per claim_number.

        @param claim_number: Facility claim number (idempotency key)
        @param member_number: SHA membership number
        @param amount_cents: Claimed amount in KES cents
        @param diagnosis_codes: ICD codes
        @param items: Claim line items
        @returns Submission result with the SHA reference on acceptance
        """
        if not self.configured:
            # Mock mode — clearly labelled so it is never mistaken for a real
            # SHA acknowledgement.
            logger.warning("sha_eclaims_not_configured", claim=claim_number)
            return ShaSubmissionResult(
                accepted=True,
                sha_reference=f"MOCK-SHA-{claim_number}",
                status="mock",
                message="SHA e-claims endpoint not configured; mock reference issued.",
                mock=True,
            )

        payload = {
            "claimNumber": claim_number,
            "memberNumber": member_number,
            "amountKes": amount_cents / 100,
            "diagnosisCodes": diagnosis_codes,
            "items": items,
        }

        last_error = ""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as http:
                    resp = await http.post(
                        f"{self._base_url}/claims",
                        json=payload,
                        headers=self._headers(claim_number),
                    )
                if resp.status_code in (200, 201, 202):
                    data = resp.json()
                    return ShaSubmissionResult(
                        accepted=True,
                        sha_reference=data.get("shaReference") or data.get("reference"),
                        status="submitted",
                        message=data.get("message", ""),
                    )
                if resp.status_code in (400, 409, 422):
                    # Deterministic rejection — do not retry.
                    data = resp.json() if resp.content else {}
                    return ShaSubmissionResult(
                        accepted=False,
                        sha_reference=None,
                        status="rejected",
                        message=data.get("message", f"SHA rejected ({resp.status_code})"),
                    )
                last_error = f"HTTP {resp.status_code}"
            except Exception as exc:  # transient — retry
                last_error = str(exc)

            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

        logger.error(
            "sha_eclaims_submit_failed", claim=claim_number, error=last_error
        )
        return ShaSubmissionResult(
            accepted=False,
            sha_reference=None,
            status="error",
            message=f"SHA submission failed after {_MAX_ATTEMPTS} attempts: {last_error}",
        )

    async def check_status(self, sha_reference: str) -> str | None:
        """
        Poll SHA for a claim's processing status.

        @param sha_reference: SHA system reference from submission
        @returns SHA status string, or None when unavailable/unconfigured
        """
        if not self.configured:
            return None
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                resp = await http.get(
                    f"{self._base_url}/claims/{sha_reference}",
                    headers=self._headers(sha_reference),
                )
                resp.raise_for_status()
                return resp.json().get("status")
        except Exception as exc:
            logger.warning(
                "sha_eclaims_status_failed", reference=sha_reference, error=str(exc)
            )
            return None
