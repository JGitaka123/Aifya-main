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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Ward(AuditMixin, Base):
    """
    Hospital ward / unit (e.g., Male Medical, Female Surgical, ICU, HDU, Maternity).
    Wards contain beds and are used for bed allocation during admission.
    """

    __tablename__ = "wards"
    __table_args__ = (
        Index("ix_wards_facility_name", "facility_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    ward_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # general, icu, hdu, maternity, paediatric, nicu, psychiatric, isolation, surgical, burns
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    floor: Mapped[str | None] = mapped_column(String(20))
    total_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gender_restriction: Mapped[str | None] = mapped_column(
        String(10)
    )  # male, female, any
    charge_per_day_cents: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Bed(AuditMixin, Base):
    """
    Individual bed within a ward. Tracks occupancy status.
    """

    __tablename__ = "beds"
    __table_args__ = (
        Index("ix_beds_ward", "facility_id", "ward_id"),
        Index("ix_beds_facility_number", "facility_id", "ward_id", "bed_number", unique=True),
        Index("ix_beds_status", "facility_id", "status"),
    )

    ward_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wards.id"), nullable=False
    )
    bed_number: Mapped[str] = mapped_column(String(20), nullable=False)
    bed_type: Mapped[str] = mapped_column(
        String(20), default="standard", nullable=False
    )  # standard, icu, hdu, cot, incubator, isolation
    status: Mapped[str] = mapped_column(
        String(20), default="available", nullable=False
    )  # available, occupied, reserved, maintenance, cleaning
    current_patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    current_admission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)


class Admission(AuditMixin, Base):
    """
    Inpatient admission record linking encounter to bed assignment.
    Tracks the full admission lifecycle from admit to discharge.
    """

    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint("facility_id", "admission_number", name="uq_admissions_admission_number"),
        Index("ix_admissions_facility_patient", "facility_id", "patient_id"),
        Index("ix_admissions_facility_status", "facility_id", "status"),
        Index("ix_admissions_encounter", "encounter_id"),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    ward_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wards.id"), nullable=False
    )
    bed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("beds.id"), nullable=False
    )
    admission_number: Mapped[str] = mapped_column(String(30), nullable=False)
    attending_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    primary_nurse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # Status lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="admitted", nullable=False
    )  # admitted, on_leave, transferred, discharged, deceased

    # Admission details
    admission_reason: Mapped[str | None] = mapped_column(Text)
    admission_diagnosis: Mapped[str | None] = mapped_column(String(500))
    admitted_from: Mapped[str | None] = mapped_column(
        String(30)
    )  # opd, emergency, referral, direct
    accommodation_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # general, semi_private, private, icu, hdu

    # Timestamps
    admitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Discharge
    discharge_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # improved, recovered, dama, absconded, deceased, transferred, referred
    discharge_diagnosis: Mapped[str | None] = mapped_column(String(500))
    discharge_summary: Mapped[str | None] = mapped_column(Text)
    follow_up_plan: Mapped[str | None] = mapped_column(Text)
    discharge_medications: Mapped[str | None] = mapped_column(Text)

    # Length of stay (computed on discharge)
    length_of_stay_days: Mapped[int | None] = mapped_column(Integer)


class AdmissionOrder(AuditMixin, Base):
    """
    A clinician's request to admit a patient, raised during consultation.

    Kept deliberately separate from :class:`Admission`. Raising an order is a
    clinical decision, not a bed allocation: no inpatient exists until the
    IPD/admission desk works the order and a ward plus bed are assigned. That
    separation is what lets "the doctor asked" and "the patient is an
    inpatient" be audited, reversed and reported on independently.
    """

    __tablename__ = "admission_orders"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "order_number", name="uq_admission_orders_order_number"
        ),
        Index("ix_admission_orders_facility_status", "facility_id", "status"),
        Index("ix_admission_orders_facility_patient", "facility_id", "patient_id"),
        Index("ix_admission_orders_encounter", "encounter_id"),
    )

    order_number: Mapped[str] = mapped_column(String(30), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    # Actor ids come from the access token, so they carry no FK — the same
    # rationale as Admission.discharged_by.
    ordered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    attending_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # What the clinician is asking for.
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    primary_diagnosis: Mapped[str | None] = mapped_column(String(500))
    admission_type: Mapped[str] = mapped_column(
        String(20), default="elective", nullable=False
    )  # emergency, urgent, elective
    priority: Mapped[str] = mapped_column(
        String(20), default="routine", nullable=False
    )  # routine, urgent, emergency
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    requested_ward_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wards.id")
    )
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # pending -> accepted | bed_pending -> admitted; or declined / cancelled.
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    # IPD / admission-desk decision.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)

    # Populated only once the order becomes a real admission (or one is linked
    # to it), so the queue can always answer "what happened to this request?".
    admission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admissions.id")
    )


class NursingNote(AuditMixin, Base):
    """
    Nursing observation / care note linked to an admission.
    Includes vitals monitoring, care actions, and shift handover notes.
    """

    __tablename__ = "nursing_notes"
    __table_args__ = (
        Index("ix_nursing_notes_admission", "facility_id", "admission_id"),
    )

    admission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admissions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    note_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # observation, medication, procedure, shift_handover, intake_output, pain_assessment, wound_care
    content: Mapped[str] = mapped_column(Text, nullable=False)
    shift: Mapped[str | None] = mapped_column(
        String(10)
    )  # morning, afternoon, night
    severity: Mapped[str | None] = mapped_column(
        String(10)
    )  # normal, warning, critical
