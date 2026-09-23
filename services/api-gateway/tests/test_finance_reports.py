"""
Tests for finance reporting, AR aging, FIFO inventory valuation,
depreciation calculations and year-end close.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.finance import (
    AccountingPeriod,
    FixedAsset,
    InsuranceClaimFinance,
    InventoryLot,
)
from app.services.finance import post_transaction
from app.services.finance.depreciation import calc_depreciation
from app.services.finance.inventory_valuation import (
    get_weighted_average_cost,
    post_inventory_usage,
)
from app.services.finance.periods import run_year_end_close
from app.services.finance.reports import (
    get_ar_aging,
    get_profit_loss,
    get_trial_balance,
)
from app.services.finance.seed_data import seed_facility_finance
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest_asyncio.fixture
async def seeded() -> AccountingPeriod:
    """Seed CoA + posting rules + an open period."""
    async with session_factory() as db:
        await seed_facility_finance(db, FACILITY_ID, USER_ID)
        period = AccountingPeriod(
            facility_id=FACILITY_ID,
            name="2026-05",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="open",
            year_end=False,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)
        return period


# ── Trial balance ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trial_balance_balances(seeded: AccountingPeriod) -> None:
    """Sum(debits) must equal sum(credits) at any time."""
    async with session_factory() as db:
        await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("1234.56"),
            {"date": "2026-05-05"},
            user_id=USER_ID,
        )
        await post_transaction(
            db,
            FACILITY_ID,
            "expense_paid",
            Decimal("250.00"),
            {"date": "2026-05-06"},
            user_id=USER_ID,
        )
        await db.commit()

    async with session_factory() as db:
        tb = await get_trial_balance(db, FACILITY_ID, period_id=seeded.id)
    assert tb.is_balanced is True
    assert tb.total_debits == tb.total_credits


# ── P&L ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profit_loss_computes_net(seeded: AccountingPeriod) -> None:
    """Net profit = income credits - expense debits."""
    async with session_factory() as db:
        await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("1000.00"),
            {"date": "2026-05-05"},
            user_id=USER_ID,
        )
        await post_transaction(
            db,
            FACILITY_ID,
            "expense_paid",
            Decimal("300.00"),
            {"date": "2026-05-06"},
            user_id=USER_ID,
        )
        await db.commit()

    async with session_factory() as db:
        pl = await get_profit_loss(db, FACILITY_ID, date(2026, 5, 1), date(2026, 5, 31))
    assert pl.total_income == Decimal("1000.00")
    assert pl.total_expenses == Decimal("300.00")
    assert pl.net_profit == Decimal("700.00")


# ── AR Aging ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ar_aging_buckets() -> None:
    """Outstanding insurance claims fall into the right bucket by age."""
    insurer_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    today = date(2026, 5, 31)

    async with session_factory() as db:
        # current
        db.add(
            InsuranceClaimFinance(
                facility_id=FACILITY_ID,
                patient_id=patient_id,
                insurer_id=insurer_id,
                amount_claimed=Decimal("100"),
                amount_approved=Decimal("0"),
                amount_paid=Decimal("0"),
                status="submitted",
                due_date=today,
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        # 60-day bucket
        db.add(
            InsuranceClaimFinance(
                facility_id=FACILITY_ID,
                patient_id=patient_id,
                insurer_id=insurer_id,
                amount_claimed=Decimal("200"),
                amount_approved=Decimal("0"),
                amount_paid=Decimal("0"),
                status="submitted",
                due_date=date(2026, 4, 1),  # 60 days outstanding
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        # 120+ bucket
        db.add(
            InsuranceClaimFinance(
                facility_id=FACILITY_ID,
                patient_id=patient_id,
                insurer_id=insurer_id,
                amount_claimed=Decimal("500"),
                amount_approved=Decimal("0"),
                amount_paid=Decimal("0"),
                status="submitted",
                due_date=date(2025, 11, 1),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    async with session_factory() as db:
        aging = await get_ar_aging(db, FACILITY_ID, today)

    assert aging.total_current == Decimal("100.00")
    assert aging.total_60 == Decimal("200.00")
    assert aging.total_120_plus == Decimal("500.00")
    assert aging.grand_total == Decimal("800.00")


# ── FIFO Inventory ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fifo_inventory_consumes_oldest_first() -> None:
    """FIFO consumes the oldest lot first."""
    item_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            InventoryLot(
                facility_id=FACILITY_ID,
                item_id=item_id,
                quantity=Decimal("10"),
                unit_cost=Decimal("5.0000"),
                received_date=date(2026, 1, 1),
                remaining_quantity=Decimal("10"),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        db.add(
            InventoryLot(
                facility_id=FACILITY_ID,
                item_id=item_id,
                quantity=Decimal("10"),
                unit_cost=Decimal("8.0000"),
                received_date=date(2026, 2, 1),
                remaining_quantity=Decimal("10"),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    async with session_factory() as db:
        cost = await post_inventory_usage(db, FACILITY_ID, item_id, Decimal("12"))
        await db.commit()
    # 10 @ 5 + 2 @ 8 = 50 + 16 = 66
    assert cost == Decimal("66.00")


@pytest.mark.asyncio
async def test_weighted_average_cost() -> None:
    """Weighted average = sum(qty*cost)/sum(qty)."""
    item_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            InventoryLot(
                facility_id=FACILITY_ID,
                item_id=item_id,
                quantity=Decimal("10"),
                unit_cost=Decimal("4.0000"),
                received_date=date(2026, 1, 1),
                remaining_quantity=Decimal("10"),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        db.add(
            InventoryLot(
                facility_id=FACILITY_ID,
                item_id=item_id,
                quantity=Decimal("30"),
                unit_cost=Decimal("6.0000"),
                received_date=date(2026, 2, 1),
                remaining_quantity=Decimal("30"),
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    async with session_factory() as db:
        wac = await get_weighted_average_cost(db, FACILITY_ID, item_id)
    # (10*4 + 30*6) / 40 = 220/40 = 5.5
    assert wac == Decimal("5.5000")


# ── Depreciation ─────────────────────────────────────────────────────────────


def test_straight_line_depreciation() -> None:
    """Straight line: (cost - salvage) / months."""
    asset = FixedAsset(
        id=uuid.uuid4(),
        facility_id=FACILITY_ID,
        name="X-ray machine",
        account_id=uuid.uuid4(),
        purchase_date=date(2026, 1, 1),
        purchase_cost=Decimal("120000.00"),
        useful_life_months=120,
        salvage_value=Decimal("12000.00"),
        depreciation_method="straight_line",
        accumulated_depreciation=Decimal("0"),
        is_active=True,
    )
    monthly = calc_depreciation(asset)
    # (120,000 - 12,000) / 120 = 900
    assert monthly == Decimal("900.00")


def test_declining_balance_depreciation() -> None:
    """Declining balance 200%: NBV * (2 / months)."""
    asset = FixedAsset(
        id=uuid.uuid4(),
        facility_id=FACILITY_ID,
        name="Generator",
        account_id=uuid.uuid4(),
        purchase_date=date(2026, 1, 1),
        purchase_cost=Decimal("60000.00"),
        useful_life_months=60,
        salvage_value=Decimal("0.00"),
        depreciation_method="declining_balance",
        accumulated_depreciation=Decimal("0"),
        is_active=True,
    )
    monthly = calc_depreciation(asset)
    # NBV 60000 * (2/60) = 2000
    assert monthly == Decimal("2000.00")


# ── Year-End Close ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_year_end_close_locks_period(seeded: AccountingPeriod) -> None:
    """After year-end close, the period status becomes 'locked'."""
    async with session_factory() as db:
        await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("500.00"),
            {"date": "2026-05-10"},
            user_id=USER_ID,
        )
        await db.commit()

    async with session_factory() as db:
        await run_year_end_close(db, FACILITY_ID, seeded.id, USER_ID)
        await db.commit()

    async with session_factory() as db:
        period = await db.get(AccountingPeriod, seeded.id)
    assert period is not None
    assert period.status == "locked"
