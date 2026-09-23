"""
M-Pesa STK Push service — extends the Daraja client with persistence.
Stores STK push requests in `mpesa_stk_requests` for tracking, polling,
and reconciliation. Wraps DarajaClient.stk_push so callers get one entry
point that both initiates the payment and persists state.

Per CLAUDE.md:
- All POST endpoints support X-Idempotency-Key
- Multi-tenant: every row has facility_id from JWT
- Soft-delete only — never hard delete
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.mpesa import MpesaStkRequest
from app.services.mpesa.daraja import (
    DarajaClient,
    STKPushRequest,
    STKPushResponse,
    get_daraja_config,
)

logger = get_logger(__name__)


class StkPushService:
    """
    Service that initiates STK Push and stores the request lifecycle.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the STK Push service.

        @param db: Async database session
        """
        self.db = db

    async def initiate_stk_push(
        self,
        facility_id: uuid.UUID,
        phone_number: str,
        amount: int,
        reference: str,
        description: str = "Hospital Payment",
        invoice_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> tuple[STKPushResponse, MpesaStkRequest | None]:
        """
        Initiate an STK Push and persist it for tracking.

        @param facility_id: Tenant facility UUID
        @param phone_number: Customer phone (any Kenyan format)
        @param amount: Amount in KES (whole number)
        @param reference: Account reference (typically invoice number)
        @param description: Transaction description
        @param invoice_id: Linked invoice UUID
        @param patient_id: Linked patient UUID
        @param created_by: User initiating the request
        @returns Tuple of (Daraja API response, persisted request row)
        """
        config = get_daraja_config()
        if not config:
            return (
                STKPushResponse(
                    error=(
                        "M-Pesa not configured. Set MPESA_CONSUMER_KEY, "
                        "MPESA_CONSUMER_SECRET, MPESA_SHORTCODE, MPESA_PASSKEY."
                    )
                ),
                None,
            )

        client = DarajaClient(config)
        api_response = await client.stk_push(
            STKPushRequest(
                phone_number=phone_number,
                amount=amount,
                account_reference=reference[:12],
                description=description[:13],
            )
        )

        # Persist row regardless of success — failed pushes are auditable too
        row = MpesaStkRequest(
            id=uuid.uuid4(),
            facility_id=facility_id,
            invoice_id=invoice_id,
            patient_id=patient_id,
            phone_number=phone_number,
            amount=Decimal(amount),
            reference=reference,
            description=description,
            checkout_request_id=api_response.checkout_request_id or f"FAILED-{uuid.uuid4()}",
            merchant_request_id=api_response.merchant_request_id or "",
            status="pending" if api_response.success else "failed",
            result_code=None,
            result_desc=api_response.error or api_response.response_description or "",
            created_by=created_by,
        )
        self.db.add(row)
        await self.db.flush()

        logger.info(
            "stk_push_persisted",
            stk_request_id=str(row.id),
            checkout_request_id=row.checkout_request_id,
            facility_id=str(facility_id),
            success=api_response.success,
        )
        return api_response, row

    async def get_status(
        self,
        facility_id: uuid.UUID,
        checkout_request_id: str,
    ) -> MpesaStkRequest | None:
        """
        Get the current status of an STK Push by checkout_request_id.

        @param facility_id: Tenant facility UUID (multi-tenant scoping)
        @param checkout_request_id: Daraja checkout request ID
        @returns The stored STK request row, or None if not found
        """
        result = await self.db.execute(
            select(MpesaStkRequest).where(
                MpesaStkRequest.facility_id == facility_id,
                MpesaStkRequest.checkout_request_id == checkout_request_id,
                MpesaStkRequest.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        checkout_request_id: str,
        result_code: int,
        result_desc: str,
        mpesa_receipt: str | None,
        transaction_date: str | None,
    ) -> MpesaStkRequest | None:
        """
        Mark an STK Push as completed (success or failure) from a callback.
        Idempotent — repeat callbacks for the same checkout_request_id are safe.

        @param checkout_request_id: Daraja checkout request ID
        @param result_code: 0 = success, else failed
        @param result_desc: Result description from Safaricom
        @param mpesa_receipt: M-Pesa receipt number on success
        @param transaction_date: Transaction date (YYYYMMDDHHMMSS string from Daraja)
        @returns Updated request row, or None if not found
        """
        result = await self.db.execute(
            select(MpesaStkRequest).where(
                MpesaStkRequest.checkout_request_id == checkout_request_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            logger.warning(
                "stk_callback_for_unknown_request",
                checkout_request_id=checkout_request_id,
            )
            return None

        # Idempotency — if already terminal, do nothing
        if row.status in ("success", "failed", "timeout"):
            return row

        row.result_code = result_code
        row.result_desc = result_desc[:500] if result_desc else ""
        if result_code == 0:
            row.status = "success"
            row.mpesa_receipt_number = mpesa_receipt
            row.transaction_date = _parse_daraja_timestamp(transaction_date)
        else:
            row.status = "failed"
        row.completed_at = datetime.now(UTC)
        await self.db.flush()
        return row


def _parse_daraja_timestamp(ts: str | None) -> datetime | None:
    """
    Parse a Daraja YYYYMMDDHHMMSS timestamp string into UTC datetime.

    @param ts: Raw timestamp string from Daraja callback (may be None)
    @returns Parsed datetime in UTC, or None on parse failure
    """
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None
