"""Queue management and patient calling.

A queue ticket is a lightweight workflow object: it references a patient and,
when the visit already exists, an encounter. It owns nothing clinical - the
encounter stays the clinical record, the ticket only describes the wait.

Permanent ticket state and the transitional events that move it live in
separate tables, so a status can never be polluted by an event name (see
``app/services/queue/state_machine.py``). Every table is facility-scoped and
carries the standard audit columns, so the same row level security policy and
audit trail that protect the rest of Aifya apply unchanged.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class QueueServicePoint(AuditMixin, Base):
    """A room, counter or consulting bay a patient can be called into."""

    __tablename__ = "queue_service_points"
    __table_args__ = (
        Index("ix_queue_service_points_facility_active", "facility_id", "is_active"),
    )

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="room")
    display_label: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QueueTicket(AuditMixin, Base):
    """A patient waiting to be called."""

    __tablename__ = "queue_tickets"
    __table_args__ = (
        # The sequence restarts every day, so the day is part of the key:
        # OPD-001 exists once per facility per day, never twice in a day and
        # never blocked by yesterday's OPD-001.
        UniqueConstraint(
            "facility_id",
            "issued_on",
            "ticket_number",
            name="uq_queue_tickets_facility_day_number",
        ),
        Index("ix_queue_tickets_facility_status", "facility_id", "status"),
        Index(
            "ix_queue_tickets_facility_department_status",
            "facility_id",
            "department_id",
            "status",
        ),
        Index("ix_queue_tickets_facility_issued", "facility_id", "issued_at"),
        Index("ix_queue_tickets_encounter", "encounter_id"),
        # A caller-supplied retry key only ever names one ticket per facility.
        Index(
            "uq_queue_tickets_facility_idempotency",
            "facility_id",
            "idempotency_key",
            unique=True,
        ),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), index=True
    )
    service_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queue_service_points.id")
    )
    ticket_number: Mapped[str] = mapped_column(String(20), nullable=False)
    # The day the number was issued, so a per-day sequence stays unique.
    issued_on: Mapped[date] = mapped_column(
        Date, nullable=False, default=lambda: datetime.now(timezone.utc).date()
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triage_category: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="WAITING", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    called_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recall_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # Client retry key: a repeat POST /tickets with the same key returns the
    # ticket already issued instead of queueing the patient twice.
    idempotency_key: Mapped[str | None] = mapped_column(String(255))


class QueueEvent(Base):
    """Immutable log of every transition a ticket went through."""

    __tablename__ = "queue_events"
    __table_args__ = (
        Index("ix_queue_events_facility_ticket", "facility_id", "ticket_id"),
        Index("ix_queue_events_facility_created", "facility_id", "created_at"),
        Index(
            "ix_queue_events_facility_type_created",
            "facility_id",
            "event_type",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queue_tickets.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    service_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QueueAnnouncement(AuditMixin, Base):
    """A spoken announcement for a ticket, cached by the hash of its text.

    The audio itself lives in object storage (`storage_key`); this row is the
    index that lets a repeat call for the same text skip synthesis entirely.
    """

    __tablename__ = "queue_announcements"
    __table_args__ = (
        Index("ix_queue_announcements_facility_ticket", "facility_id", "ticket_id"),
        Index("ix_queue_announcements_facility_cache", "facility_id", "cache_key"),
    )

    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queue_tickets.id")
    )
    queue_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queue_events.id")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40))
    voice: Mapped[str | None] = mapped_column(String(60))
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
