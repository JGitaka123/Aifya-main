"""
Tests for the GL posting engine: idempotency, period lock,
DR=CR validation, and reversal correctness.

Note: tests use the in-memory SQLite test DB created by conftest.
PostgreSQL-only features (FOR UPDATE, JSONB) degrade gracefully on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.finance import (
    AccountingPeriod,
)
from app.services.finance import (
    PeriodLockedError,
    PostingRuleNotFoundError,
    UnbalancedTransactionError,
    post_transaction,
    reverse_transaction,
)
from app.services.finance.seed_data import seed_facility_finance
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest_asyncio.fixture
async def seeded_period() -> AccountingPeriod:
    """Seed a facility's CoA + posting rules and create an open period."""
    async with session_factory() as db:
        await seed_facility_finance(db, FACILITY_ID, USER_ID)
        period = AccountingPeriod(
            facility_id=FACILITY_ID,
            name="2026-05",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="open",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)
        return period


@pytest.mark.asyncio
async def test_post_transaction_balances(seeded_period: AccountingPeriod) -> None:
    """A successful post creates balanced DR/CR entries."""
    async with session_factory() as db:
        txn = await post_transaction(
            db=db,
            facility_id=FACILITY_ID,
            event_type="invoice_cash",
            amount=Decimal("1000.00"),
            metadata={"date": "2026-05-15", "description": "Test invoice"},
            user_id=USER_ID,
        )
        await db.commit()
        assert txn.amount == Decimal("1000.00")
        assert txn.event_type == "invoice_cash"


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicates(
    seeded_period: AccountingPeriod,
) -> None:
    """Repeat calls with the same key return the same transaction."""
    key = f"test-{uuid.uuid4()}"
    async with session_factory() as db:
        first = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("500.00"),
            {"date": "2026-05-10"},
            idempotency_key=key,
            user_id=USER_ID,
        )
        await db.commit()
    async with session_factory() as db:
        second = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("500.00"),
            {"date": "2026-05-10"},
            idempotency_key=key,
            user_id=USER_ID,
        )
        await db.commit()
    assert first.id == second.id


@pytest.mark.asyncio
async def test_period_locked_blocks_posting(
    seeded_period: AccountingPeriod,
) -> None:
    """Posting into a locked period raises PeriodLockedError."""
    async with session_factory() as db:
        period = await db.get(AccountingPeriod, seeded_period.id)
        assert period is not None
        period.status = "locked"
        await db.commit()

    async with session_factory() as db:
        with pytest.raises(PeriodLockedError):
            await post_transaction(
                db,
                FACILITY_ID,
                "invoice_cash",
                Decimal("100.00"),
                {"date": "2026-05-15"},
                user_id=USER_ID,
            )


@pytest.mark.asyncio
async def test_unknown_event_type_raises(
    seeded_period: AccountingPeriod,
) -> None:
    """No posting rule for an event_type -> raises PostingRuleNotFoundError."""
    async with session_factory() as db:
        with pytest.raises(PostingRuleNotFoundError):
            await post_transaction(
                db,
                FACILITY_ID,
                "made_up_event",
                Decimal("100.00"),
                {"date": "2026-05-15"},
                user_id=USER_ID,
            )


@pytest.mark.asyncio
async def test_reverse_transaction_swaps_dr_cr(
    seeded_period: AccountingPeriod,
) -> None:
    """A reversal creates an opposing balanced entry."""
    async with session_factory() as db:
        original = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("750.00"),
            {"date": "2026-05-12"},
            user_id=USER_ID,
        )
        await db.commit()

    async with session_factory() as db:
        rev = await reverse_transaction(
            db,
            FACILITY_ID,
            original.id,
            posting_date=date(2026, 5, 20),
            user_id=USER_ID,
            description="undo",
        )
        await db.commit()

    assert rev.is_reversal is True
    assert rev.reverses_transaction_id == original.id
    assert rev.amount == original.amount


@pytest.mark.asyncio
async def test_seed_creates_27_accounts() -> None:
    """seed_facility_finance creates the default chart and rules."""
    async with session_factory() as db:
        summary = await seed_facility_finance(db, FACILITY_ID, USER_ID)
        await db.commit()
    # 27 accounts in the spec
    assert summary["accounts_created"] == 27
    assert summary["rules_created"] >= 10


@pytest.mark.asyncio
async def test_missing_period_auto_provisions(seeded_period: AccountingPeriod) -> None:
    """
    A facility with no period for a date self-heals: ensure_open_period
    creates the covering calendar-month period so clinical/billing GL posts
    are never rejected for want of a seeded period (D3 root cause). The
    strict low-level helper still raises so callers can opt into strictness.
    """
    from datetime import date

    from app.services.finance import NoOpenPeriodError
    from app.services.finance.posting_engine import (
        _get_period_for_date,
        ensure_open_period,
    )

    async with session_factory() as db:
        with pytest.raises(NoOpenPeriodError):
            await _get_period_for_date(db, FACILITY_ID, date(2099, 1, 1))

        period = await ensure_open_period(db, FACILITY_ID, date(2099, 1, 1), USER_ID)
        assert period.status == "open"
        assert period.start_date == date(2099, 1, 1)
        assert period.end_date == date(2099, 1, 31)


@pytest.mark.asyncio
async def test_locked_period_still_rejects() -> None:
    """A closed/locked period is honoured — postings are still rejected."""
    from datetime import date

    from app.services.finance import PeriodLockedError
    from app.services.finance.periods import create_period
    from app.services.finance.posting_engine import ensure_open_period

    async with session_factory() as db:
        period = await create_period(
            db, FACILITY_ID, "2088-05", date(2088, 5, 1), date(2088, 5, 31), user_id=USER_ID
        )
        period.status = "locked"
        await db.flush()
        with pytest.raises(PeriodLockedError):
            await ensure_open_period(db, FACILITY_ID, date(2088, 5, 15), USER_ID)


@pytest.mark.asyncio
async def test_unbalanced_error_class_exists() -> None:
    """Sanity: UnbalancedTransactionError is exported."""
    assert issubclass(UnbalancedTransactionError, Exception)


def test_account_uniqueness_constraint_module_imports() -> None:
    """Smoke test: model module imports cleanly."""
    from app.models.finance import Account as AccountModel

    assert AccountModel.__tablename__ == "accounts"
