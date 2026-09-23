import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditMixin:
    """
    Mixin providing audit fields for all tables.
    Soft-delete only per CLAUDE.md — 20-year retention.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventBase(Base):
    """
    Immutable event store for clinical data event sourcing.
    Events are the audit trail — no separate audit_log needed.
    """

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    stream_type: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    version: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )
