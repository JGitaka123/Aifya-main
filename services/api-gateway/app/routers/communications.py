"""
Patient Communication Hub router.
Endpoints for sending messages, managing templates, patient preferences,
and Africa's Talking-powered bulk SMS campaigns.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.services.comms.models import (
    BulkMessageRequest,
    CommunicationPreference,
    CommunicationPreferenceUpdate,
    MessageCategory,
    MessageChannel,
    MessageListResponse,
    MessageResponse,
    MessageStatus,
    MessageTemplate,
    MessageTemplateCreate,
    SendMessageRequest,
)
from app.services.comms.service import CommunicationService
from app.services.sms.bulk_sms import (
    BulkSmsResult,
    send_bulk_sms,
)
from app.services.sms.bulk_sms import (
    list_campaigns as list_sms_campaigns,
)
from app.services.sms.bulk_sms import (
    list_delivery_log as list_sms_delivery_log,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("communications"))])


# ── Send Messages ─────────────────────────────────────────────────────────────


@router.post(
    "/messages/send",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    data: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """
    Send a single message to a patient via SMS, WhatsApp, or email.
    Checks consent before sending per Kenya DPA.

    @param data: Send message request
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Created message with delivery status
    """
    service = CommunicationService(db)

    # Look up patient phone from DB
    from sqlalchemy import select

    from app.models.patient import Patient

    result = await db.execute(
        select(Patient).where(
            Patient.id == data.patient_id,
            Patient.facility_id == current_user.facility_id,
            Patient.is_deleted == False,  # noqa: E712
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    # Each channel needs its own contact detail on the patient record, so the
    # failure names the missing field instead of a generic delivery error.
    if data.channel == MessageChannel.email:
        if not patient.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient has no email address on file",
            )
    elif not patient.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient has no phone number on file",
        )

    try:
        msg = await service.send_message(
            facility_id=current_user.facility_id,
            request=data,
            recipient_phone=patient.phone_number or "",
            recipient_email=patient.email,
            created_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return MessageResponse(**msg.model_dump())


@router.post(
    "/messages/bulk",
    response_model=list[MessageResponse],
    status_code=status.HTTP_201_CREATED,
)
async def send_bulk_messages(
    data: BulkMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> list[MessageResponse]:
    """
    Send bulk messages to multiple patients. Admin only.

    @param data: Bulk message request
    @param db: Database session
    @param current_user: Authenticated admin from JWT
    @returns List of created messages
    """
    service = CommunicationService(db)
    messages = await service.send_bulk_messages(
        facility_id=current_user.facility_id,
        request=data,
    )
    return [MessageResponse(**m.model_dump()) for m in messages]


# ── Message History ───────────────────────────────────────────────────────────


@router.get(
    "/messages",
    response_model=MessageListResponse,
)
async def get_messages(
    patient_id: uuid.UUID | None = Query(None),
    channel: str | None = Query(None),
    message_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageListResponse:
    """
    Get paginated message history for the facility.

    @param patient_id: Optional patient filter
    @param channel: Optional channel filter
    @param message_status: Optional status filter
    @param page: Page number
    @param per_page: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated message list
    """
    service = CommunicationService(db)

    status_filter = MessageStatus(message_status) if message_status else None
    channel_filter = MessageChannel(channel) if channel else None

    return await service.get_message_history(
        facility_id=current_user.facility_id,
        patient_id=patient_id,
        page=page,
        per_page=per_page,
        status=status_filter,
        channel=channel_filter,
    )


@router.get(
    "/messages/{message_id}",
    response_model=MessageResponse,
)
async def get_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """
    Get a single message detail.

    @param message_id: Message UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Message detail
    """
    service = CommunicationService(db)
    msg = await service.get_message_detail(
        facility_id=current_user.facility_id,
        message_id=message_id,
    )
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    return msg


# ── Preferences ───────────────────────────────────────────────────────────────


@router.get(
    "/preferences/{patient_id}",
    response_model=CommunicationPreference,
)
async def get_preferences(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommunicationPreference:
    """
    Get communication preferences for a patient.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Communication preference record
    """
    service = CommunicationService(db)
    return await service.get_patient_preferences(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
    )


@router.put(
    "/preferences/{patient_id}",
    response_model=CommunicationPreference,
)
async def update_preferences(
    patient_id: uuid.UUID,
    data: CommunicationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommunicationPreference:
    """
    Update communication preferences for a patient.

    @param patient_id: Patient UUID
    @param data: Preference fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated preferences
    """
    service = CommunicationService(db)
    return await service.update_patient_preferences(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        data=data,
    )


# ── Templates ─────────────────────────────────────────────────────────────────


@router.get(
    "/templates",
    response_model=list[MessageTemplate],
)
async def list_templates(
    language: str | None = Query(None),
    channel: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[MessageTemplate]:
    """
    List available message templates.

    @param language: Optional language filter (en/sw)
    @param channel: Optional channel filter
    @param category: Optional category filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of active templates
    """
    service = CommunicationService(db)

    channel_filter = MessageChannel(channel) if channel else None
    category_filter = MessageCategory(category) if category else None

    return await service.list_templates(
        language=language,
        channel=channel_filter,
        category=category_filter,
    )


@router.post(
    "/templates",
    response_model=MessageTemplate,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: MessageTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> MessageTemplate:
    """
    Create a custom message template. Admin only.

    @param data: Template creation data
    @param db: Database session
    @param current_user: Authenticated admin from JWT
    @returns Created template
    """
    service = CommunicationService(db)
    return await service.create_template(
        facility_id=current_user.facility_id,
        data=data,
    )


# ── Bulk SMS Campaigns ────────────────────────────────────────────────────────


_RecipientFilter = Literal[
    "all_patients", "all_staff", "appointments_today", "custom"
]


class BulkSmsApiRequest(BaseModel):
    """
    Request to send a bulk SMS campaign.

    @param name: Human-readable campaign name
    @param message: SMS body (max 480 chars = 3 SMS segments)
    @param recipient_filter: Audience selector
    @param recipients: Phone numbers when recipient_filter is "custom"
    @param sender_id: Alphanumeric sender ID (must be registered with provider)
    """

    name: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=480)
    recipient_filter: _RecipientFilter = "custom"
    recipients: list[str] = []
    sender_id: str = Field(default="AIFYA", max_length=11)


class SmsCampaignResponse(BaseModel):
    """Single SMS campaign in list responses."""

    id: uuid.UUID
    name: str
    message: str
    recipient_count: int
    sent_count: int
    failed_count: int
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SmsDeliveryLogItem(BaseModel):
    """Single delivery log row."""

    id: uuid.UUID
    campaign_id: uuid.UUID | None
    phone_number: str
    status: str
    provider_message_id: str | None
    cost: float
    sent_at: datetime | None
    error_msg: str | None

    model_config = {"from_attributes": True}


async def _resolve_recipients(
    db: AsyncSession,
    facility_id: uuid.UUID,
    request: BulkSmsApiRequest,
) -> list[str]:
    """
    Resolve the recipient list from the campaign filter.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param request: Bulk SMS request
    @returns List of phone numbers (deduplication happens in send_bulk_sms)
    """
    if request.recipient_filter == "custom":
        return [p for p in request.recipients if p]

    if request.recipient_filter == "all_patients":
        from app.models.patient import Patient

        result = await db.execute(
            select(Patient.phone_number).where(
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
                Patient.phone_number.is_not(None),
            )
        )
        return [row[0] for row in result.all() if row[0]]

    if request.recipient_filter == "all_staff":
        from app.models.staff import Staff

        result = await db.execute(
            select(Staff.phone).where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
                Staff.phone.is_not(None),
            )
        )
        return [row[0] for row in result.all() if row[0]]

    if request.recipient_filter == "appointments_today":
        from app.models.appointment import Appointment
        from app.models.patient import Patient

        today = datetime.now(UTC).date()
        result = await db.execute(
            select(Patient.phone_number)
            .join(Appointment, Appointment.patient_id == Patient.id)
            .where(
                Appointment.facility_id == facility_id,
                Appointment.appointment_date == today,
                Appointment.is_deleted == False,  # noqa: E712
                Patient.is_deleted == False,  # noqa: E712
                Patient.phone_number.is_not(None),
            )
            .distinct()
        )
        return [row[0] for row in result.all() if row[0]]

    return []


@router.post(
    "/bulk-sms",
    response_model=BulkSmsResult,
    status_code=status.HTTP_201_CREATED,
)
async def send_bulk_sms_campaign(
    data: BulkSmsApiRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> BulkSmsResult:
    """
    Send a bulk SMS campaign. Admin only.

    @param data: Campaign request
    @param db: Database session
    @param current_user: Authenticated admin from JWT
    @returns Campaign result with sent/failed counts
    @raises HTTPException 400: If recipient resolution returns nothing
    """
    recipients = await _resolve_recipients(db, current_user.facility_id, data)
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipients matched the selected filter",
        )

    return await send_bulk_sms(
        db,
        facility_id=current_user.facility_id,
        name=data.name,
        recipients=recipients,
        message=data.message,
        sender_id=data.sender_id,
        created_by=current_user.user_id,
    )


@router.get(
    "/sms-campaigns",
    response_model=list[SmsCampaignResponse],
)
async def list_bulk_sms_campaigns(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SmsCampaignResponse]:
    """
    List recent bulk SMS campaigns for the facility.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of campaigns
    """
    rows = await list_sms_campaigns(db, current_user.facility_id)
    return [SmsCampaignResponse.model_validate(r) for r in rows]


@router.get(
    "/sms-delivery-log",
    response_model=list[SmsDeliveryLogItem],
)
async def get_sms_delivery_log(
    campaign_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SmsDeliveryLogItem]:
    """
    Get the SMS delivery log, optionally filtered by campaign.

    @param campaign_id: Optional campaign filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of delivery records
    """
    rows = await list_sms_delivery_log(
        db, current_user.facility_id, campaign_id=campaign_id
    )
    return [SmsDeliveryLogItem.model_validate(r) for r in rows]
