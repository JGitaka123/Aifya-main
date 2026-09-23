import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Referral(AuditMixin, Base):
    """
    Patient referral between departments or to an external facility.
    """

    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "referral_number", name="uq_referrals_referral_number"
        ),
        Index("ix_referrals_status", "facility_id", "status"),
        Index("ix_referrals_patient", "facility_id", "patient_id"),
        Index("ix_referrals_date", "facility_id", "referral_date"),
        Index("ix_referrals_type", "facility_id", "referral_type"),
    )

    referral_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # REF-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    # Set when the referral was raised from an emergency visit.
    emergency_visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emergency_visits.id")
    )

    # Type
    referral_type: Mapped[str] = mapped_column(
        String(20), default="internal", nullable=False
    )  # internal, external
    direction: Mapped[str] = mapped_column(
        String(20), default="outgoing", nullable=False
    )  # outgoing, incoming

    # Referring side
    referring_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    referring_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    referring_facility_name: Mapped[str | None] = mapped_column(String(200))

    # Receiving side
    receiving_doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    receiving_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    receiving_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id")
    )
    receiving_facility_name: Mapped[str | None] = mapped_column(String(200))
    receiving_facility_mfl: Mapped[str | None] = mapped_column(String(20))  # MFL code

    # Clinical
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(String(500))
    urgency: Mapped[str] = mapped_column(
        String(20), default="routine", nullable=False
    )  # emergency, urgent, routine

    # Status
    referral_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, sent, received, accepted, declined, completed, cancelled

    # Response
    response_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_notes: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(Text)

    # Attachments
    attachments: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{file_key, filename, type}]
    notes: Mapped[str | None] = mapped_column(Text)
