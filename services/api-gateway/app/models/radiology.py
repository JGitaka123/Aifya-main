import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class ImagingOrder(AuditMixin, Base):
    """
    Imaging / radiology order from a clinical encounter.
    Follows same lifecycle pattern as LabOrder: ordered → scheduled → in_progress → completed.
    """

    __tablename__ = "imaging_orders"
    __table_args__ = (
        Index("ix_imaging_orders_encounter", "facility_id", "encounter_id"),
        Index("ix_imaging_orders_patient", "facility_id", "patient_id"),
        Index("ix_imaging_orders_status", "facility_id", "status"),
        Index("ix_imaging_orders_modality", "facility_id", "modality"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    ordered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Order identifiers
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    accession_number: Mapped[str | None] = mapped_column(String(50))

    # Imaging details
    modality: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # xray, ultrasound, ct, mri, fluoroscopy, mammography, ecg, echo
    body_part: Mapped[str] = mapped_column(String(100), nullable=False)  # chest, abdomen, skull, etc.
    laterality: Mapped[str | None] = mapped_column(
        String(20)
    )  # left, right, bilateral, na
    views_requested: Mapped[str | None] = mapped_column(String(200))  # AP, PA, lateral, etc.
    study_description: Mapped[str] = mapped_column(String(300), nullable=False)

    # Clinical context
    priority: Mapped[str] = mapped_column(
        String(20), default="routine", nullable=False
    )  # stat, urgent, routine
    clinical_indication: Mapped[str | None] = mapped_column(Text)
    clinical_history: Mapped[str | None] = mapped_column(Text)
    contrast_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    contrast_type: Mapped[str | None] = mapped_column(String(100))
    pregnancy_status: Mapped[str | None] = mapped_column(
        String(20)
    )  # not_pregnant, pregnant, unknown, na
    allergies_noted: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="ordered", nullable=False
    )  # ordered, scheduled, in_progress, completed, cancelled

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    room: Mapped[str | None] = mapped_column(String(50))

    # Performing tech
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Cost (KES cents)
    total_cost_cents: Mapped[int | None] = mapped_column(Integer)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))


class ImagingResult(AuditMixin, Base):
    """
    Radiologist report / result for an imaging order.
    Reports go through: draft → preliminary → final lifecycle.
    """

    __tablename__ = "imaging_results"
    __table_args__ = (
        Index("ix_imaging_results_order", "facility_id", "order_id"),
        Index("ix_imaging_results_status", "facility_id", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("imaging_orders.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )

    # Reporting radiologist
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # Report
    findings: Mapped[str | None] = mapped_column(Text)
    impression: Mapped[str | None] = mapped_column(Text)  # Summary / conclusion
    recommendations: Mapped[str | None] = mapped_column(Text)
    technique: Mapped[str | None] = mapped_column(Text)  # How the study was performed
    comparison: Mapped[str | None] = mapped_column(Text)  # Prior studies compared

    # Classification
    urgency: Mapped[str] = mapped_column(
        String(20), default="normal", nullable=False
    )  # normal, abnormal, critical, incidental
    is_critical: Mapped[bool] = mapped_column(default=False, nullable=False)
    critical_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    critical_notified_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    critical_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, preliminary, final, addendum

    # Timestamps
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Image references (PACS / MinIO keys)
    image_keys: Mapped[dict | None] = mapped_column(JSONB)
    # e.g. [{"key": "minio/radiology/...", "description": "PA chest", "modality": "CR"}]

    # DICOM metadata
    dicom_study_uid: Mapped[str | None] = mapped_column(String(200))
    dicom_series_count: Mapped[int | None] = mapped_column(Integer)
    dicom_instance_count: Mapped[int | None] = mapped_column(Integer)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
