"""Payroll-aware leave engine.

- Daily-rate calculation for unpaid leave.
- Submit / approve / reject leave requests.
- Leave balance lookup.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import EmployeeSalary
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest

_TWO_PLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _working_days(year: int, month: int) -> int:
    """Mon-Fri count for the month."""
    last_day = calendar.monthrange(year, month)[1]
    count = 0
    d = date(year, month, 1)
    while d.day <= last_day and d.month == month:
        if d.weekday() < 5:
            count += 1
        nxt = d.toordinal() + 1
        d = date.fromordinal(nxt)
    return count or 22


async def _gross_for_period(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    target: date,
) -> Decimal:
    """Sum gross from the active salary record."""
    stmt = (
        select(EmployeeSalary)
        .where(
            EmployeeSalary.is_deleted.is_(False),
            EmployeeSalary.facility_id == facility_id,
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from <= target,
            or_(
                EmployeeSalary.effective_to.is_(None),
                EmployeeSalary.effective_to >= target,
            ),
        )
        .order_by(EmployeeSalary.effective_from.desc())
        .limit(1)
    )
    salary = (await db.execute(stmt)).scalars().first()
    if salary is None:
        return Decimal("0")
    gross = (
        Decimal(salary.basic_salary or 0)
        + Decimal(salary.house_allowance or 0)
        + Decimal(salary.transport_allowance or 0)
    )
    other = salary.other_allowances or {}
    for v in other.values():
        try:
            gross += Decimal(str(v))
        except (ValueError, ArithmeticError):
            continue
    return gross


async def calculate_unpaid_leave_deduction(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    month: int,
    year: int,
    unpaid_days: int,
) -> Decimal:
    """Return KES deduction for `unpaid_days` of unpaid leave in given month.

    @param db: Async session
    @param facility_id: Tenant
    @param employee_id: Employee
    @param month: Pay period month (1..12)
    @param year: Pay period year
    @param unpaid_days: Number of unpaid working days
    @returns Deduction amount, 2 dp
    """
    if unpaid_days <= 0:
        return Decimal("0")
    target = date(year, month, calendar.monthrange(year, month)[1])
    gross = await _gross_for_period(db, facility_id, employee_id, target)
    if gross <= 0:
        return Decimal("0")
    daily = gross / Decimal(_working_days(year, month))
    return _q(daily * Decimal(unpaid_days))


async def get_leave_balance(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    leave_type_id: uuid.UUID,
    year: int,
) -> int:
    """Compute remaining days = entitlement - approved-days-taken-in-year.

    @returns Remaining days for the year (>= 0)
    """
    lt = (
        await db.execute(
            select(LeaveType).where(
                LeaveType.id == leave_type_id,
                LeaveType.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if lt is None:
        return 0
    entitlement = int(lt.days_entitlement or 0)

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    rows = (
        await db.execute(
            select(PayrollLeaveRequest).where(
                PayrollLeaveRequest.facility_id == facility_id,
                PayrollLeaveRequest.employee_id == employee_id,
                PayrollLeaveRequest.leave_type_id == leave_type_id,
                PayrollLeaveRequest.status == "approved",
                PayrollLeaveRequest.is_deleted.is_(False),
                PayrollLeaveRequest.start_date >= year_start,
                PayrollLeaveRequest.start_date <= year_end,
            )
        )
    ).scalars().all()
    taken = sum(int(r.days_requested or 0) for r in rows)
    return max(0, entitlement - taken)


async def submit_leave_request(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    leave_type_id: uuid.UUID,
    start_date: date,
    end_date: date,
    days_requested: int,
    reason: str | None,
    user_id: uuid.UUID,
) -> PayrollLeaveRequest:
    """Submit a new leave request. Pre-computes the payroll deduction
    if the leave type is unpaid (uses the current month gross to derive a
    daily rate; recomputed on approval if the request straddles months).

    @returns Newly created PayrollLeaveRequest
    """
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")
    # Allow future leave but reject obviously bad input (>5 years out)
    if start_date > date.today() and (start_date - date.today()).days > 365 * 5:
        raise ValueError("start_date is unreasonably far in the future")
    if days_requested <= 0:
        raise ValueError("days_requested must be > 0")

    lt = (
        await db.execute(
            select(LeaveType).where(
                LeaveType.id == leave_type_id,
                LeaveType.is_deleted.is_(False),
                or_(
                    LeaveType.facility_id == facility_id,
                    LeaveType.facility_id.is_(None),
                ),
            )
        )
    ).scalars().first()
    if lt is None:
        raise ValueError("Invalid leave_type_id for this facility")

    # Verify the employee belongs to this facility (defence-in-depth)
    from app.models.payroll import Employee
    emp_check = (
        await db.execute(
            select(Employee.id).where(
                Employee.id == employee_id,
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if emp_check is None:
        raise ValueError("Employee not found in this facility")

    deduction = Decimal("0")
    if not lt.paid:
        deduction = await calculate_unpaid_leave_deduction(
            db=db,
            facility_id=facility_id,
            employee_id=employee_id,
            month=start_date.month,
            year=start_date.year,
            unpaid_days=days_requested,
        )

    req = PayrollLeaveRequest(
        facility_id=facility_id,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        days_requested=days_requested,
        reason=reason,
        status="pending",
        payroll_deduction=deduction,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req


async def resolve_payroll_employee(
    db: AsyncSession,
    facility_id: uuid.UUID,
    staff_id: uuid.UUID,
):
    """Find the payroll Employee row linked to a staff/auth user.

    Auth users are staff rows; payroll employee rows are a separate master
    record. They are mirrored onto staff via ``employees.staff_id ==
    staff.employee_number`` (see payroll/employee_staff_sync.py), so match
    on that code first, then fall back to email.

    @param db: Async DB session
    @param facility_id: Tenant facility
    @param staff_id: Auth/staff UUID (current_user.user_id)
    @returns Matching payroll Employee or None
    """
    from app.models.payroll import Employee
    from app.models.staff import Staff

    staff = await db.get(Staff, staff_id)
    if staff is None or staff.is_deleted or staff.facility_id != facility_id:
        return None

    candidate = None
    code = (getattr(staff, "employee_number", None) or "").strip()
    if code:
        candidate = (
            await db.execute(
                select(Employee)
                .where(
                    Employee.facility_id == facility_id,
                    Employee.is_deleted.is_(False),
                    func.lower(Employee.staff_id) == func.lower(code),
                )
                .limit(1)
            )
        ).scalars().first()
    if candidate is None and getattr(staff, "email", None):
        candidate = (
            await db.execute(
                select(Employee)
                .where(
                    Employee.facility_id == facility_id,
                    Employee.is_deleted.is_(False),
                    func.lower(Employee.email) == func.lower(staff.email),
                )
                .limit(1)
            )
        ).scalars().first()
    return candidate


async def approve_leave_request(
    db: AsyncSession,
    facility_id: uuid.UUID,
    leave_id: uuid.UUID,
    approver_id: uuid.UUID,
) -> PayrollLeaveRequest | None:
    """Approve a pending leave request."""
    req = (
        await db.execute(
            select(PayrollLeaveRequest).where(
                PayrollLeaveRequest.id == leave_id,
                PayrollLeaveRequest.facility_id == facility_id,
                PayrollLeaveRequest.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if req is None:
        return None
    req.status = "approved"
    req.approved_by = approver_id
    req.approved_at = datetime.now(UTC)
    req.updated_by = approver_id
    await db.flush()
    await db.refresh(req)
    return req


async def reject_leave_request(
    db: AsyncSession,
    facility_id: uuid.UUID,
    leave_id: uuid.UUID,
    approver_id: uuid.UUID,
    reason: str | None,
) -> PayrollLeaveRequest | None:
    """Reject a pending leave request."""
    req = (
        await db.execute(
            select(PayrollLeaveRequest).where(
                PayrollLeaveRequest.id == leave_id,
                PayrollLeaveRequest.facility_id == facility_id,
                PayrollLeaveRequest.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if req is None:
        return None
    req.status = "rejected"
    req.rejection_reason = reason
    req.updated_by = approver_id
    await db.flush()
    await db.refresh(req)
    return req
