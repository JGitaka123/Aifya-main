"""SQLAlchemy models for the HR/Payroll module.

Core payroll-grade tables. Companion file `payroll_extra.py` contains
the supporting tables (leave, deductions, disciplinary, training,
performance, exit).
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
from app.utils.encryption import EncryptedString


class Employee(AuditMixin, Base):
    """Payroll-grade employee master record (multi-tenant)."""

    __tablename__ = "employees"

    staff_id: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # National ID and KRA PIN are sensitive PII — encrypted at rest.
    id_number: Mapped[str | None] = mapped_column(EncryptedString(20))
    kra_pin: Mapped[str | None] = mapped_column(EncryptedString(20))
    nssf_number: Mapped[str | None] = mapped_column(String(20))
    shif_number: Mapped[str | None] = mapped_column(String(20))
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    job_title: Mapped[str | None] = mapped_column(String(200))
    employment_type: Mapped[str] = mapped_column(
        String(20), default="permanent", nullable=False
    )  # permanent|contract|casual|intern
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_branch: Mapped[str | None] = mapped_column(String(100))
    # Encrypted at rest (Fernet, app-level) — see app/utils/encryption.py.
    # Never exposed in API responses; the payslip masks all but the last 4.
    bank_account: Mapped[str | None] = mapped_column(EncryptedString(34))
    disability_exemption: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class EmployeeSalary(AuditMixin, Base):
    """Salary structure history with effective dating."""

    __tablename__ = "employee_salaries"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    house_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    transport_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    other_allowances: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollRun(AuditMixin, Base):
    """A monthly payroll calculation run."""

    __tablename__ = "payroll_runs"

    period_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft|approved|posted|locked
    run_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gl_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    total_gross: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_paye: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_nssf: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_shif: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_hl: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_net: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_employer_nssf: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    total_employer_hl: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollLineItem(AuditMixin, Base):
    """Per-employee pay slip line in a payroll run."""

    __tablename__ = "payroll_line_items"

    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_runs.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    basic_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    house_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    transport_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    other_allowances: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    gross_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    nssf_employee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    shif: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    housing_levy: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    taxable_pay: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    paye_gross: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    personal_relief: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    insurance_relief: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    paye: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    other_deductions: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    total_deductions: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    net_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    employer_nssf: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    employer_housing_levy: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)


class StatutoryRate(AuditMixin, Base):
    """Statutory rate (PAYE relief, SHIF rate, HL rate, insurance relief).

    facility_id NULL means a global default applied to all facilities.
    """

    __tablename__ = "statutory_rates"

    facility_id: Mapped[uuid.UUID | None] = mapped_column(  # type: ignore[assignment]
        UUID(as_uuid=True), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # paye|nssf|shif|housing_levy|relief
    rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fixed_cap: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PAYEBand(AuditMixin, Base):
    """Progressive PAYE band (Kenya KRA).

    facility_id NULL means a global default.
    """

    __tablename__ = "paye_bands"

    facility_id: Mapped[uuid.UUID | None] = mapped_column(  # type: ignore[assignment]
        UUID(as_uuid=True), index=True, nullable=True
    )
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    upper_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)


class NSSFTier(AuditMixin, Base):
    """NSSF contribution tier (I or II)."""

    __tablename__ = "nssf_tiers"

    facility_id: Mapped[uuid.UUID | None] = mapped_column(  # type: ignore[assignment]
        UUID(as_uuid=True), index=True, nullable=True
    )
    tier: Mapped[str] = mapped_column(String(5), nullable=False)  # I or II
    lower_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    upper_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    employee_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    employer_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
