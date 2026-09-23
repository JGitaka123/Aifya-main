import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import AuditMixin


class LabOrder(AuditMixin, Base):
    """Lab test order from a clinical encounter."""

    __tablename__ = "lab_orders"
    __table_args__ = (
        Index("ix_lab_orders_encounter", "facility_id", "encounter_id"),
        Index("ix_lab_orders_patient", "facility_id", "patient_id"),
        Index("ix_lab_orders_status", "facility_id", "status"),
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

    # Order
    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20), default="routine", nullable=False
    )  # stat, urgent, routine

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="ordered", nullable=False
    )  # ordered, collected, processing, completed, cancelled

    # Specimen
    specimen_type: Mapped[str | None] = mapped_column(String(50))  # blood, urine, csf, etc.
    specimen_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    specimen_collected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    specimen_id: Mapped[str | None] = mapped_column(String(50))  # Barcode / accession number

    # Clinical info
    clinical_info: Mapped[str | None] = mapped_column(Text)
    fasting: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Cost (KES cents)
    total_cost_cents: Mapped[int | None] = mapped_column(Integer)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    results: Mapped[list["LabResult"]] = relationship("LabResult", foreign_keys="[LabResult.order_id]", lazy="selectin")


class LabResult(AuditMixin, Base):
    """
    Individual lab test result within an order.
    Critical values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).
    """

    __tablename__ = "lab_results"
    __table_args__ = (
        Index("ix_lab_results_order", "facility_id", "order_id"),
        Index("ix_lab_results_test_code", "test_code"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lab_orders.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # Test
    test_code: Mapped[str] = mapped_column(String(50), nullable=False)
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    loinc_code: Mapped[str | None] = mapped_column(String(20))  # LOINC standard code
    panel_name: Mapped[str | None] = mapped_column(String(100))  # CBC, LFT, RFT, etc.

    # Result
    result_value: Mapped[str | None] = mapped_column(String(200))
    result_numeric: Mapped[float | None] = mapped_column(Float)
    result_unit: Mapped[str | None] = mapped_column(String(50))
    reference_range: Mapped[str | None] = mapped_column(String(100))
    interpretation: Mapped[str | None] = mapped_column(
        String(20)
    )  # normal, abnormal, critical, inconclusive

    # Flags
    is_critical: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_abnormal: Mapped[bool] = mapped_column(default=False, nullable=False)
    critical_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    critical_notified_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    critical_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, preliminary, final, corrected, cancelled

    # Timestamps
    resulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str | None] = mapped_column(String(100))  # Testing method

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))


class LabTestCatalog(AuditMixin, Base):
    """
    Managed catalog of orderable lab tests (D6). Provides the authoritative
    test code, name, specimen type, and price so ordering is consistent and
    charges reach the invoice (D2) — mirroring the KEML drug formulary.
    """

    __tablename__ = "lab_test_catalog"
    __table_args__ = (
        Index("ix_lab_catalog_facility_code", "facility_id", "test_code"),
        Index("ix_lab_catalog_facility_active", "facility_id", "is_active"),
    )

    test_code: Mapped[str] = mapped_column(String(50), nullable=False)
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    specimen_type: Mapped[str | None] = mapped_column(String(50))
    loinc_code: Mapped[str | None] = mapped_column(String(20))
    panel_name: Mapped[str | None] = mapped_column(String(100))
    # Managed price in KES cents. Not clinician-editable (D6).
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference_range: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
