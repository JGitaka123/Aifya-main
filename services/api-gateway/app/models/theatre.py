import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
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


class OperatingTheatre(AuditMixin, Base):
    """Operating theatre / surgical room."""

    __tablename__ = "operating_theatres"
    __table_args__ = (Index("ix_operating_theatres_facility", "facility_id"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    theatre_type: Mapped[str] = mapped_column(
        String(30), default="general", nullable=False
    )  # general, orthopaedic, cardiac, neuro, ophthalmic, obstetric, ent, dental, minor
    status: Mapped[str] = mapped_column(
        String(20), default="available", nullable=False
    )  # available, in_use, cleaning, maintenance, closed
    floor: Mapped[str | None] = mapped_column(String(20))
    equipment: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{name, status}]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SurgicalCase(AuditMixin, Base):
    """A scheduled or completed surgical case."""

    __tablename__ = "surgical_cases"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "case_number", name="uq_surgical_cases_case_number"
        ),
        Index("ix_surgical_cases_date", "facility_id", "scheduled_date"),
        Index("ix_surgical_cases_status", "facility_id", "status"),
        Index("ix_surgical_cases_patient", "facility_id", "patient_id"),
    )

    case_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # SC-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    theatre_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operating_theatres.id")
    )

    # Scheduling
    scheduled_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    estimated_duration_min: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(20), default="elective", nullable=False
    )  # emergency, urgent, elective

    # Procedure
    procedure_name: Mapped[str] = mapped_column(String(500), nullable=False)
    procedure_code: Mapped[str | None] = mapped_column(String(20))  # ICD-10-PCS or CPT
    laterality: Mapped[str | None] = mapped_column(
        String(10)
    )  # left, right, bilateral, na
    diagnosis: Mapped[str | None] = mapped_column(Text)  # preoperative diagnosis

    # Anaesthesia
    anaesthesia_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # general, spinal, epidural, regional, local, sedation
    anaesthetist_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Surgical team
    lead_surgeon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    assistant_surgeon_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    scrub_nurse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    circulating_nurse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, preop, in_progress, in_recovery, completed, cancelled, postponed

    # Timings
    preop_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    surgery_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    surgery_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Operative details
    operative_findings: Mapped[str | None] = mapped_column(Text)
    operative_notes: Mapped[str | None] = mapped_column(Text)
    specimens: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{type, sent_to_lab, description}]
    implants: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{name, serial, manufacturer}]
    complications: Mapped[str | None] = mapped_column(Text)
    blood_loss_ml: Mapped[int | None] = mapped_column(Integer)
    postop_instructions: Mapped[str | None] = mapped_column(Text)

    # Checklists
    preop_checklist: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # WHO Surgical Safety Checklist
    timeout_checklist: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    signout_checklist: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    # Cancellation
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)
