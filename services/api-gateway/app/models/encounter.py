import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import AuditMixin

if TYPE_CHECKING:
    from app.models.patient import Patient


class Encounter(AuditMixin, Base):
    """
    Clinical encounter — OPD visit, IPD admission, emergency, MCH visit, etc.
    Event-sourced: writes to events table, reads from this materialized view.
    """

    __tablename__ = "encounters"
    __table_args__ = (
        Index("ix_encounters_facility_patient", "facility_id", "patient_id"),
        Index("ix_encounters_facility_status", "facility_id", "status"),
        Index("ix_encounters_facility_date", "facility_id", "encounter_date"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # opd, ipd, emergency, mch, dental, surgical, follow_up

    encounter_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Department and provider
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    attending_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    nurse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # Queue / triage
    queue_number: Mapped[int | None] = mapped_column(Integer)
    triage_category: Mapped[str | None] = mapped_column(
        String(20)
    )  # SATS category: emergency, urgent, standard, non_urgent, or dead
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="waiting", nullable=False
    )  # waiting, in_consultation, completed, admitted, discharged, cancelled

    # Chief complaint
    chief_complaint: Mapped[str | None] = mapped_column(Text)

    # Disposition
    disposition: Mapped[str | None] = mapped_column(
        String(30)
    )  # discharged, admitted, referred, follow_up, deceased

    # IPD-specific
    bed_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    admission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharge_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharge_summary: Mapped[str | None] = mapped_column(Text)

    # Billing
    billing_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, billed, paid, waived

    # ScribeAI
    scribe_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Clinical trial alert
    trial_participant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient", foreign_keys="[Encounter.patient_id]", lazy="selectin"
    )


class ClinicalNote(AuditMixin, Base):
    """
    Clinical notes attached to an encounter.
    Supports SOAP format, free text, and ScribeAI-generated notes.
    """

    __tablename__ = "clinical_notes"
    __table_args__ = (
        Index("ix_clinical_notes_encounter", "facility_id", "encounter_id"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    note_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # soap, progress, admission, discharge, procedure, consultation, scribe_ai

    # SOAP structure (nullable for non-SOAP notes)
    subjective: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)

    # Free text (for non-SOAP note types)
    content: Mapped[str | None] = mapped_column(Text)

    # ScribeAI
    is_ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_model_version: Mapped[str | None] = mapped_column(String(50))
    clinician_approved: Mapped[bool] = mapped_column(default=False, nullable=False)
    clinician_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    clinician_approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Addendum
    is_addendum: Mapped[bool] = mapped_column(default=False, nullable=False)
    parent_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_notes.id")
    )
