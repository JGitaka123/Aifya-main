import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class StaffProfile(AuditMixin, Base):
    """
    Extended staff profile for HR management.
    Links to Staff model for employment details, qualifications, and emergency contacts.
    """

    __tablename__ = "staff_profiles"
    __table_args__ = (
        Index("ix_staff_profiles_staff", "facility_id", "staff_id", unique=True),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Personal
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(10))  # male, female, other
    national_id: Mapped[str | None] = mapped_column(String(20))
    kra_pin: Mapped[str | None] = mapped_column(String(20))
    nhif_number: Mapped[str | None] = mapped_column(String(20))
    nssf_number: Mapped[str | None] = mapped_column(String(20))

    # Address
    address: Mapped[str | None] = mapped_column(Text)
    county: Mapped[str | None] = mapped_column(String(50))
    sub_county: Mapped[str | None] = mapped_column(String(50))

    # Emergency contact
    emergency_contact_name: Mapped[str | None] = mapped_column(String(200))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))
    emergency_contact_relationship: Mapped[str | None] = mapped_column(String(50))

    # Employment
    employment_type: Mapped[str] = mapped_column(
        String(20), default="permanent", nullable=False
    )  # permanent, contract, casual, intern, locum
    employment_date: Mapped[date | None] = mapped_column(Date)
    contract_end_date: Mapped[date | None] = mapped_column(Date)
    probation_end_date: Mapped[date | None] = mapped_column(Date)

    # Compensation (KES cents)
    basic_salary: Mapped[int | None] = mapped_column(Integer)
    allowances: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # {housing, transport, risk}

    # Qualifications
    qualifications: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{degree, institution, year}]
    certifications: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # [{name, issuer, expiry}]

    # Leave balances (days)
    annual_leave_balance: Mapped[int] = mapped_column(
        Integer, default=21, nullable=False
    )
    sick_leave_balance: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    maternity_leave_balance: Mapped[int] = mapped_column(
        Integer, default=90, nullable=False
    )
    paternity_leave_balance: Mapped[int] = mapped_column(
        Integer, default=14, nullable=False
    )

    # Photo
    photo_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)


class Shift(AuditMixin, Base):
    """
    Shift definition for staff scheduling.
    E.g., Morning (06:00-14:00), Evening (14:00-22:00), Night (22:00-06:00).
    """

    __tablename__ = "shifts"
    __table_args__ = (
        Index("ix_shifts_facility_code", "facility_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # MORNING, EVENING, NIGHT
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)  # 8, 12
    is_night_shift: Mapped[bool] = mapped_column(default=False, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ShiftAssignment(AuditMixin, Base):
    """
    Staff shift assignment for a specific date.
    Links a staff member to a shift on a given day.
    """

    __tablename__ = "shift_assignments"
    __table_args__ = (
        Index("ix_shift_assignments_date", "facility_id", "assignment_date"),
        Index("ix_shift_assignments_staff", "facility_id", "staff_id"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )

    assignment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="assigned", nullable=False
    )  # assigned, confirmed, completed, swapped, cancelled

    # Swap tracking
    swapped_with_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    swap_reason: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)


class LeaveRequest(AuditMixin, Base):
    """
    Staff leave request with approval workflow.
    Types: annual, sick, maternity, paternity, compassionate, study, unpaid.
    """

    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_requests_staff", "facility_id", "staff_id"),
        Index("ix_leave_requests_status", "facility_id", "status"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    leave_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # annual, sick, maternity, paternity, compassionate, study, unpaid
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, approved, rejected, cancelled

    # Approval
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    # Handover
    handover_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    handover_notes: Mapped[str | None] = mapped_column(Text)

    # Supporting docs
    attachment_keys: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # MinIO keys

    notes: Mapped[str | None] = mapped_column(Text)


class Attendance(AuditMixin, Base):
    """
    Staff attendance record for daily clock-in/clock-out tracking.
    """

    __tablename__ = "attendance"
    __table_args__ = (
        Index("ix_attendance_staff_date", "facility_id", "staff_id", "attendance_date"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id")
    )

    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    clock_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(
        String(20), default="present", nullable=False
    )  # present, absent, late, half_day, on_leave, holiday

    # Overtime (minutes)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)
