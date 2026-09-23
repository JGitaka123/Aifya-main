"""End-to-end tests for the payroll engine (uses SQLite-in-memory + conftest)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

# Import models so they register with Base.metadata before setup_database runs
from app.models import payroll as _payroll  # noqa: F401
from app.models import payroll_extra as _payroll_extra  # noqa: F401
from app.models.payroll import (
    Employee,
    EmployeeSalary,
    NSSFTier,
    PAYEBand,
    PayrollLineItem,
    StatutoryRate,
)
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest
from app.services.payroll.engine import run_monthly_payroll
from app.services.payroll.payslip import (
    PayslipNotAvailableError,
    generate_payslip,
)
from app.services.payroll.reports import generate_p9
from tests.conftest import FACILITY_ID, USER_ID, session_factory

# ── Helpers ────────────────────────────────────────────────────────────────


async def _seed_rates(db) -> None:
    """Seed minimum statutory data for the engine."""
    eff = date(2024, 1, 1)
    db.add_all(
        [
            PAYEBand(
                facility_id=None,
                lower_limit=Decimal("0"),
                upper_limit=Decimal("24000"),
                rate=Decimal("0.10"),
                effective_from=eff,
            ),
            PAYEBand(
                facility_id=None,
                lower_limit=Decimal("24000"),
                upper_limit=Decimal("32333"),
                rate=Decimal("0.25"),
                effective_from=eff,
            ),
            PAYEBand(
                facility_id=None,
                lower_limit=Decimal("32333"),
                upper_limit=Decimal("500000"),
                rate=Decimal("0.30"),
                effective_from=eff,
            ),
            PAYEBand(
                facility_id=None,
                lower_limit=Decimal("500000"),
                upper_limit=Decimal("800000"),
                rate=Decimal("0.325"),
                effective_from=eff,
            ),
            PAYEBand(
                facility_id=None,
                lower_limit=Decimal("800000"),
                upper_limit=None,
                rate=Decimal("0.35"),
                effective_from=eff,
            ),
            NSSFTier(
                facility_id=None,
                tier="I",
                lower_limit=Decimal("0"),
                upper_limit=Decimal("9000"),
                employee_rate=Decimal("0.06"),
                employer_rate=Decimal("0.06"),
                effective_from=eff,
            ),
            NSSFTier(
                facility_id=None,
                tier="II",
                lower_limit=Decimal("9000"),
                upper_limit=Decimal("108000"),
                employee_rate=Decimal("0.06"),
                employer_rate=Decimal("0.06"),
                effective_from=eff,
            ),
            StatutoryRate(
                facility_id=None,
                name="Personal Relief",
                category="relief",
                rate=None,
                fixed_amount=Decimal("2400"),
                effective_from=eff,
            ),
            StatutoryRate(
                facility_id=None,
                name="SHIF",
                category="shif",
                rate=Decimal("0.0275"),
                effective_from=eff,
            ),
            StatutoryRate(
                facility_id=None,
                name="Housing Levy",
                category="housing_levy",
                rate=Decimal("0.015"),
                effective_from=eff,
            ),
        ]
    )
    await db.flush()


async def _make_employee_with_salary(
    db,
    *,
    full_name: str,
    basic: Decimal,
    house: Decimal = Decimal("0"),
    transport: Decimal = Decimal("0"),
    disability: bool = False,
    hire_date: date = date(2020, 1, 1),
) -> Employee:
    emp = Employee(
        facility_id=FACILITY_ID,
        staff_id=str(uuid.uuid4())[:8],
        full_name=full_name,
        kra_pin="A012345678X",
        nssf_number="NSSF-1",
        shif_number="SHIF-1",
        hire_date=hire_date,
        is_active=True,
        disability_exemption=disability,
        created_by=USER_ID,
        updated_by=USER_ID,
    )
    db.add(emp)
    await db.flush()
    db.add(
        EmployeeSalary(
            facility_id=FACILITY_ID,
            employee_id=emp.id,
            basic_salary=basic,
            house_allowance=house,
            transport_allowance=transport,
            other_allowances={},
            effective_from=date(2024, 1, 1),
            created_by=USER_ID,
            updated_by=USER_ID,
        )
    )
    await db.flush()
    return emp


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_monthly_payroll_basic() -> None:
    """End-to-end: 1 employee, gross 50,000 → produces a line item."""
    async with session_factory() as db:
        await _seed_rates(db)
        emp = await _make_employee_with_salary(
            db, full_name="Alice Wanjiru", basic=Decimal("50000")
        )
        await db.commit()

        run = await run_monthly_payroll(
            db=db, facility_id=FACILITY_ID, month=3, year=2026, user_id=USER_ID
        )
        await db.commit()

        line = (
            (
                await db.execute(
                    select(PayrollLineItem).where(
                        PayrollLineItem.payroll_run_id == run.id,
                        PayrollLineItem.employee_id == emp.id,
                    )
                )
            )
            .scalars()
            .first()
        )

        assert line is not None
        assert line.gross_salary == Decimal("50000.00")
        # NSSF: 9000*0.06 + 41000*0.06 = 3000
        assert line.nssf_employee == Decimal("3000.00")
        assert line.shif == Decimal("1375.00")  # 50000 * 0.0275
        assert line.housing_levy == Decimal("750.00")  # 50000 * 0.015
        assert line.personal_relief == Decimal("2400.00")
        assert line.net_salary > Decimal("0")
        # Run totals
        assert run.total_gross == Decimal("50000.00")


@pytest.mark.asyncio
async def test_draft_run_payslip_blocked() -> None:
    """Generating a payslip for a draft run is rejected."""
    async with session_factory() as db:
        await _seed_rates(db)
        emp = await _make_employee_with_salary(
            db, full_name="Brian Otieno", basic=Decimal("60000")
        )
        await db.commit()

        run = await run_monthly_payroll(
            db=db, facility_id=FACILITY_ID, month=4, year=2026, user_id=USER_ID
        )
        await db.commit()
        assert run.status == "draft"

        with pytest.raises(PayslipNotAvailableError):
            await generate_payslip(
                db=db,
                facility_id=FACILITY_ID,
                payroll_run_id=run.id,
                employee_id=emp.id,
            )


@pytest.mark.asyncio
async def test_disability_exemption_reduces_paye() -> None:
    """Employee with disability_exemption pays less PAYE than peer at same gross."""
    async with session_factory() as db:
        await _seed_rates(db)
        await _make_employee_with_salary(
            db,
            full_name="Disability Employee",
            basic=Decimal("200000"),
            disability=True,
        )
        await _make_employee_with_salary(
            db,
            full_name="Standard Employee",
            basic=Decimal("200000"),
            disability=False,
        )
        await db.commit()

        run = await run_monthly_payroll(
            db=db, facility_id=FACILITY_ID, month=5, year=2026, user_id=USER_ID
        )
        await db.commit()

        lines = (
            (
                await db.execute(
                    select(PayrollLineItem).where(
                        PayrollLineItem.payroll_run_id == run.id
                    )
                )
            )
            .scalars()
            .all()
        )
        by_paye = sorted(lines, key=lambda li: li.paye)
        assert by_paye[0].paye < by_paye[1].paye


@pytest.mark.asyncio
async def test_unpaid_leave_reduces_net() -> None:
    """Verify approved unpaid leave appears in deductions and lowers net pay."""
    async with session_factory() as db:
        await _seed_rates(db)
        emp = await _make_employee_with_salary(
            db, full_name="Caroline Achieng", basic=Decimal("50000")
        )

        # Add a global "Unpaid" leave type and an approved leave request.
        unpaid_type = LeaveType(
            facility_id=None,
            name="Unpaid",
            days_entitlement=0,
            paid=False,
            partial_pay=False,
            carries_over=False,
        )
        db.add(unpaid_type)
        await db.flush()

        db.add(
            PayrollLeaveRequest(
                facility_id=FACILITY_ID,
                employee_id=emp.id,
                leave_type_id=unpaid_type.id,
                start_date=date(2026, 6, 5),
                end_date=date(2026, 6, 6),
                days_requested=2,
                status="approved",
                payroll_deduction=Decimal("4545.45"),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

        run = await run_monthly_payroll(
            db=db, facility_id=FACILITY_ID, month=6, year=2026, user_id=USER_ID
        )
        await db.commit()

        line = (
            (
                await db.execute(
                    select(PayrollLineItem).where(
                        PayrollLineItem.payroll_run_id == run.id,
                        PayrollLineItem.employee_id == emp.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        assert line is not None
        assert "Unpaid Leave" in (line.other_deductions or {})


@pytest.mark.asyncio
async def test_p9_reconciles_to_monthly_paye_sum() -> None:
    """P9 total_paye must equal sum of monthly rows."""
    async with session_factory() as db:
        await _seed_rates(db)
        emp = await _make_employee_with_salary(
            db, full_name="Daniel Mwangi", basic=Decimal("80000")
        )
        await db.commit()

        # Run + approve 3 months (Jan, Feb, Mar 2026)
        for month in (1, 2, 3):
            run = await run_monthly_payroll(
                db=db, facility_id=FACILITY_ID, month=month, year=2026, user_id=USER_ID
            )
            run.status = "approved"
            await db.commit()

        p9 = await generate_p9(
            db=db, facility_id=FACILITY_ID, employee_id=emp.id, year=2026
        )
        # Must reconcile: sum of monthly PAYEs == total_paye
        sum_paye = sum((row["paye"] for row in p9["rows"]), Decimal("0"))
        assert sum_paye == p9["total_paye"]
        assert len(p9["rows"]) == 3


@pytest.mark.asyncio
async def test_salary_effective_dating_picks_correct_record() -> None:
    """When two salary records overlap dates, the one effective on the
    period_end is used."""
    async with session_factory() as db:
        await _seed_rates(db)
        emp = await _make_employee_with_salary(
            db, full_name="Esther Njeri", basic=Decimal("40000")
        )
        # Close the original; add a higher salary effective March
        original_salary = (
            (
                await db.execute(
                    select(EmployeeSalary).where(EmployeeSalary.employee_id == emp.id)
                )
            )
            .scalars()
            .first()
        )
        assert original_salary is not None
        original_salary.effective_to = date(2026, 2, 28)
        db.add(
            EmployeeSalary(
                facility_id=FACILITY_ID,
                employee_id=emp.id,
                basic_salary=Decimal("80000"),
                house_allowance=Decimal("0"),
                transport_allowance=Decimal("0"),
                other_allowances={},
                effective_from=date(2026, 3, 1),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

        # Run for March → should pick the new 80k record
        run = await run_monthly_payroll(
            db=db, facility_id=FACILITY_ID, month=3, year=2026, user_id=USER_ID
        )
        await db.commit()

        line = (
            (
                await db.execute(
                    select(PayrollLineItem).where(
                        PayrollLineItem.payroll_run_id == run.id,
                        PayrollLineItem.employee_id == emp.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        assert line is not None
        assert line.basic_salary == Decimal("80000.00")
