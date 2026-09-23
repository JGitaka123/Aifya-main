"""
Accounting period management.

Periods can be: ``open`` -> ``closed`` -> ``locked``.
Year-end close sweeps income/expense balances to Retained Earnings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    Account,
    AccountingPeriod,
    FinanceAuditLog,
    Transaction,
    TransactionEntry,
)
from app.services.finance.posting_engine import (
    PeriodLockedError,
    post_transaction,
)

_ZERO = Decimal("0")
_QUANT = Decimal("0.01")
_RETAINED_EARNINGS_CODE = "3010"


def _q(value: Decimal | int | float) -> Decimal:
    """Quantise to 2dp."""
    return Decimal(value).quantize(_QUANT)


# ── Period CRUD ──────────────────────────────────────────────────────────────


async def create_period(
    db: AsyncSession,
    facility_id: uuid.UUID,
    name: str,
    start: date_type,
    end: date_type,
    year_end: bool = False,
    user_id: uuid.UUID | None = None,
) -> AccountingPeriod:
    """
    Create a new accounting period.

    @param db: Database session
    @param facility_id: Facility scope
    @param name: Period name (e.g. ``2026-05``)
    @param start: Inclusive start date
    @param end: Inclusive end date
    @param year_end: True if this period is the fiscal year end
    @param user_id: Creator
    @returns Newly-created period
    """
    period = AccountingPeriod(
        facility_id=facility_id,
        name=name,
        start_date=start,
        end_date=end,
        status="open",
        year_end=year_end,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(period)
    await db.flush()
    return period


async def assert_period_open(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
) -> AccountingPeriod:
    """
    Ensure a period is open. Raises ``PeriodLockedError`` if not.

    @returns The open period
    """
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.facility_id == facility_id,
        )
    )
    period = result.scalar_one()
    if period.status != "open":
        raise PeriodLockedError(f"Period '{period.name}' is {period.status}")
    return period


async def close_period(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AccountingPeriod:
    """
    Close a period (status = closed). New postings rejected; can still be reopened.

    @param db: Database session
    @param facility_id: Facility scope
    @param period_id: Period to close
    @param user_id: User closing it
    @returns Closed period
    """
    period = await assert_period_open(db, facility_id, period_id)
    period.status = "closed"
    period.closed_by = user_id
    period.closed_at = datetime.now(UTC)
    period.updated_by = user_id

    db.add(
        FinanceAuditLog(
            facility_id=facility_id,
            action="close_period",
            table_name="accounting_periods",
            record_id=period_id,
            user_id=user_id,
            payload={"period_name": period.name},
        )
    )
    await db.flush()
    return period


async def lock_period(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AccountingPeriod:
    """
    Permanently lock a period (after year-end close). Cannot be reopened.

    @returns Locked period
    """
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.facility_id == facility_id,
        )
    )
    period = result.scalar_one()
    period.status = "locked"
    period.updated_by = user_id

    db.add(
        FinanceAuditLog(
            facility_id=facility_id,
            action="lock_period",
            table_name="accounting_periods",
            record_id=period_id,
            user_id=user_id,
            payload={"period_name": period.name},
        )
    )
    await db.flush()
    return period


# ── Year-End Close ───────────────────────────────────────────────────────────


async def run_year_end_close(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Transaction | None:
    """
    Sweep income & expense balances into Retained Earnings, then auto-lock.

    Steps:
      1. Compute net of (income credits - income debits) and
         (expense debits - expense credits) for the period.
      2. Post a single closing entry that zeroes income & expenses,
         net to Retained Earnings (account code 3010).
      3. Lock the period.

    @param db: Database session
    @param facility_id: Facility scope
    @param period_id: Year-end period
    @param user_id: User running the close
    @returns The closing transaction (None if nothing to close)
    """
    period = await assert_period_open(db, facility_id, period_id)

    # Find Retained Earnings account
    re_result = await db.execute(
        select(Account).where(
            Account.facility_id == facility_id,
            Account.code == _RETAINED_EARNINGS_CODE,
            Account.is_deleted == False,  # noqa: E712
        )
    )
    re_account = re_result.scalar_one()

    # Compute net per income/expense account
    stmt = (
        select(
            Account.id,
            Account.type,
            func.coalesce(func.sum(TransactionEntry.debit), 0),
            func.coalesce(func.sum(TransactionEntry.credit), 0),
        )
        .join(
            TransactionEntry,
            (TransactionEntry.account_id == Account.id)
            & (TransactionEntry.facility_id == facility_id),
            isouter=True,
        )
        .join(
            Transaction,
            (TransactionEntry.transaction_id == Transaction.id)
            & (Transaction.facility_id == facility_id)
            & (Transaction.date >= period.start_date)
            & (Transaction.date <= period.end_date),
            isouter=True,
        )
        .where(
            Account.facility_id == facility_id,
            Account.is_deleted == False,  # noqa: E712
            Account.type.in_(["income", "expense"]),
        )
        .group_by(Account.id, Account.type)
    )
    rows = (await db.execute(stmt)).all()

    # Filter out rows where Account.id is None (no entries) — outerjoin produces NULLs
    rows = [r for r in rows if r[0] is not None]

    if not rows:
        await lock_period(db, facility_id, period_id, user_id)
        return None

    # Build closing transaction
    closing_txn = Transaction(
        facility_id=facility_id,
        date=period.end_date,
        event_type="year_end_close",
        description=f"Year-end close — {period.name}",
        period_id=period.id,
        amount=_ZERO,
        is_reversal=False,
        created_by=user_id,
    )
    db.add(closing_txn)
    await db.flush()

    total_dr = _ZERO
    total_cr = _ZERO

    # Net to retained earnings: income (credit balance) -> DR income, CR RE
    # expense (debit balance) -> CR expense, DR RE
    re_net = _ZERO

    for acct_id, atype, dr, cr in rows:
        dr_d = Decimal(dr)
        cr_d = Decimal(cr)
        if atype == "income":
            net = cr_d - dr_d  # income should be positive credit
            if net == 0:
                continue
            if net > 0:
                # DR income (close it), CR Retained Earnings
                db.add(
                    TransactionEntry(
                        facility_id=facility_id,
                        transaction_id=closing_txn.id,
                        account_id=acct_id,
                        debit=_q(net),
                        credit=_ZERO,
                    )
                )
                total_dr += _q(net)
                re_net += _q(net)
            else:
                amount = _q(abs(net))
                db.add(
                    TransactionEntry(
                        facility_id=facility_id,
                        transaction_id=closing_txn.id,
                        account_id=acct_id,
                        debit=_ZERO,
                        credit=amount,
                    )
                )
                total_cr += amount
                re_net -= amount
        else:  # expense
            net = dr_d - cr_d  # expense should be positive debit
            if net == 0:
                continue
            if net > 0:
                # CR expense (close it), DR Retained Earnings
                db.add(
                    TransactionEntry(
                        facility_id=facility_id,
                        transaction_id=closing_txn.id,
                        account_id=acct_id,
                        debit=_ZERO,
                        credit=_q(net),
                    )
                )
                total_cr += _q(net)
                re_net -= _q(net)
            else:
                amount = _q(abs(net))
                db.add(
                    TransactionEntry(
                        facility_id=facility_id,
                        transaction_id=closing_txn.id,
                        account_id=acct_id,
                        debit=amount,
                        credit=_ZERO,
                    )
                )
                total_dr += amount
                re_net += amount

    # Net plug to Retained Earnings to balance the close
    if re_net > 0:
        # Net profit: CR Retained Earnings
        db.add(
            TransactionEntry(
                facility_id=facility_id,
                transaction_id=closing_txn.id,
                account_id=re_account.id,
                debit=_ZERO,
                credit=_q(re_net),
            )
        )
        total_cr += _q(re_net)
    elif re_net < 0:
        # Net loss: DR Retained Earnings
        db.add(
            TransactionEntry(
                facility_id=facility_id,
                transaction_id=closing_txn.id,
                account_id=re_account.id,
                debit=_q(abs(re_net)),
                credit=_ZERO,
            )
        )
        total_dr += _q(abs(re_net))

    if _q(total_dr) != _q(total_cr):
        from app.services.finance.posting_engine import (
            UnbalancedTransactionError,
        )

        raise UnbalancedTransactionError(
            f"Year-end close unbalanced: DR={total_dr} CR={total_cr}"
        )

    closing_txn.amount = _q(total_dr)

    db.add(
        FinanceAuditLog(
            facility_id=facility_id,
            action="year_end_close",
            table_name="transactions",
            record_id=closing_txn.id,
            user_id=user_id,
            payload={
                "period_id": str(period_id),
                "total_dr": str(total_dr),
                "total_cr": str(total_cr),
                "re_net": str(re_net),
            },
        )
    )

    # Lock the period
    period.status = "locked"
    period.closed_by = user_id
    period.closed_at = datetime.now(UTC)
    period.updated_by = user_id

    await db.flush()
    return closing_txn


# silence "unused" lints — post_transaction is re-exported by package
_ = post_transaction
