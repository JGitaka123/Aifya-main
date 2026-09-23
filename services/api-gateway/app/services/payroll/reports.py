"""On-demand payroll reports.

All queries scoped by facility_id (multi-tenant). Results are computed
from the materialised line items rather than re-running the engine.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import (
    Employee,
    PayrollLineItem,
    PayrollRun,
)
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest
from app.models.staff import Department

_ZERO = Decimal("0")

# A payroll run only feeds statutory returns once it has been approved.
_REPORTABLE_STATUSES = ("approved", "posted", "locked")


# ── Monthly summary ────────────────────────────────────────────────────────


async def get_monthly_payroll_summary(
    db: AsyncSession,
    facility_id: uuid.UUID,
    month: int,
    year: int,
) -> dict[str, Any]:
    """Return totals per department for the given period.

    @returns dict with `month`, `year`, `departments` (list), grand totals.
    """
    run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.month == month,
                PayrollRun.year == year,
            ).order_by(PayrollRun.created_at.desc()).limit(1)
        )
    ).scalars().first()
    if run is None:
        return {
            "month": month,
            "year": year,
            "departments": [],
            "grand_total_gross": _ZERO,
            "grand_total_net": _ZERO,
            "grand_total_paye": _ZERO,
            "grand_total_nssf": _ZERO,
            "grand_total_shif": _ZERO,
            "grand_total_hl": _ZERO,
            "headcount": 0,
        }

    rows = (
        await db.execute(
            select(
                Employee.department_id,
                Department.name.label("department_name"),
                func.count(PayrollLineItem.id).label("headcount"),
                func.coalesce(func.sum(PayrollLineItem.gross_salary), 0).label("gross"),
                func.coalesce(func.sum(PayrollLineItem.net_salary), 0).label("net"),
                func.coalesce(func.sum(PayrollLineItem.paye), 0).label("paye"),
            )
            .join(Employee, Employee.id == PayrollLineItem.employee_id)
            .outerjoin(
                Department,
                and_(
                    Department.id == Employee.department_id,
                    Department.is_deleted.is_(False),
                ),
            )
            .where(
                PayrollLineItem.payroll_run_id == run.id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
            .group_by(Employee.department_id, Department.name)
        )
    ).all()

    departments: list[dict[str, Any]] = []
    for dept_id, dept_name, headcount, gross, net, paye in rows:
        departments.append(
            {
                "department_id": dept_id,
                "department_name": dept_name or "Unassigned",
                "headcount": int(headcount or 0),
                "total_gross": Decimal(gross or 0),
                "total_net": Decimal(net or 0),
                "total_paye": Decimal(paye or 0),
            }
        )

    return {
        "month": month,
        "year": year,
        "departments": departments,
        "grand_total_gross": Decimal(run.total_gross or 0),
        "grand_total_net": Decimal(run.total_net or 0),
        "grand_total_paye": Decimal(run.total_paye or 0),
        "grand_total_nssf": Decimal(run.total_nssf or 0),
        "grand_total_shif": Decimal(run.total_shif or 0),
        "grand_total_hl": Decimal(run.total_hl or 0),
        "headcount": sum(int(d["headcount"]) for d in departments),
    }


# ── Statutory schedules (P10 / NSSF / SHIF) ────────────────────────────────


async def _resolve_run(
    db: AsyncSession, facility_id: uuid.UUID, month: int, year: int
) -> PayrollRun | None:
    """Latest payroll run for the period, or None when the period has none."""
    return (
        await db.execute(
            select(PayrollRun)
            .where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.month == month,
                PayrollRun.year == year,
            )
            .order_by(PayrollRun.created_at.desc())
            .limit(1)
        )
    ).scalars().first()


async def _period_lines(
    db: AsyncSession,
    facility_id: uuid.UUID,
    run: PayrollRun,
    columns: list[Any],
) -> list[Any]:
    """Employee rows for one payroll run, ordered by employee name."""
    return (
        await db.execute(
            select(*columns)
            .join(Employee, Employee.id == PayrollLineItem.employee_id)
            .where(
                PayrollLineItem.payroll_run_id == run.id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
            .order_by(Employee.full_name.asc())
        )
    ).all()


def _is_reportable(run: PayrollRun | None) -> bool:
    """Only an approved run may feed a statutory return."""
    return run is not None and run.status in _REPORTABLE_STATUSES


async def get_paye_schedule(
    db: AsyncSession, facility_id: uuid.UUID, month: int, year: int
) -> dict[str, Any]:
    """KRA P10 PAYE schedule per employee.

    An unapproved draft is not a returnable period, so it yields an empty
    schedule rather than a wrong one.
    """
    run = await _resolve_run(db, facility_id, month, year)
    rows: list[dict[str, Any]] = []
    if _is_reportable(run) and run is not None:
        lines = await _period_lines(
            db,
            facility_id,
            run,
            [
                Employee.id,
                Employee.full_name,
                Employee.kra_pin,
                PayrollLineItem.taxable_pay,
                PayrollLineItem.paye,
            ],
        )
        rows = [
            {
                "employee_id": employee_id,
                "employee_name": name,
                "kra_pin": kra_pin,
                "taxable_pay": Decimal(taxable or 0),
                "paye": Decimal(paye or 0),
            }
            for (employee_id, name, kra_pin, taxable, paye) in lines
        ]
    return {
        "month": month,
        "year": year,
        "rows": rows,
        "total_taxable": sum((r["taxable_pay"] for r in rows), _ZERO),
        "total_paye": sum((r["paye"] for r in rows), _ZERO),
    }


async def get_nssf_schedule(
    db: AsyncSession, facility_id: uuid.UUID, month: int, year: int
) -> dict[str, Any]:
    """NSSF schedule per employee, employee and employer contributions."""
    run = await _resolve_run(db, facility_id, month, year)
    rows: list[dict[str, Any]] = []
    if _is_reportable(run) and run is not None:
        lines = await _period_lines(
            db,
            facility_id,
            run,
            [
                Employee.id,
                Employee.full_name,
                Employee.nssf_number,
                PayrollLineItem.gross_salary,
                PayrollLineItem.nssf_employee,
                PayrollLineItem.employer_nssf,
            ],
        )
        rows = [
            {
                "employee_id": employee_id,
                "employee_name": name,
                "nssf_number": nssf_number,
                "pensionable_pay": Decimal(pensionable or 0),
                "employee_contribution": Decimal(employee_share or 0),
                "employer_contribution": Decimal(employer_share or 0),
                "total": Decimal(employee_share or 0) + Decimal(employer_share or 0),
            }
            for (
                employee_id,
                name,
                nssf_number,
                pensionable,
                employee_share,
                employer_share,
            ) in lines
        ]
    return {
        "month": month,
        "year": year,
        "rows": rows,
        "total_employee": sum((r["employee_contribution"] for r in rows), _ZERO),
        "total_employer": sum((r["employer_contribution"] for r in rows), _ZERO),
        "total": sum((r["total"] for r in rows), _ZERO),
    }


async def get_shif_schedule(
    db: AsyncSession, facility_id: uuid.UUID, month: int, year: int
) -> dict[str, Any]:
    """SHIF schedule per employee."""
    run = await _resolve_run(db, facility_id, month, year)
    rows: list[dict[str, Any]] = []
    if _is_reportable(run) and run is not None:
        lines = await _period_lines(
            db,
            facility_id,
            run,
            [
                Employee.id,
                Employee.full_name,
                Employee.shif_number,
                PayrollLineItem.gross_salary,
                PayrollLineItem.shif,
            ],
        )
        rows = [
            {
                "employee_id": employee_id,
                "employee_name": name,
                "shif_number": shif_number,
                "gross_salary": Decimal(gross or 0),
                "contribution": Decimal(contribution or 0),
            }
            for (employee_id, name, shif_number, gross, contribution) in lines
        ]
    return {
        "month": month,
        "year": year,
        "rows": rows,
        "total": sum((r["contribution"] for r in rows), _ZERO),
    }


# ── P9 annual return ───────────────────────────────────────────────────────

async def generate_p9(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    year: int,
) -> dict[str, Any]:
    """Generate the annual P9 (PAYE return) for one employee.

    Columns follow the KRA P9 form. The caller can rely on
    `totals.paye_payable` being the sum of the monthly PAYE figures.
    """
    emp = (
        await db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if emp is None:
        raise ValueError("Employee not found")

    rows = (
        await db.execute(
            select(
                PayrollRun.month,
                PayrollLineItem.basic_salary,
                PayrollLineItem.house_allowance,
                PayrollLineItem.transport_allowance,
                PayrollLineItem.other_allowances,
                PayrollLineItem.gross_salary,
                PayrollLineItem.nssf_employee,
                PayrollLineItem.shif,
                PayrollLineItem.housing_levy,
                PayrollLineItem.taxable_pay,
                PayrollLineItem.paye_gross,
                PayrollLineItem.personal_relief,
                PayrollLineItem.insurance_relief,
                PayrollLineItem.paye,
            )
            .join(PayrollRun, PayrollRun.id == PayrollLineItem.payroll_run_id)
            .where(
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.employee_id == employee_id,
                PayrollLineItem.is_deleted.is_(False),
                PayrollRun.year == year,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.status.in_(_REPORTABLE_STATUSES),
            )
            .order_by(PayrollRun.month.asc())
        )
    ).all()

    p9_rows: list[dict[str, Any]] = []
    totals: dict[str, Decimal] = {
        "basic_salary": _ZERO,
        "benefits": _ZERO,
        "gross_pay": _ZERO,
        "defined_contribution_retirement": _ZERO,
        "affordable_housing_levy": _ZERO,
        "shif_contribution": _ZERO,
        "taxable_pay": _ZERO,
        "paye": _ZERO,
        "personal_relief": _ZERO,
        "insurance_relief": _ZERO,
        "paye_payable": _ZERO,
    }
    for (
        month,
        basic,
        house,
        transport,
        other,
        gross,
        nssf,
        shif,
        housing_levy,
        taxable,
        paye_gross,
        personal_relief,
        insurance_relief,
        paye,
    ) in rows:
        other_total = _ZERO
        if isinstance(other, dict):
            for value in other.values():
                try:
                    other_total += Decimal(str(value))
                except (ArithmeticError, TypeError, ValueError):
                    continue
        row = {
            "month": int(month),
            "basic_salary": Decimal(basic or 0),
            "benefits": Decimal(house or 0) + Decimal(transport or 0) + other_total,
            "gross_pay": Decimal(gross or 0),
            "defined_contribution_retirement": Decimal(nssf or 0),
            "affordable_housing_levy": Decimal(housing_levy or 0),
            "shif_contribution": Decimal(shif or 0),
            "taxable_pay": Decimal(taxable or 0),
            "paye": Decimal(paye_gross or 0),
            "personal_relief": Decimal(personal_relief or 0),
            "insurance_relief": Decimal(insurance_relief or 0),
            "paye_payable": Decimal(paye or 0),
        }
        p9_rows.append(row)
        for key in totals:
            totals[key] += row[key]

    return {
        "employee_id": employee_id,
        "employee_name": emp.full_name,
        "kra_pin": emp.kra_pin,
        "year": year,
        "rows": p9_rows,
        "totals": {"month": 0, **totals},
    }


# ── Headcount ──────────────────────────────────────────────────────────────

async def get_headcount_report(
    db: AsyncSession,
    facility_id: uuid.UUID,
    as_of: date,
) -> dict[str, Any]:
    """Headcount as of a date, by department and by employment type.

    Employees with no department are reported under "Unassigned" so the
    department breakdown always reconciles to the total.
    """
    active = (
        Employee.facility_id == facility_id,
        Employee.is_deleted.is_(False),
        Employee.is_active.is_(True),
        Employee.hire_date <= as_of,
    )

    department_label = func.coalesce(Department.name, literal("Unassigned"))
    department_rows = (
        await db.execute(
            select(
                department_label.label("label"),
                func.count(Employee.id).label("count"),
            )
            .select_from(Employee)
            .outerjoin(
                Department,
                and_(
                    Department.id == Employee.department_id,
                    Department.is_deleted.is_(False),
                ),
            )
            .where(*active)
            .group_by(department_label)
            .order_by(func.count(Employee.id).desc())
        )
    ).all()

    type_rows = (
        await db.execute(
            select(Employee.employment_type, func.count(Employee.id))
            .where(*active)
            .group_by(Employee.employment_type)
            .order_by(func.count(Employee.id).desc())
        )
    ).all()

    by_department = [
        {"label": label, "count": int(count)} for (label, count) in department_rows
    ]
    by_employment_type = [
        {"label": employment_type or "unspecified", "count": int(count)}
        for (employment_type, count) in type_rows
    ]
    return {
        "as_of": as_of,
        "total": sum(bucket["count"] for bucket in by_department),
        "by_department": by_department,
        "by_employment_type": by_employment_type,
    }

async def get_leave_utilisation(
    db: AsyncSession,
    facility_id: uuid.UUID,
    year: int,
) -> dict[str, Any]:
    """Per-employee leave utilisation for the year.

    Reports entitlement, approved days taken and remaining balance for each
    active employee and each leave type they are entitled to (or have used).
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    employees = (
        await db.execute(
            select(Employee)
            .where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.is_active.is_(True),
            )
            .order_by(Employee.full_name.asc())
        )
    ).scalars().all()
    leave_types = (
        await db.execute(
            select(LeaveType)
            .where(
                LeaveType.is_deleted.is_(False),
                or_(
                    LeaveType.facility_id == facility_id,
                    LeaveType.facility_id.is_(None),
                ),
            )
            .order_by(LeaveType.name.asc())
        )
    ).scalars().all()
    used_rows = (
        await db.execute(
            select(
                PayrollLeaveRequest.employee_id,
                PayrollLeaveRequest.leave_type_id,
                func.coalesce(func.sum(PayrollLeaveRequest.days_requested), 0),
            )
            .where(
                PayrollLeaveRequest.facility_id == facility_id,
                PayrollLeaveRequest.is_deleted.is_(False),
                PayrollLeaveRequest.status == "approved",
                PayrollLeaveRequest.start_date >= year_start,
                PayrollLeaveRequest.start_date <= year_end,
            )
            .group_by(
                PayrollLeaveRequest.employee_id,
                PayrollLeaveRequest.leave_type_id,
            )
        )
    ).all()
    used_by_key = {
        (employee_id, leave_type_id): int(days or 0)
        for (employee_id, leave_type_id, days) in used_rows
    }
    rows: list[dict[str, Any]] = []
    for emp in employees:
        for lt in leave_types:
            used_days = used_by_key.get((emp.id, lt.id), 0)
            entitlement = int(lt.days_entitlement or 0)
            if entitlement <= 0 and used_days <= 0:
                continue
            rows.append(
                {
                    "employee_id": str(emp.id),
                    "employee_name": emp.full_name,
                    "leave_type": lt.name,
                    "entitlement": entitlement,
                    "used": used_days,
                    "remaining": max(0, entitlement - used_days),
                }
            )
    return {
        "year": year,
        "total": len(rows),
        "rows": rows,
    }


_MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _next_month(value: date) -> date:
    """First day of the month after the one containing `value`."""
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


async def get_payroll_cost_trend(
    db: AsyncSession,
    facility_id: uuid.UUID,
    year: int,
) -> dict[str, Any]:
    """Per-month gross, net, PAYE and statutory deductions for a year.

    `statutory` is the employee-side total of NSSF + SHIF + Housing Levy.
    """
    rows = (
        await db.execute(
            select(
                PayrollRun.month,
                func.coalesce(func.sum(PayrollRun.total_gross), 0),
                func.coalesce(func.sum(PayrollRun.total_net), 0),
                func.coalesce(func.sum(PayrollRun.total_paye), 0),
                func.coalesce(func.sum(PayrollRun.total_nssf), 0),
                func.coalesce(func.sum(PayrollRun.total_shif), 0),
                func.coalesce(func.sum(PayrollRun.total_hl), 0),
            )
            .where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.year == year,
                PayrollRun.status.in_(_REPORTABLE_STATUSES),
            )
            .group_by(PayrollRun.month)
            .order_by(PayrollRun.month.asc())
        )
    ).all()
    points = [
        {
            "month": int(month),
            "year": year,
            "label": _MONTH_LABELS[int(month) - 1],
            "gross": Decimal(gross or 0),
            "net": Decimal(net or 0),
            "paye": Decimal(paye or 0),
            "statutory": Decimal(nssf or 0)
            + Decimal(shif or 0)
            + Decimal(housing_levy or 0),
        }
        for (month, gross, net, paye, nssf, shif, housing_levy) in rows
    ]
    return {"year": year, "points": points}


