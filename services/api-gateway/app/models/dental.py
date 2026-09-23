import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class DentalChart(AuditMixin, Base):
    """Patient dental chart — persistent tooth-level status record."""

    __tablename__ = "dental_charts"
    __table_args__ = (
        Index("ix_dental_charts_facility", "facility_id"),
        Index("ix_dental_charts_patient", "facility_id", "patient_id", unique=True),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    # Per-tooth status keyed by FDI tooth number, with status and clinical notes.
    teeth: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    # Periodontal notes
    periodontal_status: Mapped[str | None] = mapped_column(Text)
    occlusion_notes: Mapped[str | None] = mapped_column(Text)
    last_xray_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class DentalVisit(AuditMixin, Base):
    """A dental visit / encounter."""

    __tablename__ = "dental_visits"
    __table_args__ = (
        Index("ix_dental_visits_date", "facility_id", "visit_date"),
        Index("ix_dental_visits_patient", "facility_id", "patient_id"),
        Index("ix_dental_visits_status", "facility_id", "status"),
    )

    visit_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # DV-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    dentist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    visit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chief_complaint: Mapped[str | None] = mapped_column(Text)
    examination_findings: Mapped[str | None] = mapped_column(Text)

    # Procedures done in this visit
    procedures: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{tooth, surface, procedure_type, material, notes}]

    diagnosis: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, in_progress, completed, cancelled

    notes: Mapped[str | None] = mapped_column(Text)


class DentalTreatmentPlan(AuditMixin, Base):
    """Planned dental treatments for a patient."""

    __tablename__ = "dental_treatment_plans"
    __table_args__ = (
        Index("ix_dental_treatment_plans_patient", "facility_id", "patient_id"),
        Index("ix_dental_treatment_plans_status", "facility_id", "status"),
    )

    plan_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # DP-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    dentist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    diagnosis: Mapped[str | None] = mapped_column(Text)

    # Plan items: [{tooth, procedure_type, priority, estimated_cost, status, notes}]
    plan_items: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )

    total_estimated_cost: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, approved, in_progress, completed, cancelled
    notes: Mapped[str | None] = mapped_column(Text)
