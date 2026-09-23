"""13-step monthly payroll calculation engine.

Wraps the entire run in a single DB transaction. Skips employees with
missing salary records, logging a warning rather than failing.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import (
    Employee,
    EmployeeSalary,
    NSSFTier,
    PAYEBand,
    PayrollLineItem,
    PayrollRun,
    StatutoryRate,
)
from app.models.payroll_extra import (
    EmployeeDeduction,
    PayrollLeaveRequest,
)
from app.services.payroll.statutory import (
    NSSFTierSpec,
    PAYEBandSpec,
    calc_employer_housing_levy,
    calc_employer_nssf,
    calc_housing_levy,
    calc_insurance_relief,
    calc_nssf,
    calc_paye,
    calc_shif,
)

_logger = logging.getLogger(__name__)
_ZERO = Decimal("0")
_PERSONAL_RELIEF_DEFAULT = Decimal("2400")
_DISABILITY_EXEMPTION = Decimal("150000")


def _period_bounds(month: int, year: int) -> tuple[date, date]:
    """Return (first, last) dates of the given month."""
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


def _working_days(year: int, month: int) -> int:
    """Working days in a month, Mon-Fri (rough; refine via holiday calendar later)."""
    first_day, last_day = _period_bounds(month, year)
    count = 0
    d = first_day
    while d <= last_day:
        if d.weekday() < 5:
            count += 1
        d = date.fromordinal(d.toordinal() + 1)
    return count or 22


async def _load_paye_bands(
    db: AsyncSession, facility_id: uuid.UUID, target: date
) -> list[PAYEBandSpec]:
    """Effective PAYE bands for the period (facility override beats global)."""
    stmt = (
        select(PAYEBand)
        .where(
            PAYEBand.is_deleted.is_(False),
            PAYEBand.effective_from <= target,
            or_(
                PAYEBand.effective_to.is_(None),
                PAYEBand.effective_to >= target,
            ),
            or_(
                PAYEBand.facility_id == facility_id,
                PAYEBand.facility_id.is_(None),
            ),
        )
        .order_by(PAYEBand.lower_limit.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    # Prefer facility overrides — if any row has facility_id == facility_id, drop globals.
    if any(r.facility_id is not None for r in rows):
        rows = [r for r in rows if r.facility_id is not None]
    return [
        PAYEBandSpec(
            lower_limit=Decimal(b.lower_limit),
            upper_limit=Decimal(b.upper_limit) if b.upper_limit is not None else None,
            rate=Decimal(b.rate),
        )
        for b in rows
    ]


async def _load_nssf_tiers(
    db: AsyncSession, facility_id: uuid.UUID, target: date
) -> list[NSSFTierSpec]:
    """Effective NSSF tiers for the period."""
    stmt = (
        select(NSSFTier)
        .where(
            NSSFTier.is_deleted.is_(False),
            NSSFTier.effective_from <= target,
            or_(
                NSSFTier.effective_to.is_(None),
                NSSFTier.effective_to >= target,
            ),
            or_(
                NSSFTier.facility_id == facility_id,
                NSSFTier.facility_id.is_(None),
            ),
        )
        .order_by(NSSFTier.lower_limit.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    if any(r.facility_id is not None for r in rows):
        rows = [r for r in rows if r.facility_id is not None]
    return [
        NSSFTierSpec(
            tier=t.tier,
            lower_limit=Decimal(t.lower_limit),
            upper_limit=Decimal(t.upper_limit),
            employee_rate=Decimal(t.employee_rate),
            employer_rate=Decimal(t.employer_rate),
        )
        for t in rows
    ]


async def _load_rate_value(
    db: AsyncSession,
    facility_id: uuid.UUID,
    category: str,
    name: str,
    target: date,
    field: str,
) -> Decimal | None:
    """Get a single statutory rate field (rate / fixed_amount / fixed_cap)."""
    stmt = (
        select(StatutoryRate)
        .where(
            StatutoryRate.is_deleted.is_(False),
            StatutoryRate.category == category,
            StatutoryRate.name == name,
            StatutoryRate.effective_from <= target,
            or_(
                StatutoryRate.effective_to.is_(None),
                StatutoryRate.effective_to >= target,
            ),
            or_(
                StatutoryRate.facility_id == facility_id,
                StatutoryRate.facility_id.is_(None),
            ),
        )
        .order_by(
            StatutoryRate.facility_id.is_(None).asc(),  # facility override first
            StatutoryRate.effective_from.desc(),
        )
    )
    row = (await db.execute(stmt)).scalars().first()
    if row is None:
        return None
    val = getattr(row, field)
    return Decimal(val) if val is not None else None


async def _load_active_salary(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    target: date,
) -> EmployeeSalary | None:
    """Return the salary record effective for the given period date."""
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
    return (await db.execute(stmt)).scalars().first()


async def _sum_other_deductions(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> tuple[Decimal, dict[str, str]]:
    """Sum recurring + one-time deductions falling in the period.

    @returns (total, breakdown) where breakdown maps name -> amount string.
    """
    stmt = select(EmployeeDeduction).where(
        EmployeeDeduction.is_deleted.is_(False),
        EmployeeDeduction.facility_id == facility_id,
        EmployeeDeduction.employee_id == employee_id,
        EmployeeDeduction.is_active.is_(True),
        EmployeeDeduction.start_date <= period_end,
        or_(
            EmployeeDeduction.end_date.is_(None),
            EmployeeDeduction.end_date >= period_start,
        ),
    )
    rows = (await db.execute(stmt)).scalars().all()
    total = _ZERO
    breakdown: dict[str, str] = {}
    for d in rows:
        if d.frequency == "one_time" and not (
            period_start <= d.start_date <= period_end
        ):
            continue
        amount = Decimal(d.amount)
        total += amount
        breakdown[d.name] = str(amount)
    return total, breakdown


async def _sum_unpaid_leave(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> Decimal:
    """Sum payroll_deduction across approved unpaid leave overlapping the period."""
    stmt = select(PayrollLeaveRequest).where(
        PayrollLeaveRequest.is_deleted.is_(False),
        PayrollLeaveRequest.facility_id == facility_id,
        PayrollLeaveRequest.employee_id == employee_id,
        PayrollLeaveRequest.status == "approved",
        PayrollLeaveRequest.start_date <= period_end,
        PayrollLeaveRequest.end_date >= period_start,
    )
    rows = (await db.execute(stmt)).scalars().all()
    total = _ZERO
    for r in rows:
        total += Decimal(r.payroll_deduction or 0)
    return total


async def run_monthly_payroll(
    db: AsyncSession,
    facility_id: uuid.UUID,
    month: int,
    year: int,
    user_id: uuid.UUID,
) -> PayrollRun:
    """Calculate a draft payroll run for all active employees.

    Wraps every line in the same DB transaction (caller commits). Skips
    employees with missing/zero salary, logging a warning. Returns the
    PayrollRun instance with line_items relationship populated via re-query.

    @param db: Async SQLAlchemy session
    @param facility_id: Tenant facility UUID
    @param month: 1..12
    @param year: 4-digit year
    @param user_id: User running the payroll
    @returns Newly-created draft PayrollRun
    """
    if not (1 <= month <= 12):
        raise ValueError("month must be 1..12")

    period_start, period_end = _period_bounds(month, year)
    _working_days(year, month)

    # Reject duplicate active runs for this period
    dup = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.is_deleted.is_(False),
                PayrollRun.facility_id == facility_id,
                PayrollRun.month == month,
                PayrollRun.year == year,
                PayrollRun.status.in_(["approved", "posted", "locked"]),
            )
        )
    ).scalars().first()
    if dup is not None:
        raise ValueError(
            f"An active payroll run already exists for {year}-{month:02d}"
        )

    # Load rate tables once
    paye_bands = await _load_paye_bands(db, facility_id, period_end)
    nssf_tiers = await _load_nssf_tiers(db, facility_id, period_end)
    shif_rate = await _load_rate_value(
        db, facility_id, "shif", "SHIF", period_end, "rate"
    ) or Decimal("0.0275")
    hl_rate = await _load_rate_value(
        db, facility_id, "housing_levy", "Housing Levy", period_end, "rate"
    ) or Decimal("0.015")
    personal_relief = await _load_rate_value(
        db, facility_id, "relief", "Personal Relief", period_end, "fixed_amount"
    ) or _PERSONAL_RELIEF_DEFAULT

    run = PayrollRun(
        facility_id=facility_id,
        month=month,
        year=year,
        status="draft",
        run_date=datetime.now(UTC),
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(run)
    await db.flush()

    # Active employees as of period_end (hire_date <= period_end, not terminated before period_start)
    employees = (
        await db.execute(
            select(Employee).where(
                Employee.is_deleted.is_(False),
                Employee.facility_id == facility_id,
                Employee.is_active.is_(True),
                Employee.hire_date <= period_end,
                or_(
                    Employee.termination_date.is_(None),
                    Employee.termination_date >= period_start,
                ),
            )
        )
    ).scalars().all()

    totals = {
        "gross": _ZERO,
        "paye": _ZERO,
        "nssf": _ZERO,
        "shif": _ZERO,
        "hl": _ZERO,
        "net": _ZERO,
        "emp_nssf": _ZERO,
        "emp_hl": _ZERO,
    }

    for emp in employees:
        salary = await _load_active_salary(db, facility_id, emp.id, period_end)
        if salary is None:
            _logger.warning(
                "payroll.skip_no_salary",
                extra={
                    "employee_id": str(emp.id),
                    "facility_id": str(facility_id),
                    "period": f"{year}-{month:02d}",
                },
            )
            continue

        basic = Decimal(salary.basic_salary or 0)
        house = Decimal(salary.house_allowance or 0)
        transport = Decimal(salary.transport_allowance or 0)

        other_alw_raw = salary.other_allowances or {}
        other_alw_sum = _ZERO
        for v in other_alw_raw.values():
            try:
                other_alw_sum += Decimal(str(v))
            except (ValueError, ArithmeticError):
                continue

        # Step 1
        gross = basic + house + transport + other_alw_sum

        if gross <= _ZERO:
            _logger.warning(
                "payroll.skip_zero_gross",
                extra={"employee_id": str(emp.id), "period": f"{year}-{month:02d}"},
            )
            continue

        # Step 2
        nssf_emp = calc_nssf(gross, nssf_tiers)
        # Step 3
        shif = calc_shif(gross, shif_rate)
        # Step 4
        hl = calc_housing_levy(gross, hl_rate)
        # Step 5
        disability_ex = _DISABILITY_EXEMPTION if emp.disability_exemption else _ZERO
        # Step 6
        taxable_pay = gross - nssf_emp - shif - hl - disability_ex
        if taxable_pay < _ZERO:
            taxable_pay = _ZERO
        # Step 7
        gross_paye = calc_paye(taxable_pay, paye_bands)
        # Step 8
        relief = personal_relief
        # Step 9
        ins_relief = calc_insurance_relief(_ZERO)  # premium lookup TBD
        # Step 10
        paye = gross_paye - relief - ins_relief
        if paye < _ZERO:
            paye = _ZERO

        # Step 11: other deductions = recurring + unpaid leave
        other_total, other_breakdown = await _sum_other_deductions(
            db, facility_id, emp.id, period_start, period_end
        )
        unpaid_leave = await _sum_unpaid_leave(
            db, facility_id, emp.id, period_start, period_end
        )
        if unpaid_leave > _ZERO:
            other_total += unpaid_leave
            other_breakdown["Unpaid Leave"] = str(unpaid_leave)

        # Step 12
        total_deductions = paye + nssf_emp + shif + hl + other_total
        # Step 13
        net = gross - total_deductions

        # Employer side
        emp_nssf = calc_employer_nssf(gross, nssf_tiers)
        emp_hl = calc_employer_housing_levy(gross, hl_rate)

        line = PayrollLineItem(
            facility_id=facility_id,
            payroll_run_id=run.id,
            employee_id=emp.id,
            basic_salary=basic,
            house_allowance=house,
            transport_allowance=transport,
            other_allowances={k: str(v) for k, v in other_alw_raw.items()},
            gross_salary=gross,
            nssf_employee=nssf_emp,
            shif=shif,
            housing_levy=hl,
            taxable_pay=taxable_pay,
            paye_gross=gross_paye,
            personal_relief=relief,
            insurance_relief=ins_relief,
            paye=paye,
            other_deductions=other_breakdown,
            total_deductions=total_deductions,
            net_salary=net,
            employer_nssf=emp_nssf,
            employer_housing_levy=emp_hl,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(line)
        totals["gross"] += gross
        totals["paye"] += paye
        totals["nssf"] += nssf_emp
        totals["shif"] += shif
        totals["hl"] += hl
        totals["net"] += net
        totals["emp_nssf"] += emp_nssf
        totals["emp_hl"] += emp_hl

    run.total_gross = totals["gross"]
    run.total_paye = totals["paye"]
    run.total_nssf = totals["nssf"]
    run.total_shif = totals["shif"]
    run.total_hl = totals["hl"]
    run.total_net = totals["net"]
    run.total_employer_nssf = totals["emp_nssf"]
    run.total_employer_hl = totals["emp_hl"]

    await db.flush()
    await db.refresh(run)
    return run
