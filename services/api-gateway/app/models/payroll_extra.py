"""Supporting HR/Payroll models: leave, deductions, disciplinary,
training, performance, exit. Companion to `payroll.py`.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class LeaveType(AuditMixin, Base):
    """Leave type definition. facility_id NULL = global default."""

    __tablename__ = "leave_types"

    facility_id: Mapped[uuid.UUID | None] = mapped_column(  # type: ignore[assignment]
        UUID(as_uuid=True), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    days_entitlement: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    partial_pay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    carries_over: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_carryover: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollLeaveRequest(AuditMixin, Base):
    """Payroll-aware leave request (separate from generic hr.leave_requests)."""

    __tablename__ = "payroll_leave_requests"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending|approved|rejected|cancelled
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    payroll_deduction: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    payroll_period_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class EmployeeDeduction(AuditMixin, Base):
    """Recurring employee-level deduction (loan, sacco, advance, etc.)."""

    __tablename__ = "employee_deductions"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )  # monthly|one_time
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class DisciplinaryCase(AuditMixin, Base):
    """Disciplinary case file."""

    __tablename__ = "disciplinary_cases"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    allegation: Mapped[str] = mapped_column(Text, nullable=False)
    investigation_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending|hearing|resolved|appealed
    outcome: Mapped[str | None] = mapped_column(
        String(30)
    )  # warning|final_warning|suspension|dismissal
    hearing_date: Mapped[date | None] = mapped_column(Date)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class GrievanceCase(AuditMixin, Base):
    """Employee grievance / complaint."""

    __tablename__ = "grievance_cases"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )  # open|investigating|resolved
    resolution: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrainingProgram(AuditMixin, Base):
    """Training/CPD program."""

    __tablename__ = "training_programs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    cpd_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class TrainingAttendance(AuditMixin, Base):
    """Per-employee training attendance + completion certificate."""

    __tablename__ = "training_attendance"

    training_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_programs.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="nominated", nullable=False
    )  # nominated|attended|completed|failed
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    certificate_url: Mapped[str | None] = mapped_column(String(500))
    completion_date: Mapped[date | None] = mapped_column(Date)


class PerformanceReview(AuditMixin, Base):
    """Periodic performance review."""

    __tablename__ = "performance_reviews"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    period_label: Mapped[str] = mapped_column(String(50), nullable=False)
    self_assessment: Mapped[dict | None] = mapped_column(JSONB)
    manager_review: Mapped[dict | None] = mapped_column(JSONB)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    calibrated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft|self_done|manager_done|calibrated|approved


class ExitChecklist(AuditMixin, Base):
    """Employee exit checklist + final pay calculation."""

    __tablename__ = "exit_checklists"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    last_day: Mapped[date] = mapped_column(Date, nullable=False)
    notice_pay: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    gratuity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    leave_encashment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    final_pay: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    checklist_status: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    processed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", nullable=False
    )  # in_progress|complete
