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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class EmergencyVisit(AuditMixin, Base):
    """
    Emergency department visit with SATS triage.
    Lifecycle: arrived, triaged, treated, then assigned a clinical disposition.
    """

    __tablename__ = "emergency_visits"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "visit_number", name="uq_emergency_visits_visit_number"
        ),
        Index("ix_emergency_visits_date", "facility_id", "arrival_time"),
        Index("ix_emergency_visits_status", "facility_id", "status"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    # Set when the patient arrived on referral from another facility.
    referral_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("referrals.id")
    )
    visit_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ER-YYYYMMDD-XXXX

    # Arrival
    arrival_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    arrival_mode: Mapped[str] = mapped_column(
        String(20), default="walk_in", nullable=False
    )  # walk_in, ambulance, referral, police, other
    brought_by: Mapped[str | None] = mapped_column(String(200))
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)

    # SATS Triage
    triage_category: Mapped[str] = mapped_column(
        String(20), default="standard", nullable=False
    )  # emergency, urgent, standard, non_urgent, dead
    triage_color: Mapped[str] = mapped_column(
        String(10), default="yellow", nullable=False
    )  # red, orange, yellow, green, blue
    triage_score: Mapped[int | None] = mapped_column(Integer)  # TEWS score 0-17
    triage_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triaged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Vitals at triage
    triage_vitals: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # {bp_systolic, bp_diastolic, hr, rr, temp, spo2, gcs, mobility, trauma}

    # Treatment
    assigned_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    treatment_area: Mapped[str | None] = mapped_column(
        String(30)
    )  # resus, acute, sub_acute, fast_track, observation, paediatric
    treatment_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="arrived", nullable=False
    )  # arrived, triaged, in_treatment, observation, or final disposition

    # Disposition
    disposition: Mapped[str | None] = mapped_column(
        String(20)
    )  # discharge, admit, transfer, deceased, left_ama
    disposition_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disposition_notes: Mapped[str | None] = mapped_column(Text)
    admitted_to_ward_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Alerts
    is_trauma: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_resuscitation: Mapped[bool] = mapped_column(default=False, nullable=False)
    allergies_noted: Mapped[str | None] = mapped_column(Text)

    # Procedures/interventions log
    interventions: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{time, procedure, by}]

    notes: Mapped[str | None] = mapped_column(Text)
