"""
Bulk SMS via Africa's Talking — the standard SMS gateway in Kenya.
Supports sending to up to 100 recipients per API call (the per-call limit
is enforced by chunking). Records every recipient to sms_delivery_log and
exposes the campaign progress for the UI.

Per CLAUDE.md:
- All POST endpoints support X-Idempotency-Key
- Multi-tenant: every row has facility_id
- Soft-delete only — never hard delete
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.config import settings
from app.models.sms import SmsCampaign, SmsDeliveryLog

logger = get_logger(__name__)

_AT_PROD_URL = "https://api.africastalking.com/version1/messaging"
_AT_SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
_BATCH_SIZE = 100


class BulkSmsResult(BaseModel):
    """
    Outcome of a bulk SMS send.

    @param campaign_id: UUID of the persisted campaign row
    @param recipient_count: Total recipients
    @param sent_count: Successfully accepted by the gateway
    @param failed_count: Rejected by the gateway
    @param status: Final campaign status
    @param error: Optional error if the send aborted entirely
    """

    campaign_id: uuid.UUID
    recipient_count: int
    sent_count: int
    failed_count: int
    status: str
    error: str | None = None


def _normalize_phone(phone: str) -> str:
    """
    Normalize a phone number to E.164 (+254XXXXXXXXX) where possible.

    @param phone: Phone in any Kenyan format
    @returns Normalized E.164 phone, or the input if it already starts with +
    """
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        return p
    if p.startswith("0") and len(p) >= 10:
        return "+254" + p[1:]
    if p.startswith("254"):
        return "+" + p
    if p.startswith("7") or p.startswith("1"):
        return "+254" + p
    return p


def _chunk(items: list[str], size: int) -> Iterable[list[str]]:
    """
    Yield successive `size`-sized chunks from `items`.

    @param items: Source list
    @param size: Chunk size
    """
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def send_bulk_sms(
    db: AsyncSession,
    *,
    facility_id: uuid.UUID,
    name: str,
    recipients: list[str],
    message: str,
    sender_id: str = "AIFYA",
    created_by: uuid.UUID | None = None,
) -> BulkSmsResult:
    """
    Send a bulk SMS campaign via Africa's Talking.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param name: Campaign label shown in the UI
    @param recipients: List of phone numbers (any Kenyan format)
    @param message: SMS body
    @param sender_id: Registered alphanumeric sender ID (defaults to AIFYA)
    @param created_by: User initiating the campaign
    @returns Outcome with sent/failed counts
    """
    deduped = list({_normalize_phone(p): None for p in recipients if p}.keys())
    campaign = SmsCampaign(
        id=uuid.uuid4(),
        facility_id=facility_id,
        name=name,
        message=message,
        recipient_count=len(deduped),
        sent_count=0,
        failed_count=0,
        status="sending",
        created_by=created_by,
    )
    db.add(campaign)
    await db.flush()

    if not deduped:
        campaign.status = "completed"
        campaign.completed_at = datetime.now(UTC)
        return BulkSmsResult(
            campaign_id=campaign.id,
            recipient_count=0,
            sent_count=0,
            failed_count=0,
            status="completed",
        )

    if not settings.at_username or not settings.at_api_key:
        # Mock mode — log every recipient as "sent" but flag mock provider
        for phone in deduped:
            db.add(
                SmsDeliveryLog(
                    id=uuid.uuid4(),
                    facility_id=facility_id,
                    campaign_id=campaign.id,
                    phone_number=phone,
                    message=message,
                    status="sent",
                    provider_message_id=f"MOCK-{uuid.uuid4().hex[:12]}",
                    cost=Decimal("0"),
                    sent_at=datetime.now(UTC),
                    error_msg="MOCK: AT_USERNAME/AT_API_KEY not configured",
                )
            )
        campaign.sent_count = len(deduped)
        campaign.status = "completed"
        campaign.completed_at = datetime.now(UTC)
        await db.flush()
        logger.warning(
            "bulk_sms_mock_mode",
            campaign_id=str(campaign.id),
            recipient_count=len(deduped),
        )
        return BulkSmsResult(
            campaign_id=campaign.id,
            recipient_count=len(deduped),
            sent_count=len(deduped),
            failed_count=0,
            status="completed",
            error="MOCK: AT_USERNAME/AT_API_KEY not configured",
        )

    base_url = _AT_SANDBOX_URL if settings.at_sandbox else _AT_PROD_URL
    sent = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for chunk in _chunk(deduped, _BATCH_SIZE):
            ok, statuses = await _send_chunk(
                client=client,
                url=base_url,
                phones=chunk,
                message=message,
                sender_id=sender_id or settings.at_sender_id or "AIFYA",
            )
            for phone, info in statuses.items():
                db.add(
                    SmsDeliveryLog(
                        id=uuid.uuid4(),
                        facility_id=facility_id,
                        campaign_id=campaign.id,
                        phone_number=phone,
                        message=message,
                        status=info["status"],
                        provider_message_id=info.get("messageId"),
                        cost=Decimal(str(info.get("cost", "0"))),
                        sent_at=datetime.now(UTC),
                        error_msg=info.get("error"),
                    )
                )
                if info["status"] == "sent":
                    sent += 1
                else:
                    failed += 1
            if not ok and not statuses:
                # Whole chunk failed — log each as failed
                for phone in chunk:
                    db.add(
                        SmsDeliveryLog(
                            id=uuid.uuid4(),
                            facility_id=facility_id,
                            campaign_id=campaign.id,
                            phone_number=phone,
                            message=message,
                            status="failed",
                            cost=Decimal("0"),
                            sent_at=datetime.now(UTC),
                            error_msg="Provider request failed",
                        )
                    )
                    failed += 1

    campaign.sent_count = sent
    campaign.failed_count = failed
    campaign.status = "completed" if failed == 0 else (
        "failed" if sent == 0 else "completed"
    )
    campaign.completed_at = datetime.now(UTC)
    await db.flush()

    return BulkSmsResult(
        campaign_id=campaign.id,
        recipient_count=len(deduped),
        sent_count=sent,
        failed_count=failed,
        status=campaign.status,
    )


async def _send_chunk(
    *,
    client: httpx.AsyncClient,
    url: str,
    phones: list[str],
    message: str,
    sender_id: str,
) -> tuple[bool, dict[str, dict[str, str | float]]]:
    """
    Send a single chunk (≤100 recipients) to Africa's Talking.

    @param client: Shared httpx async client
    @param url: AT API URL (prod or sandbox)
    @param phones: Phone numbers in this chunk
    @param message: SMS body
    @param sender_id: Sender ID
    @returns (ok flag, per-recipient status dict)
    """
    headers = {
        "apiKey": settings.at_api_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    payload = {
        "username": settings.at_username,
        "to": ",".join(phones),
        "message": message,
        "from": sender_id,
    }

    try:
        response = await client.post(url, headers=headers, data=payload)
    except httpx.HTTPError as exc:
        logger.error("bulk_sms_network_error", error=str(exc))
        return False, {}

    if response.status_code != 201:
        logger.error(
            "bulk_sms_api_error",
            status_code=response.status_code,
            body=response.text[:500],
        )
        return False, {}

    data = response.json()
    statuses: dict[str, dict[str, str | float]] = {}
    for r in data.get("SMSMessageData", {}).get("Recipients", []):
        phone = r.get("number", "")
        sc = r.get("statusCode", 0)
        accepted = sc in (100, 101)
        statuses[phone] = {
            "status": "sent" if accepted else "failed",
            "messageId": r.get("messageId", ""),
            "cost": r.get("cost", "0"),
        }
        if not accepted:
            statuses[phone]["error"] = r.get("status", "Rejected by provider")

    # Any phone the provider didn't return — mark as failed
    for phone in phones:
        if phone not in statuses:
            statuses[phone] = {
                "status": "failed",
                "error": "No status returned by provider",
                "cost": "0",
            }
    return True, statuses


async def list_campaigns(
    db: AsyncSession,
    facility_id: uuid.UUID,
    limit: int = 50,
) -> list[SmsCampaign]:
    """
    List recent SMS campaigns for the facility.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param limit: Max number of campaigns to return
    @returns List of campaigns ordered by created_at descending
    """
    result = await db.execute(
        select(SmsCampaign)
        .where(
            SmsCampaign.facility_id == facility_id,
            SmsCampaign.is_deleted == False,  # noqa: E712
        )
        .order_by(SmsCampaign.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_delivery_log(
    db: AsyncSession,
    facility_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[SmsDeliveryLog]:
    """
    List SMS delivery records, optionally filtered by campaign.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param campaign_id: Optional campaign filter
    @param limit: Max rows to return
    @returns Delivery log rows ordered by sent_at descending
    """
    stmt = (
        select(SmsDeliveryLog)
        .where(
            SmsDeliveryLog.facility_id == facility_id,
            SmsDeliveryLog.is_deleted == False,  # noqa: E712
        )
        .order_by(SmsDeliveryLog.sent_at.desc())
        .limit(limit)
    )
    if campaign_id is not None:
        stmt = stmt.where(SmsDeliveryLog.campaign_id == campaign_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
