import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class VitalSign(AuditMixin, Base):
    """
    Vital signs observation.
    Critical values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).
    """

    __tablename__ = "vital_signs"
    __table_args__ = (
        Index("ix_vitals_encounter", "facility_id", "encounter_id"),
        Index("ix_vitals_patient", "facility_id", "patient_id"),
        Index("ix_vitals_recorded_at", "facility_id", "recorded_at"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Blood pressure
    systolic_bp: Mapped[int | None] = mapped_column(Integer)  # mmHg
    diastolic_bp: Mapped[int | None] = mapped_column(Integer)  # mmHg

    # Heart rate
    heart_rate: Mapped[int | None] = mapped_column(Integer)  # bpm

    # Temperature
    temperature: Mapped[float | None] = mapped_column(Float)  # Celsius
    temperature_site: Mapped[str | None] = mapped_column(
        String(20)
    )  # oral, axillary, rectal, tympanic, temporal

    # Respiratory
    respiratory_rate: Mapped[int | None] = mapped_column(Integer)  # breaths/min
    oxygen_saturation: Mapped[float | None] = mapped_column(Float)  # SpO2 %
    on_supplemental_o2: Mapped[bool] = mapped_column(default=False, nullable=False)
    o2_flow_rate: Mapped[float | None] = mapped_column(Float)  # L/min

    # Anthropometric
    weight_kg: Mapped[float | None] = mapped_column(Float)  # kg
    height_cm: Mapped[float | None] = mapped_column(Float)  # cm
    bmi: Mapped[float | None] = mapped_column(Float)  # auto-calculated
    head_circumference_cm: Mapped[float | None] = mapped_column(Float)  # pediatric
    muac_cm: Mapped[float | None] = mapped_column(Float)  # Mid-upper arm circumference

    # Pain
    pain_score: Mapped[int | None] = mapped_column(Integer)  # 0-10 NRS

    # Blood glucose
    blood_glucose: Mapped[float | None] = mapped_column(Float)  # mmol/L
    glucose_timing: Mapped[str | None] = mapped_column(
        String(20)
    )  # fasting, random, post_prandial

    # GCS (Glasgow Coma Scale) for emergency
    gcs_eye: Mapped[int | None] = mapped_column(Integer)  # 1-4
    gcs_verbal: Mapped[int | None] = mapped_column(Integer)  # 1-5
    gcs_motor: Mapped[int | None] = mapped_column(Integer)  # 1-6

    # Alert flags (set by service layer based on critical thresholds)
    is_critical: Mapped[bool] = mapped_column(default=False, nullable=False)
    critical_alerts: Mapped[str | None] = mapped_column(
        String(500)
    )  # Comma-separated alert descriptions

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
