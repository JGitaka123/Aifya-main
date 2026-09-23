import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Diagnosis(AuditMixin, Base):
    """
    ICD-10 diagnosis linked to an encounter.
    Supports primary/secondary classification and clinical status tracking.
    """

    __tablename__ = "diagnoses"
    __table_args__ = (
        Index("ix_diagnoses_encounter", "facility_id", "encounter_id"),
        Index("ix_diagnoses_patient", "facility_id", "patient_id"),
        Index("ix_diagnoses_icd10", "icd10_code"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    diagnosed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # ICD-10
    icd10_code: Mapped[str] = mapped_column(String(20), nullable=False)
    icd10_description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Classification
    diagnosis_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # primary, secondary, differential, ruled_out
    clinical_status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active, recurrence, relapse, inactive, remission, resolved

    # Dates
    onset_date: Mapped[date | None] = mapped_column(Date)
    resolved_date: Mapped[date | None] = mapped_column(Date)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)

    # Certainty
    certainty: Mapped[str] = mapped_column(
        String(20), default="confirmed", nullable=False
    )  # confirmed, provisional, differential, refuted

    # Chronic flag for patient problem list
    is_chronic: Mapped[bool] = mapped_column(default=False, nullable=False)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
