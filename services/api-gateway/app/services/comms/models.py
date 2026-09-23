"""Pydantic models for the Patient Communication Hub."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ── Enums ──────────────────────────────────────────────────────────────────


class MessageChannel(StrEnum):
    """Supported communication channels."""

    sms = "sms"
    whatsapp = "whatsapp"
    email = "email"


class MessageStatus(StrEnum):
    """Message delivery lifecycle status."""

    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class MessageCategory(StrEnum):
    """Category of outgoing patient message."""

    appointment_reminder = "appointment_reminder"
    lab_result = "lab_result"
    prescription_alert = "prescription_alert"
    anc_reminder = "anc_reminder"
    immunization_reminder = "immunization_reminder"
    discharge_instructions = "discharge_instructions"
    follow_up = "follow_up"
    billing_notification = "billing_notification"
    custom = "custom"


# ── Templates ──────────────────────────────────────────────────────────────


class MessageTemplate(BaseModel):
    """A reusable message template with placeholder support."""

    id: uuid.UUID
    name: str
    category: MessageCategory
    channel: MessageChannel
    body_template: str = Field(
        description="Message body with {placeholder} variables"
    )
    is_active: bool = True
    language: str = Field(
        default="en", description="ISO 639-1 language code (en or sw)"
    )
    created_at: datetime
    updated_at: datetime | None = None


class MessageTemplateCreate(BaseModel):
    """Request body for creating a custom message template."""

    name: str = Field(min_length=2, max_length=200)
    category: MessageCategory
    channel: MessageChannel
    body_template: str = Field(
        min_length=5,
        max_length=1600,
        description="Message body with {placeholder} variables",
    )
    language: str = Field(
        default="en",
        pattern=r"^(en|sw)$",
        description="ISO 639-1 language code",
    )


# ── Patient Messages ──────────────────────────────────────────────────────


class PatientMessage(BaseModel):
    """A single message sent to a patient."""

    id: uuid.UUID
    patient_id: uuid.UUID
    facility_id: uuid.UUID
    channel: MessageChannel
    category: MessageCategory
    recipient_phone: str
    recipient_email: str | None = None
    subject: str | None = None
    template_id: uuid.UUID | None = None
    template_params: dict[str, str] | None = None
    body: str
    status: MessageStatus = MessageStatus.queued
    retry_count: int = 0
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


# ── Requests ──────────────────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    """Request body for sending a single patient message."""

    patient_id: uuid.UUID
    channel: MessageChannel
    category: MessageCategory
    template_id: uuid.UUID | None = None
    body: str | None = Field(
        default=None,
        max_length=1600,
        description="Custom body text. If template_id is provided, this is ignored.",
    )
    subject: str | None = Field(
        default=None,
        max_length=200,
        description="Email subject. Ignored for SMS and WhatsApp.",
    )
    template_params: dict[str, str] | None = Field(
        default=None,
        description="Placeholder values for the template.",
    )
    scheduled_at: datetime | None = Field(
        default=None,
        description="Schedule send for a future time (ISO 8601).",
    )


class BulkMessageFilter(BaseModel):
    """Filter criteria for selecting patients for bulk messaging."""

    department_id: uuid.UUID | None = None
    appointment_date: str | None = Field(
        default=None, description="ISO 8601 date string"
    )
    category_filter: MessageCategory | None = None


class BulkMessageRequest(BaseModel):
    """Request body for sending bulk messages."""

    patient_ids: list[uuid.UUID] | None = Field(
        default=None, description="Explicit list of patient IDs"
    )
    filter_criteria: BulkMessageFilter | None = Field(
        default=None,
        description="Filter criteria for selecting patients (used when patient_ids is empty)",
    )
    channel: MessageChannel
    category: MessageCategory
    template_id: uuid.UUID
    template_params: dict[str, str] | None = None


# ── Responses ─────────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    """Single message detail response."""

    id: uuid.UUID
    patient_id: uuid.UUID
    facility_id: uuid.UUID
    channel: MessageChannel
    category: MessageCategory
    recipient_phone: str
    recipient_email: str | None = None
    subject: str | None = None
    template_id: uuid.UUID | None = None
    body: str
    status: MessageStatus
    retry_count: int
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """Paginated list of messages."""

    items: list[MessageResponse]
    total: int
    page: int
    per_page: int


# ── Communication Preferences ─────────────────────────────────────────────


class CommunicationPreference(BaseModel):
    """Patient communication opt-in / opt-out preferences (Kenya DPA compliant)."""

    id: uuid.UUID
    patient_id: uuid.UUID
    facility_id: uuid.UUID
    preferred_channel: MessageChannel = MessageChannel.sms
    opt_out_categories: list[MessageCategory] = Field(default_factory=list)
    consent_given: bool = False
    consent_date: datetime | None = None
    preferred_language: str = "en"
    created_at: datetime
    updated_at: datetime | None = None


class CommunicationPreferenceUpdate(BaseModel):
    """Request body for updating patient communication preferences."""

    preferred_channel: MessageChannel | None = None
    opt_out_categories: list[MessageCategory] | None = None
    consent_given: bool | None = None
    preferred_language: str | None = None
