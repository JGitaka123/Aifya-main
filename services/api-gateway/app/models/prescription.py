import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Prescription(AuditMixin, Base):
    """
    Medication prescription.
    Drug interaction checks MUST run before save (CLAUDE.md: Clinical Safety).
    KEML (Kenya Essential Medicines List) tagged.
    """

    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescriptions_encounter", "facility_id", "encounter_id"),
        Index("ix_prescriptions_patient", "facility_id", "patient_id"),
        Index("ix_prescriptions_status", "facility_id", "status"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    prescriber_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Drug
    drug_name: Mapped[str] = mapped_column(String(300), nullable=False)
    drug_code: Mapped[str | None] = mapped_column(String(50))  # Formulary code
    generic_name: Mapped[str | None] = mapped_column(String(300))
    is_keml: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )  # Kenya Essential Medicines List
    atc_code: Mapped[str | None] = mapped_column(String(20))  # ATC classification

    # Dosage
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "500mg"
    dosage_value: Mapped[float | None] = mapped_column(Float)
    dosage_unit: Mapped[str | None] = mapped_column(String(20))  # mg, ml, units
    route: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # oral, iv, im, sc, topical, inhaled, rectal, sublingual
    frequency: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # od, bd, tds, qds, prn, stat, nocte
    duration_days: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)

    # Instructions
    instructions: Mapped[str | None] = mapped_column(Text)  # Special instructions

    # Drug interaction check (CRITICAL — must run before save)
    interaction_checked: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    interactions: Mapped[dict | None] = mapped_column(JSONB)
    # [{severity: 'critical'|'major'|'moderate'|'minor', drug, description}]

    # Clinician acknowledgement of non-blocking (WARN) safety alerts.
    acknowledged_alerts: Mapped[list | None] = mapped_column(JSONB)  # [alert_id]
    override_reason: Mapped[str | None] = mapped_column(Text)

    # Dispensing
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, dispensed, partially_dispensed, cancelled, on_hold
    dispensed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispensed_quantity: Mapped[int | None] = mapped_column(Integer)
    substitution_drug: Mapped[str | None] = mapped_column(
        String(300)
    )  # If generic substitution

    # Refill
    refills_allowed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refills_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost (KES cents)
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)
    total_cost_cents: Mapped[int | None] = mapped_column(Integer)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
