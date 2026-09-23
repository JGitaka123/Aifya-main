"""
Finance reporting engine.

All reports are computed on-demand from ``transaction_entries`` —
no caching, single source of truth.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    Account,
    AccountingPeriod,
    Budget,
    InsuranceClaimFinance,
    OpeningBalance,
    Transaction,
    TransactionEntry,
)
from app.schemas.finance import (
    ARAgingResponse,
    ARAgingRow,
    BalanceSheetResponse,
    BalanceSheetSection,
    BudgetVsActualResponse,
    BudgetVsActualRow,
    CashFlowResponse,
    CashFlowSection,
    GeneralLedgerEntry,
    GeneralLedgerResponse,
    ProfitLossResponse,
    ProfitLossRow,
    TrialBalanceResponse,
    TrialBalanceRow,
)

_ZERO = Decimal("0")
_QUANT = Decimal("0.01")


def _q(value: Decimal | None) -> Decimal:
    """Quantise a Decimal to 2dp; treat None as zero."""
    if value is None:
        return _ZERO
    return Decimal(value).quantize(_QUANT)


# ── General Ledger ───────────────────────────────────────────────────────────


async def get_general_ledger(
    db: AsyncSession,
    facility_id: uuid.UUID,
    account_id: uuid.UUID,
    start: date_type,
    end: date_type,
) -> GeneralLedgerResponse:
    """
    Get the general ledger for a single account with running balance.

    @param db: Database session
    @param facility_id: Facility scope
    @param account_id: Account to query
    @param start: Inclusive start date
    @param end: Inclusive end date
    @returns Per-entry running balance + opening/closing
    """
    account_result = await db.execute(
        select(Account).where(
            Account.id == account_id, Account.facility_id == facility_id
        )
    )
    account = account_result.scalar_one()

    # Opening balance: sum of entries before ``start``
    opening_result = await db.execute(
        select(
            func.coalesce(func.sum(TransactionEntry.debit), 0),
            func.coalesce(func.sum(TransactionEntry.credit), 0),
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
            Transaction.date < start,
        )
    )
    opening_dr, opening_cr = opening_result.first() or (0, 0)
    opening_balance = _q(Decimal(opening_dr) - Decimal(opening_cr))

    # Period entries
    rows_result = await db.execute(
        select(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            TransactionEntry.debit,
            TransactionEntry.credit,
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .order_by(Transaction.date.asc(), Transaction.created_at.asc())
    )

    entries: list[GeneralLedgerEntry] = []
    running = opening_balance
    for txn_id, txn_date, desc, dr, cr in rows_result.all():
        running = _q(running + Decimal(dr) - Decimal(cr))
        entries.append(
            GeneralLedgerEntry(
                transaction_id=txn_id,
                date=txn_date,
                description=desc,
                debit=_q(dr),
                credit=_q(cr),
                balance=running,
            )
        )

    return GeneralLedgerResponse(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        opening_balance=opening_balance,
        entries=entries,
        closing_balance=running,
    )


# ── Trial Balance ────────────────────────────────────────────────────────────


async def get_trial_balance(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID | None = None,
    as_of: date_type | None = None,
) -> TrialBalanceResponse:
    """
    Compute the trial balance per account.

    @param db: Database session
    @param facility_id: Facility scope
    @param period_id: Optional period filter
    @param as_of: Optional cutoff date
    @returns Trial balance with totals + balanced flag
    """
    end_date = as_of
    if period_id is not None:
        period_result = await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == period_id,
                AccountingPeriod.facility_id == facility_id,
            )
        )
        period = period_result.scalar_one()
        end_date = period.end_date

    if end_date is None:
        end_date = date_type.today()

    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(TransactionEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(TransactionEntry.credit), 0).label("cr"),
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
            & (Transaction.facility_id == facility_id),
            isouter=True,
        )
        .where(
            Account.facility_id == facility_id,
            Account.is_deleted == False,  # noqa: E712
        )
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code.asc())
    )

    if end_date is not None:
        stmt = stmt.where(
            (Transaction.date <= end_date) | (Transaction.date.is_(None))
        )

    result = await db.execute(stmt)

    rows: list[TrialBalanceRow] = []
    total_dr = _ZERO
    total_cr = _ZERO
    for acct_id, code, name, atype, dr, cr in result.all():
        dr_d = _q(Decimal(dr))
        cr_d = _q(Decimal(cr))
        rows.append(
            TrialBalanceRow(
                account_id=acct_id,
                account_code=code,
                account_name=name,
                account_type=atype,
                debit_total=dr_d,
                credit_total=cr_d,
            )
        )
        total_dr += dr_d
        total_cr += cr_d

    return TrialBalanceResponse(
        period_id=period_id,
        as_of=end_date,
        rows=rows,
        total_debits=_q(total_dr),
        total_credits=_q(total_cr),
        is_balanced=_q(total_dr) == _q(total_cr),
    )


# ── Profit & Loss ────────────────────────────────────────────────────────────


async def get_profit_loss(
    db: AsyncSession,
    facility_id: uuid.UUID,
    start: date_type,
    end: date_type,
    department_id: uuid.UUID | None = None,
) -> ProfitLossResponse:
    """
    Compute P&L for the date range.

    Income accounts:  amount = credits - debits
    Expense accounts: amount = debits - credits
    Net Profit = Total Income - Total Expenses.

    @param db: Database session
    @param facility_id: Facility scope
    @param start: Start date
    @param end: End date
    @param department_id: Optional department filter
    @returns Income, expenses, and net profit
    """
    conds = [
        Account.facility_id == facility_id,
        Account.is_deleted == False,  # noqa: E712
        Account.type.in_(["income", "expense"]),
    ]
    txn_conds = [
        Transaction.facility_id == facility_id,
        Transaction.date >= start,
        Transaction.date <= end,
    ]
    if department_id is not None:
        txn_conds.append(TransactionEntry.department_id == department_id)

    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(TransactionEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(TransactionEntry.credit), 0).label("cr"),
        )
        .join(
            TransactionEntry,
            (TransactionEntry.account_id == Account.id)
            & (TransactionEntry.facility_id == facility_id),
            isouter=True,
        )
        .join(
            Transaction,
            and_(
                TransactionEntry.transaction_id == Transaction.id,
                *txn_conds,
            ),
            isouter=True,
        )
        .where(*conds)
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code.asc())
    )

    result = await db.execute(stmt)

    income: list[ProfitLossRow] = []
    expenses: list[ProfitLossRow] = []
    total_income = _ZERO
    total_expenses = _ZERO

    for acct_id, code, name, atype, dr, cr in result.all():
        dr_d = Decimal(dr)
        cr_d = Decimal(cr)
        if atype == "income":
            amt = _q(cr_d - dr_d)
            income.append(
                ProfitLossRow(
                    account_id=acct_id, account_code=code,
                    account_name=name, amount=amt,
                )
            )
            total_income += amt
        else:
            amt = _q(dr_d - cr_d)
            expenses.append(
                ProfitLossRow(
                    account_id=acct_id, account_code=code,
                    account_name=name, amount=amt,
                )
            )
            total_expenses += amt

    return ProfitLossResponse(
        start_date=start,
        end_date=end,
        department_id=department_id,
        income=income,
        total_income=_q(total_income),
        expenses=expenses,
        total_expenses=_q(total_expenses),
        net_profit=_q(total_income - total_expenses),
    )


# ── Balance Sheet ────────────────────────────────────────────────────────────


async def get_balance_sheet(
    db: AsyncSession,
    facility_id: uuid.UUID,
    as_of_date: date_type,
) -> BalanceSheetResponse:
    """
    Compute Balance Sheet as of a given date.
    Asset balance = DR - CR. Liability/Equity balance = CR - DR.

    @param db: Database session
    @param facility_id: Facility scope
    @param as_of_date: Snapshot date
    @returns Assets, liabilities, equity sections + balance check
    """
    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(TransactionEntry.debit), 0).label("dr"),
            func.coalesce(func.sum(TransactionEntry.credit), 0).label("cr"),
        )
        .join(
            TransactionEntry,
            (TransactionEntry.account_id == Account.id)
            & (TransactionEntry.facility_id == facility_id),
            isouter=True,
        )
        .join(
            Transaction,
            and_(
                TransactionEntry.transaction_id == Transaction.id,
                Transaction.facility_id == facility_id,
                Transaction.date <= as_of_date,
            ),
            isouter=True,
        )
        .where(
            Account.facility_id == facility_id,
            Account.is_deleted == False,  # noqa: E712
            Account.type.in_(["asset", "liability", "equity"]),
        )
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code.asc())
    )

    result = await db.execute(stmt)

    asset_rows: list[ProfitLossRow] = []
    liability_rows: list[ProfitLossRow] = []
    equity_rows: list[ProfitLossRow] = []
    total_assets = _ZERO
    total_liab = _ZERO
    total_eq = _ZERO

    for acct_id, code, name, atype, dr, cr in result.all():
        dr_d = Decimal(dr)
        cr_d = Decimal(cr)
        if atype == "asset":
            amt = _q(dr_d - cr_d)
            asset_rows.append(
                ProfitLossRow(account_id=acct_id, account_code=code,
                              account_name=name, amount=amt)
            )
            total_assets += amt
        elif atype == "liability":
            amt = _q(cr_d - dr_d)
            liability_rows.append(
                ProfitLossRow(account_id=acct_id, account_code=code,
                              account_name=name, amount=amt)
            )
            total_liab += amt
        else:  # equity
            amt = _q(cr_d - dr_d)
            equity_rows.append(
                ProfitLossRow(account_id=acct_id, account_code=code,
                              account_name=name, amount=amt)
            )
            total_eq += amt

    # Add net profit YTD into equity (retained earnings approximation)
    pl = await get_profit_loss(
        db,
        facility_id,
        date_type(as_of_date.year, 1, 1),
        as_of_date,
    )
    total_eq += pl.net_profit

    return BalanceSheetResponse(
        as_of_date=as_of_date,
        assets=BalanceSheetSection(rows=asset_rows, total=_q(total_assets)),
        liabilities=BalanceSheetSection(rows=liability_rows, total=_q(total_liab)),
        equity=BalanceSheetSection(rows=equity_rows, total=_q(total_eq)),
        is_balanced=_q(total_assets) == _q(total_liab + total_eq),
    )


# ── Cash Flow ────────────────────────────────────────────────────────────────


async def get_cash_flow(
    db: AsyncSession,
    facility_id: uuid.UUID,
    start: date_type,
    end: date_type,
    method: str = "direct",
) -> CashFlowResponse:
    """
    Cash flow statement (direct method by default).
    Sums entries on cash accounts grouped by counterparty cashflow_category.

    @param db: Database session
    @param facility_id: Facility scope
    @param start: Start date
    @param end: End date
    @param method: 'direct' or 'indirect'
    @returns Operating/investing/financing breakdown + reconciliation
    """
    cash_accounts_result = await db.execute(
        select(Account.id).where(
            Account.facility_id == facility_id,
            Account.is_deleted == False,  # noqa: E712
            Account.type == "asset",
            Account.code.in_(["1010", "1020"]),  # Cash, Bank
        )
    )
    cash_account_ids = [row[0] for row in cash_accounts_result.all()]

    # Opening cash
    opening_result = await db.execute(
        select(
            func.coalesce(func.sum(TransactionEntry.debit), 0)
            - func.coalesce(func.sum(TransactionEntry.credit), 0)
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id.in_(cash_account_ids),
            Transaction.date < start,
        )
    )
    opening_cash = _q(Decimal(opening_result.scalar() or 0))

    # For each transaction touching cash, find the counterparty entry's
    # account.cashflow_category to bucket the inflow/outflow.
    stmt = (
        select(
            Account.cashflow_category,
            Account.id,
            Account.code,
            Account.name,
            func.coalesce(
                func.sum(TransactionEntry.credit) - func.sum(TransactionEntry.debit),
                0,
            ).label("net_for_counterparty"),
        )
        .join(TransactionEntry, TransactionEntry.account_id == Account.id)
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            Account.facility_id == facility_id,
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            Account.is_deleted == False,  # noqa: E712
            Transaction.date >= start,
            Transaction.date <= end,
            Account.id.notin_(cash_account_ids) if cash_account_ids else sa_true(),
            Transaction.id.in_(
                select(Transaction.id)
                .join(
                    TransactionEntry,
                    TransactionEntry.transaction_id == Transaction.id,
                )
                .where(
                    Transaction.facility_id == facility_id,
                    TransactionEntry.facility_id == facility_id,
                    TransactionEntry.account_id.in_(cash_account_ids)
                    if cash_account_ids
                    else sa_false(),
                )
            ),
        )
        .group_by(Account.cashflow_category, Account.id, Account.code, Account.name)
    )

    result = await db.execute(stmt)

    operating_rows: list[ProfitLossRow] = []
    investing_rows: list[ProfitLossRow] = []
    financing_rows: list[ProfitLossRow] = []
    op_total = inv_total = fin_total = _ZERO

    for cat, acct_id, code, name, net in result.all():
        amt = _q(Decimal(net))
        row = ProfitLossRow(
            account_id=acct_id, account_code=code, account_name=name, amount=amt
        )
        if cat == "operating":
            operating_rows.append(row)
            op_total += amt
        elif cat == "investing":
            investing_rows.append(row)
            inv_total += amt
        elif cat == "financing":
            financing_rows.append(row)
            fin_total += amt

    net_change = _q(op_total + inv_total + fin_total)
    closing_cash = _q(opening_cash + net_change)

    return CashFlowResponse(
        start_date=start,
        end_date=end,
        method=method,
        operating=CashFlowSection(rows=operating_rows, total=_q(op_total)),
        investing=CashFlowSection(rows=investing_rows, total=_q(inv_total)),
        financing=CashFlowSection(rows=financing_rows, total=_q(fin_total)),
        net_change_in_cash=net_change,
        opening_cash=opening_cash,
        closing_cash=closing_cash,
    )


# ── AR Aging ─────────────────────────────────────────────────────────────────


async def get_ar_aging(
    db: AsyncSession,
    facility_id: uuid.UUID,
    as_of_date: date_type,
) -> ARAgingResponse:
    """
    Accounts receivable aging.
    Buckets by days overdue against ``due_date``: current/30/60/90/120+.

    @param db: Database session
    @param facility_id: Facility scope
    @param as_of_date: Reference date for ageing
    @returns Aged AR per insurer
    """
    result = await db.execute(
        select(InsuranceClaimFinance).where(
            InsuranceClaimFinance.facility_id == facility_id,
            InsuranceClaimFinance.is_deleted == False,  # noqa: E712
            InsuranceClaimFinance.status.in_(["submitted", "approved", "partial"]),
        )
    )
    claims = list(result.scalars().all())

    by_insurer: dict[uuid.UUID, ARAgingRow] = {}
    totals = [_ZERO, _ZERO, _ZERO, _ZERO, _ZERO]

    for claim in claims:
        outstanding = _q(claim.amount_claimed - claim.amount_paid)
        if outstanding <= 0:
            continue
        days_outstanding = (
            (as_of_date - claim.due_date).days if claim.due_date else 0
        )
        if days_outstanding <= 0:
            bucket = 0
        elif days_outstanding <= 30:
            bucket = 1
        elif days_outstanding <= 60:
            bucket = 2
        elif days_outstanding <= 90:
            bucket = 3
        else:
            bucket = 4

        row = by_insurer.setdefault(
            claim.insurer_id,
            ARAgingRow(
                insurer_id=claim.insurer_id,
                party_name=str(claim.insurer_id),
                current=_ZERO,
                bucket_30=_ZERO,
                bucket_60=_ZERO,
                bucket_90=_ZERO,
                bucket_120_plus=_ZERO,
                total=_ZERO,
            ),
        )
        if bucket == 0:
            row.current += outstanding
        elif bucket == 1:
            row.bucket_30 += outstanding
        elif bucket == 2:
            row.bucket_60 += outstanding
        elif bucket == 3:
            row.bucket_90 += outstanding
        else:
            row.bucket_120_plus += outstanding
        row.total += outstanding
        totals[bucket] += outstanding

    rows = [
        ARAgingRow(
            insurer_id=r.insurer_id,
            party_name=r.party_name,
            current=_q(r.current),
            bucket_30=_q(r.bucket_30),
            bucket_60=_q(r.bucket_60),
            bucket_90=_q(r.bucket_90),
            bucket_120_plus=_q(r.bucket_120_plus),
            total=_q(r.total),
        )
        for r in by_insurer.values()
    ]
    grand = sum(totals, start=_ZERO)
    return ARAgingResponse(
        as_of_date=as_of_date,
        rows=rows,
        total_current=_q(totals[0]),
        total_30=_q(totals[1]),
        total_60=_q(totals[2]),
        total_90=_q(totals[3]),
        total_120_plus=_q(totals[4]),
        grand_total=_q(grand),
    )


# ── Budget vs Actual ─────────────────────────────────────────────────────────


async def get_budget_vs_actual(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
) -> BudgetVsActualResponse:
    """
    Compare budgeted amounts to actual postings within the period.

    @param db: Database session
    @param facility_id: Facility scope
    @param period_id: Period to evaluate
    @returns Per-account variance + percent used
    """
    period_result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.facility_id == facility_id,
        )
    )
    period = period_result.scalar_one()

    budgets_result = await db.execute(
        select(Budget, Account)
        .join(Account, Account.id == Budget.account_id)
        .where(
            Budget.facility_id == facility_id,
            Budget.period_id == period_id,
            Budget.is_deleted == False,  # noqa: E712
        )
    )
    rows: list[BudgetVsActualRow] = []
    for budget, account in budgets_result.all():
        # Compute actual: for expenses use net debit; for income use net credit
        actual_result = await db.execute(
            select(
                func.coalesce(func.sum(TransactionEntry.debit), 0),
                func.coalesce(func.sum(TransactionEntry.credit), 0),
            )
            .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
            .where(
                TransactionEntry.facility_id == facility_id,
                Transaction.facility_id == facility_id,
                TransactionEntry.account_id == account.id,
                Transaction.date >= period.start_date,
                Transaction.date <= period.end_date,
            )
        )
        dr, cr = actual_result.first() or (0, 0)
        if account.type == "expense":
            actual = _q(Decimal(dr) - Decimal(cr))
        else:
            actual = _q(Decimal(cr) - Decimal(dr))

        budgeted = _q(budget.budgeted_amount)
        variance = _q(budgeted - actual)
        pct_used = (
            _q((actual / budgeted) * Decimal("100"))
            if budgeted > 0
            else _ZERO
        )
        rows.append(
            BudgetVsActualRow(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                department_id=budget.department_id,
                budgeted=budgeted,
                actual=actual,
                variance=variance,
                pct_used=pct_used,
            )
        )

    return BudgetVsActualResponse(period_id=period_id, rows=rows)


# Re-export helper for opening balance lookups
async def get_account_opening_balance(
    db: AsyncSession,
    facility_id: uuid.UUID,
    account_id: uuid.UUID,
    period_id: uuid.UUID,
) -> Decimal:
    """
    Look up the opening balance entered for an account in a period.

    @returns DR - CR opening balance, or 0 if not entered.
    """
    result = await db.execute(
        select(OpeningBalance).where(
            OpeningBalance.facility_id == facility_id,
            OpeningBalance.account_id == account_id,
            OpeningBalance.period_id == period_id,
            OpeningBalance.is_deleted == False,  # noqa: E712
        )
    )
    ob = result.scalar_one_or_none()
    if ob is None:
        return _ZERO
    return _q(ob.debit_balance - ob.credit_balance)
