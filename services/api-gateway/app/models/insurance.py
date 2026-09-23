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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class InsuranceScheme(AuditMixin, Base):
    """Insurance scheme / payer (SHA, private, corporate)."""

    __tablename__ = "insurance_schemes"
    __table_args__ = (
        Index("ix_insurance_schemes_facility", "facility_id"),
        Index("ix_insurance_schemes_facility_type", "facility_id", "scheme_type"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(50), nullable=False)
    scheme_type: Mapped[str] = mapped_column(
        String(30), default="sha", nullable=False
    )  # sha, private, corporate, nhif_legacy
    contact_person: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    contract_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contract_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_details: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # {inpatient, outpatient, dental, optical, maternity, limits}
    rebate_percentage: Mapped[int | None] = mapped_column(Integer)  # 0-100
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class PatientInsurance(AuditMixin, Base):
    """Patient insurance membership."""

    __tablename__ = "patient_insurance"
    __table_args__ = (
        Index("ix_patient_insurance_patient", "facility_id", "patient_id"),
        Index("ix_patient_insurance_facility_status", "facility_id", "is_active"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_schemes.id"), nullable=False
    )
    member_number: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_name: Mapped[str | None] = mapped_column(String(200))
    relationship: Mapped[str | None] = mapped_column(
        String(30)
    )  # self, spouse, child, parent
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class InsuranceClaim(AuditMixin, Base):
    """Insurance claim for reimbursement."""

    __tablename__ = "insurance_claims"
    __table_args__ = (
        Index("ix_insurance_claims_status", "facility_id", "status"),
        Index("ix_insurance_claims_scheme", "facility_id", "scheme_id"),
        Index("ix_insurance_claims_patient", "facility_id", "patient_id"),
    )

    claim_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CLM-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_schemes.id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id")
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    member_number: Mapped[str] = mapped_column(String(50), nullable=False)

    # Amounts in KES cents
    claim_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False
    )  # draft, submitted, processing, approved, partially_approved, rejected, paid
    claim_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Details
    claim_items: Mapped[list[dict] | None] = mapped_column(JSONB)  # [{service, code, amount, approved}]
    diagnosis_codes: Mapped[list[str] | None] = mapped_column(JSONB)  # [ICD-10 codes]
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    sha_reference: Mapped[str | None] = mapped_column(
        String(50)
    )  # SHA system reference
    notes: Mapped[str | None] = mapped_column(Text)

    # ClaimFlow pre-submission validation (SHA rule engine).
    validation_decision: Mapped[str | None] = mapped_column(
        String(20)
    )  # PASSED | WARNING | FAILED | UNAVAILABLE
    validation_result: Mapped[dict | None] = mapped_column(
        JSONB
    )  # {total_rules, findings[], fix_report_markdown, rulepack_version}
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PreAuthorization(AuditMixin, Base):
    """Pre-authorization request for insurance."""

    __tablename__ = "pre_authorizations"
    __table_args__ = (Index("ix_pre_auth_status", "facility_id", "status"),)

    auth_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # PA-YYYYMMDD-XXXX
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_schemes.id"), nullable=False
    )
    member_number: Mapped[str] = mapped_column(String(50), nullable=False)
    service_description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost: Mapped[int] = mapped_column(Integer, nullable=False)  # KES cents
    approved_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    diagnosis: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, approved, declined, expired
    request_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    response_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