async def get_employee_turnover(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Hires, terminations and ending headcount for a period.

    Also returns one joiner/leaver point per calendar month in the period, so
    the trend line is continuous instead of only showing months with activity.
    """
    hire_rows = (
        await db.execute(
            select(
                func.date_trunc("month", Employee.hire_date).label("bucket"),
                func.count(Employee.id),
            )
            .where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.hire_date >= period_start,
                Employee.hire_date <= period_end,
            )
            .group_by("bucket")
        )
    ).all()
    leaver_rows = (
        await db.execute(
            select(
                func.date_trunc("month", Employee.termination_date).label("bucket"),
                func.count(Employee.id),
            )
            .where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.termination_date.isnot(None),
                Employee.termination_date >= period_start,
                Employee.termination_date <= period_end,
            )
            .group_by("bucket")
        )
    ).all()

    hires_by_month = {(b.year, b.month): int(c) for (b, c) in hire_rows if b}
    leavers_by_month = {(b.year, b.month): int(c) for (b, c) in leaver_rows if b}

    points: list[dict[str, Any]] = []
    cursor = date(period_start.year, period_start.month, 1)
    while cursor <= period_end:
        key = (cursor.year, cursor.month)
        points.append(
            {
                "period": f"{_MONTH_LABELS[cursor.month - 1]} {cursor.year}",
                "joiners": hires_by_month.get(key, 0),
                "leavers": leavers_by_month.get(key, 0),
            }
        )
        cursor = _next_month(cursor)

    ending = (
        await db.execute(
            select(func.count(Employee.id)).where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.is_active.is_(True),
                Employee.hire_date <= period_end,
                or_(
                    Employee.termination_date.is_(None),
                    Employee.termination_date > period_end,
                ),
            )
        )
    ).scalar() or 0

    return {
        "period_start": period_start,
        "period_end": period_end,
        "hires": sum(hires_by_month.values()),
        "terminations": sum(leavers_by_month.values()),
        "ending_headcount": int(ending),
        "points": points,
    }