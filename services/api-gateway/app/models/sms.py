"""
Bulk SMS campaign and delivery log models.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class SmsCampaign(AuditMixin, Base):
    """
    A bulk SMS campaign — one row per send (which may target many recipients).
    """

    __tablename__ = "sms_campaigns"
    __table_args__ = (
        Index("ix_sms_campaigns_facility_status", "facility_id", "status"),
        Index("ix_sms_campaigns_created_at", "facility_id", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # draft | sending | completed | failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SmsDeliveryLog(AuditMixin, Base):
    """
    Per-recipient delivery record. Tracks status (queued → sent → delivered)
    plus cost reported by the provider.
    """

    __tablename__ = "sms_delivery_log"
    __table_args__ = (
        Index("ix_sms_delivery_campaign", "facility_id", "campaign_id"),
        Index("ix_sms_delivery_status", "facility_id", "status"),
        Index("ix_sms_delivery_phone", "facility_id", "phone_number"),
    )

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sms_campaigns.id")
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # queued | sent | delivered | failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    cost: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_msg: Mapped[str | None] = mapped_column(Text)
