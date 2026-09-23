"""Patient communication models.

Two facility-scoped tables that make the Communication Hub durable:

* ``patient_messages`` — the outbound delivery log (SMS, WhatsApp, email).
* ``communication_preferences`` — per-patient consent and channel preference,
  which is the Kenya Data Protection Act consent record.

Both carry ``facility_id`` via ``AuditMixin``, so the tenant RLS policies
created alongside them in migration 022 isolate them like every other table.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class PatientMessage(AuditMixin, Base):
    """
    One outbound patient message.

    The Communication Hub history reads from this table, so a message
    outlives the request that created it instead of vanishing with the
    in-memory store it used to live in.
    """

    __tablename__ = "patient_messages"
    __table_args__ = (
        Index("ix_patient_messages_facility_created", "facility_id", "created_at"),
        Index("ix_patient_messages_patient", "facility_id", "patient_id"),
        Index("ix_patient_messages_status", "facility_id", "status"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # sms | whatsapp | email
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    # appointment_reminder | lab_result | ... | custom
    category: Mapped[str] = mapped_column(String(40), nullable=False)

    # Populated for SMS and WhatsApp; empty for email.
    recipient_phone: Mapped[str] = mapped_column(
        String(20), nullable=False, default=""
    )
    # Populated for email.
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    # Subject line, used by the email channel.
    subject: Mapped[str | None] = mapped_column(String(200))

    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    template_params: Mapped[dict | None] = mapped_column(JSONB)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # queued | sent | delivered | read | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Why a message was not delivered, e.g. "SMTP delivery is not configured".
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(120))


class CommunicationPreference(AuditMixin, Base):
    """
    Per-patient consent and channel preference.

    One row per patient per facility; the opt-out list and consent flag are
    what ``CommunicationService._check_consent`` enforces before sending.
    """

    __tablename__ = "communication_preferences"
    __table_args__ = (
        UniqueConstraint(
            "facility_id",
            "patient_id",
            name="uq_communication_preferences_patient",
        ),
        Index("ix_communication_preferences_facility", "facility_id"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # sms | whatsapp | email
    preferred_channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sms"
    )
    opt_out_categories: Mapped[list | None] = mapped_column(JSONB, default=list)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_language: Mapped[str] = mapped_column(
        String(5), nullable=False, default="en"
    )