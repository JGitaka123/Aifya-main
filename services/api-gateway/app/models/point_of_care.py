import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class PointOfCareTest(AuditMixin, Base):
    """
    A test performed and resulted in the consultation room.

    HIV, malaria RDT, urinalysis and pregnancy tests are done at the bedside,
    not in the laboratory, so they must not be pushed onto the lab worklist.
    Recording them here keeps the general screening an OPD clinician performs
    on the encounter itself, visible the moment it is done.
    """

    __tablename__ = "point_of_care_tests"
    __table_args__ = (
        Index("ix_poc_tests_encounter", "facility_id", "encounter_id"),
        Index("ix_poc_tests_patient", "facility_id", "patient_id"),
        Index("ix_poc_tests_code", "facility_id", "test_code"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Test
    test_code: Mapped[str] = mapped_column(String(50), nullable=False)
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(30), default="screening", nullable=False
    )  # screening, rapid_diagnostic, urinalysis, other
    specimen_type: Mapped[str | None] = mapped_column(String(50))

    # Result
    result_value: Mapped[str | None] = mapped_column(String(200))
    result_numeric: Mapped[float | None] = mapped_column(Float)
    result_unit: Mapped[str | None] = mapped_column(String(50))
    interpretation: Mapped[str | None] = mapped_column(
        String(20)
    )  # normal, abnormal, positive, negative, reactive, non_reactive, inconclusive
    is_abnormal: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
