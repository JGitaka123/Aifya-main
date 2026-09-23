"""
Hospital Finance Module v2.0 — REST router.

All endpoints are mounted under ``/api/v1/finance/`` and gated by the
``finance`` license module.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.models.finance import (
    Account,
    AccountingPeriod,
    BankStatement,
    Budget,
    FixedAsset,
    OpeningBalance,
    RecurringTemplate,
    TaxRate,
    Transaction,
    TransactionEntry,
)
from app.schemas.finance import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
    ARAgingResponse,
    BalanceSheetResponse,
    BankStatementImport,
    BankStatementResponse,
    BudgetCreate,
    BudgetResponse,
    BudgetVsActualResponse,
    CashFlowResponse,
    DepreciationRunResponse,
    FixedAssetCreate,
    FixedAssetResponse,
    GeneralLedgerResponse,
    ManualJournalCreate,
    ManualMatchRequest,
    OpeningBalanceCreate,
    OpeningBalanceResponse,
    PeriodCloseRequest,
    PeriodCreate,
    PeriodResponse,
    PostTransactionRequest,
    ProfitLossResponse,
    ReconciliationResponse,
    RecurringTemplateCreate,
    RecurringTemplateResponse,
    TaxRateCreate,
    TaxRateResponse,
    TransactionDetail,
    TransactionEntryResponse,
    TransactionListResponse,
    TransactionResponse,
    TrialBalanceResponse,
)
from app.services.finance import (
    FinanceError,
    PeriodLockedError,
    PostingRuleNotFoundError,
    UnbalancedTransactionError,
    post_compound_transaction,
    post_transaction,
    reverse_transaction,
)
from app.services.finance.depreciation import post_monthly_depreciation
from app.services.finance.periods import (
    close_period,
    create_period,
    run_year_end_close,
)
from app.services.finance.reconciliation import (
    auto_match,
    get_reconciliation_report,
    import_bank_statement,
    manual_match,
)
from app.services.finance.recurring import (
    post_recurring_now,
    process_due_recurring,
)
from app.services.finance.reports import (
    get_ar_aging,
    get_balance_sheet,
    get_budget_vs_actual,
    get_cash_flow,
    get_general_ledger,
    get_profit_loss,
    get_trial_balance,
)

router = APIRouter(dependencies=[Depends(require_module("finance"))])


_FINANCE_ROLES = ("finance_admin", "facility_admin", "admin")


# ── Chart of Accounts ────────────────────────────────────────────────────────


@router.get("/accounts", response_model=AccountListResponse)
async def list_accounts(
    type_filter: str | None = Query(None, alias="type"),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountListResponse:
    """
    List the facility's chart of accounts.

    @param type_filter: Optional account type filter
    @param is_active: Optional active filter
    @param db: Database session
    @param current_user: Authenticated user
    @returns Account list
    """
    stmt = select(Account).where(
        Account.facility_id == current_user.facility_id,
        Account.is_deleted == False,  # noqa: E712
    )
    if type_filter:
        stmt = stmt.where(Account.type == type_filter)
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)
    stmt = stmt.order_by(Account.code.asc())
    result = await db.execute(stmt)
    accounts = list(result.scalars().all())
    return AccountListResponse(
        items=[AccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> AccountResponse:
    """
    Create a new chart-of-accounts entry.

    @param data: Account data
    @param db: Database session
    @param current_user: Authenticated finance admin
    @returns Created account
    """
    account = Account(
        facility_id=current_user.facility_id,
        code=data.code,
        name=data.name,
        type=data.type,
        cashflow_category=data.cashflow_category,
        parent_id=data.parent_id,
        description=data.description,
        is_system=False,
        is_active=True,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountResponse:
    """
    Fetch a single account from the facility's chart of accounts.

    @param account_id: Account UUID
    @param db: Database session
    @param current_user: Authenticated user
    @returns The requested account
    """
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.facility_id == current_user.facility_id,
            Account.is_deleted == False,  # noqa: E712
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return AccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> AccountResponse:
    """
    Update editable account metadata. Type and code are NEVER editable
    if entries already exist on the account.

    @param account_id: Account UUID
    @param data: Mutable fields
    @param db: Database session
    @param current_user: Authenticated finance admin
    @returns Updated account
    """
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.facility_id == current_user.facility_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")

    if data.name is not None:
        account.name = data.name
    if data.cashflow_category is not None:
        account.cashflow_category = data.cashflow_category
    if data.parent_id is not None:
        account.parent_id = data.parent_id
    if data.description is not None:
        account.description = data.description
    if data.is_active is not None:
        account.is_active = data.is_active
    account.updated_by = current_user.user_id

    await db.flush()
    await db.refresh(account)
    return AccountResponse.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> None:
    """
    Soft-delete an account. Forbidden if any transaction entries reference it.

    @param account_id: Account UUID
    @param db: Database session
    @param current_user: Authenticated finance admin
    """
    has_entries = await db.execute(
        select(func.count(TransactionEntry.id)).where(
            TransactionEntry.account_id == account_id,
            TransactionEntry.facility_id == current_user.facility_id,
        )
    )
    if (has_entries.scalar() or 0) > 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Account has ledger entries — cannot delete",
        )

    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.facility_id == current_user.facility_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    account.is_deleted = True
    account.is_active = False
    account.updated_by = current_user.user_id
    await db.flush()


# ── Transactions ─────────────────────────────────────────────────────────────


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_transaction(
    data: PostTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
    x_idempotency_key: str | None = Header(None),
) -> TransactionResponse:
    """
    Manually post a transaction through the GL engine.

    @param data: Posting request (event_type + amount + metadata)
    @param db: Database session
    @param current_user: Authenticated finance admin
    @param x_idempotency_key: Idempotency key
    @returns Posted transaction
    """
    try:
        txn = await post_transaction(
            db=db,
            facility_id=current_user.facility_id,
            event_type=data.event_type,
            amount=data.amount,
            metadata=data.metadata.model_dump(mode="json"),
            idempotency_key=x_idempotency_key,
            user_id=current_user.user_id,
        )
    except PeriodLockedError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except PostingRuleNotFoundError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except UnbalancedTransactionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TransactionResponse.model_validate(txn)


@router.post(
    "/transactions/manual",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_journal(
    data: ManualJournalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
    x_idempotency_key: str | None = Header(None),
) -> TransactionResponse:
    """
    Post a manually keyed double-entry journal (explicit debit/credit lines).

    Lines are supplied as account ids; the GL engine still enforces
    SUM(debit) == SUM(credit), open-period checks, idempotency and atomicity.

    @param data: Journal header plus balanced entry lines
    @param db: Database session
    @param current_user: Authenticated finance admin
    @param x_idempotency_key: Idempotency key
    @returns The posted transaction
    """
    account_ids = {entry.account_id for entry in data.entries}
    result = await db.execute(
        select(Account).where(
            Account.id.in_(account_ids),
            Account.facility_id == current_user.facility_id,
            Account.is_deleted == False,  # noqa: E712
        )
    )
    id_to_code = {a.id: a.code for a in result.scalars().all()}
    missing = account_ids - set(id_to_code)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown account(s): {sorted(str(m) for m in missing)}",
        )

    entries = [
        {
            "account_code": id_to_code[entry.account_id],
            "debit": entry.debit,
            "credit": entry.credit,
        }
        for entry in data.entries
    ]
    try:
        txn = await post_compound_transaction(
            db=db,
            facility_id=current_user.facility_id,
            entries=entries,
            metadata={
                "date": data.date,
                "reference_type": data.reference_type or "manual",
                "description": data.description,
                "department_id": data.department_id,
                "event_type": "manual_journal",
            },
            idempotency_key=x_idempotency_key,
            user_id=current_user.user_id,
        )
    except PeriodLockedError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except UnbalancedTransactionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except FinanceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TransactionResponse.model_validate(txn)


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    start_date: date_type | None = Query(None),
    end_date: date_type | None = Query(None),
    event_type: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionListResponse:
    """
    List transactions with optional filters.

    @returns Paginated list
    """
    base = select(Transaction).where(
        Transaction.facility_id == current_user.facility_id
    )
    if start_date:
        base = base.where(Transaction.date >= start_date)
    if end_date:
        base = base.where(Transaction.date <= end_date)
    if event_type:
        base = base.where(Transaction.event_type == event_type)
    if department_id:
        base = base.where(Transaction.department_id == department_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        base.order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [
        TransactionResponse.model_validate(t)
        for t in result.scalars().all()
    ]
    return TransactionListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionDetail)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionDetail:
    """Return a transaction with its ledger entries."""
    txn_result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.facility_id == current_user.facility_id,
        )
    )
    txn = txn_result.scalar_one_or_none()
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")

    entries_result = await db.execute(
        select(TransactionEntry).where(
            TransactionEntry.transaction_id == txn.id,
            TransactionEntry.facility_id == current_user.facility_id,
        )
    )
    entries = list(entries_result.scalars().all())
    return TransactionDetail(
        transaction=TransactionResponse.model_validate(txn),
        entries=[TransactionEntryResponse.model_validate(e) for e in entries],
    )


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reverse_a_transaction(
    transaction_id: uuid.UUID,
    posting_date: date_type = Query(..., description="Reversal posting date"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> TransactionResponse:
    """Post a reversing transaction for the given original transaction."""
    try:
        rev = await reverse_transaction(
            db=db,
            facility_id=current_user.facility_id,
            transaction_id=transaction_id,
            posting_date=posting_date,
            user_id=current_user.user_id,
        )
    except (PeriodLockedError, UnbalancedTransactionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TransactionResponse.model_validate(rev)


# ── Reports ──────────────────────────────────────────────────────────────────


@router.get("/reports/general-ledger", response_model=GeneralLedgerResponse)
async def report_general_ledger(
    account_id: uuid.UUID = Query(...),
    start: date_type = Query(...),
    end: date_type = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> GeneralLedgerResponse:
    """General ledger for one account."""
    return await get_general_ledger(
        db, current_user.facility_id, account_id, start, end
    )


@router.get("/reports/trial-balance", response_model=TrialBalanceResponse)
async def report_trial_balance(
    period_id: uuid.UUID | None = Query(None),
    as_of: date_type | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TrialBalanceResponse:
    """Trial balance — debits should equal credits."""
    return await get_trial_balance(
        db, current_user.facility_id, period_id, as_of
    )


@router.get("/reports/profit-loss", response_model=ProfitLossResponse)
async def report_profit_loss(
    start: date_type = Query(...),
    end: date_type = Query(...),
    department_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ProfitLossResponse:
    """P&L for the date range."""
    return await get_profit_loss(
        db, current_user.facility_id, start, end, department_id
    )


@router.get("/reports/balance-sheet", response_model=BalanceSheetResponse)
async def report_balance_sheet(
    as_of_date: date_type = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BalanceSheetResponse:
    """Balance sheet snapshot."""
    return await get_balance_sheet(db, current_user.facility_id, as_of_date)


@router.get("/reports/cash-flow", response_model=CashFlowResponse)
async def report_cash_flow(
    start: date_type = Query(...),
    end: date_type = Query(...),
    method: str = Query("direct", pattern=r"^(direct|indirect)$"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CashFlowResponse:
    """Cash flow statement."""
    return await get_cash_flow(
        db, current_user.facility_id, start, end, method
    )


@router.get("/reports/ar-aging", response_model=ARAgingResponse)
async def report_ar_aging(
    as_of_date: date_type = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ARAgingResponse:
    """AR aging buckets."""
    return await get_ar_aging(db, current_user.facility_id, as_of_date)


@router.get(
    "/reports/budget-vs-actual", response_model=BudgetVsActualResponse
)
async def report_budget_vs_actual(
    period_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BudgetVsActualResponse:
    """Budget vs actual variance report."""
    return await get_budget_vs_actual(db, current_user.facility_id, period_id)


# ── Periods ──────────────────────────────────────────────────────────────────


@router.get("/periods", response_model=list[PeriodResponse])
async def list_periods(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PeriodResponse]:
    """List accounting periods."""
    result = await db.execute(
        select(AccountingPeriod)
        .where(
            AccountingPeriod.facility_id == current_user.facility_id,
            AccountingPeriod.is_deleted == False,  # noqa: E712
        )
        .order_by(AccountingPeriod.start_date.desc())
    )
    return [
        PeriodResponse.model_validate(p) for p in result.scalars().all()
    ]


@router.post(
    "/periods",
    response_model=PeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_a_period(
    data: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> PeriodResponse:
    """Create a new accounting period."""
    period = await create_period(
        db,
        facility_id=current_user.facility_id,
        name=data.name,
        start=data.start_date,
        end=data.end_date,
        year_end=data.year_end,
        user_id=current_user.user_id,
    )
    return PeriodResponse.model_validate(period)


@router.post("/periods/{period_id}/close", response_model=PeriodResponse)
async def close_a_period(
    period_id: uuid.UUID,
    data: PeriodCloseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> PeriodResponse:
    """Close (not lock) a period."""
    _ = data
    try:
        period = await close_period(
            db, current_user.facility_id, period_id, current_user.user_id
        )
    except PeriodLockedError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return PeriodResponse.model_validate(period)


@router.post(
    "/periods/{period_id}/year-end-close", response_model=PeriodResponse
)
async def year_end_close(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> PeriodResponse:
    """Sweep income/expense to retained earnings and lock the period."""
    try:
        await run_year_end_close(
            db, current_user.facility_id, period_id, current_user.user_id
        )
    except (PeriodLockedError, UnbalancedTransactionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    result = await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id)
    )
    period = result.scalar_one()
    return PeriodResponse.model_validate(period)


# ── Opening Balances ─────────────────────────────────────────────────────────


@router.post(
    "/opening-balances",
    response_model=OpeningBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_opening_balance(
    data: OpeningBalanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> OpeningBalanceResponse:
    """Record an opening balance for an account in a period."""
    if data.debit_balance > 0 and data.credit_balance > 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Opening balance must be a debit XOR credit, not both",
        )
    ob = OpeningBalance(
        facility_id=current_user.facility_id,
        account_id=data.account_id,
        period_id=data.period_id,
        debit_balance=data.debit_balance,
        credit_balance=data.credit_balance,
        entered_by=current_user.user_id,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(ob)
    await db.flush()
    await db.refresh(ob)
    return OpeningBalanceResponse.model_validate(ob)


# ── Bank Reconciliation ──────────────────────────────────────────────────────


@router.post(
    "/bank-statements/import",
    response_model=list[BankStatementResponse],
    status_code=status.HTTP_201_CREATED,
)
async def import_statements(
    data: BankStatementImport,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> list[BankStatementResponse]:
    """Bulk-import a bank statement."""
    rows = await import_bank_statement(
        db,
        facility_id=current_user.facility_id,
        account_id=data.account_id,
        statement_date=data.statement_date,
        rows=data.rows,
        user_id=current_user.user_id,
    )
    return [BankStatementResponse.model_validate(r) for r in rows]


@router.get("/bank-statements", response_model=list[BankStatementResponse])
async def list_bank_statements(
    account_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BankStatementResponse]:
    """List bank statement rows."""
    stmt = select(BankStatement).where(
        BankStatement.facility_id == current_user.facility_id,
        BankStatement.is_deleted == False,  # noqa: E712
    )
    if account_id:
        stmt = stmt.where(BankStatement.account_id == account_id)
    if status_filter:
        stmt = stmt.where(BankStatement.status == status_filter)
    stmt = stmt.order_by(BankStatement.transaction_date.desc())
    result = await db.execute(stmt)
    return [
        BankStatementResponse.model_validate(s) for s in result.scalars().all()
    ]


@router.post(
    "/bank-statements/{statement_id}/match",
    response_model=BankStatementResponse,
)
async def match_statement(
    statement_id: uuid.UUID,
    data: ManualMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> BankStatementResponse:
    """Manually match a statement row to a GL entry."""
    stmt = await manual_match(
        db,
        facility_id=current_user.facility_id,
        statement_id=statement_id,
        entry_id=data.entry_id,
        user_id=current_user.user_id,
    )
    return BankStatementResponse.model_validate(stmt)


@router.post(
    "/bank-statements/auto-match",
    response_model=dict[str, int],
)
async def auto_match_statements(
    account_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> dict[str, int]:
    """Auto-match unmatched statements against GL cash entries."""
    return await auto_match(
        db, current_user.facility_id, account_id, current_user.user_id
    )


@router.get(
    "/reconciliation/{account_id}", response_model=ReconciliationResponse
)
async def reconciliation_report(
    account_id: uuid.UUID,
    period_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReconciliationResponse:
    """Reconciliation summary for a cash account."""
    return await get_reconciliation_report(
        db, current_user.facility_id, account_id, period_id
    )


# ── Fixed Assets ─────────────────────────────────────────────────────────────


@router.get("/fixed-assets", response_model=list[FixedAssetResponse])
async def list_fixed_assets(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[FixedAssetResponse]:
    """List fixed assets."""
    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.facility_id == current_user.facility_id,
            FixedAsset.is_deleted == False,  # noqa: E712
        )
    )
    return [
        FixedAssetResponse.model_validate(a) for a in result.scalars().all()
    ]


@router.post(
    "/fixed-assets",
    response_model=FixedAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fixed_asset(
    data: FixedAssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> FixedAssetResponse:
    """Register a fixed asset."""
    asset = FixedAsset(
        facility_id=current_user.facility_id,
        name=data.name,
        asset_tag=data.asset_tag,
        account_id=data.account_id,
        accumulated_depreciation_account_id=data.accumulated_depreciation_account_id,
        depreciation_expense_account_id=data.depreciation_expense_account_id,
        purchase_date=data.purchase_date,
        purchase_cost=data.purchase_cost,
        useful_life_months=data.useful_life_months,
        salvage_value=data.salvage_value,
        depreciation_method=data.depreciation_method,
        accumulated_depreciation=Decimal("0"),
        is_active=True,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    return FixedAssetResponse.model_validate(asset)


@router.post(
    "/depreciation/run", response_model=DepreciationRunResponse
)
async def run_depreciation(
    period_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> DepreciationRunResponse:
    """Run monthly depreciation for all active assets."""
    summary = await post_monthly_depreciation(
        db,
        facility_id=current_user.facility_id,
        period_id=period_id,
        user_id=current_user.user_id,
    )
    return DepreciationRunResponse(**summary)


# ── Tax ──────────────────────────────────────────────────────────────────────


@router.get("/tax-rates", response_model=list[TaxRateResponse])
async def list_tax_rates(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TaxRateResponse]:
    """List tax rates."""
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.facility_id == current_user.facility_id,
            TaxRate.is_deleted == False,  # noqa: E712
        )
    )
    return [
        TaxRateResponse.model_validate(t) for t in result.scalars().all()
    ]


@router.post(
    "/tax-rates",
    response_model=TaxRateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tax_rate(
    data: TaxRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> TaxRateResponse:
    """Create a tax rate."""
    rate = TaxRate(
        facility_id=current_user.facility_id,
        name=data.name,
        rate=data.rate,
        tax_type=data.tax_type,
        account_id=data.account_id,
        is_active=True,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return TaxRateResponse.model_validate(rate)


# ── Budgets ──────────────────────────────────────────────────────────────────


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    period_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BudgetResponse]:
    """List budgets."""
    stmt = select(Budget).where(
        Budget.facility_id == current_user.facility_id,
        Budget.is_deleted == False,  # noqa: E712
    )
    if period_id:
        stmt = stmt.where(Budget.period_id == period_id)
    result = await db.execute(stmt)
    return [BudgetResponse.model_validate(b) for b in result.scalars().all()]


@router.post(
    "/budgets",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget(
    data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> BudgetResponse:
    """Create a budget line."""
    budget = Budget(
        facility_id=current_user.facility_id,
        account_id=data.account_id,
        department_id=data.department_id,
        period_id=data.period_id,
        budgeted_amount=data.budgeted_amount,
        notes=data.notes,
        approved_by=current_user.user_id,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(budget)
    await db.flush()
    await db.refresh(budget)
    return BudgetResponse.model_validate(budget)


# ── Recurring ────────────────────────────────────────────────────────────────


@router.get("/recurring", response_model=list[RecurringTemplateResponse])
async def list_recurring(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RecurringTemplateResponse]:
    """List recurring transaction templates."""
    result = await db.execute(
        select(RecurringTemplate).where(
            RecurringTemplate.facility_id == current_user.facility_id,
            RecurringTemplate.is_deleted == False,  # noqa: E712
        )
    )
    return [
        RecurringTemplateResponse.model_validate(t)
        for t in result.scalars().all()
    ]


@router.post(
    "/recurring",
    response_model=RecurringTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring(
    data: RecurringTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> RecurringTemplateResponse:
    """Create a recurring transaction template."""
    tpl = RecurringTemplate(
        facility_id=current_user.facility_id,
        name=data.name,
        event_type=data.event_type,
        amount=data.amount,
        account_debit_id=data.account_debit_id,
        account_credit_id=data.account_credit_id,
        department_id=data.department_id,
        frequency=data.frequency,
        next_post_date=data.next_post_date,
        requires_approval=data.requires_approval,
        is_active=True,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(tpl)
    await db.flush()
    await db.refresh(tpl)
    return RecurringTemplateResponse.model_validate(tpl)


@router.post(
    "/recurring/{template_id}/post-now", response_model=TransactionResponse
)
async def post_recurring_template_now(
    template_id: uuid.UUID,
    posting_date: date_type | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> TransactionResponse:
    """Force-post a recurring template now."""
    try:
        txn = await post_recurring_now(
            db,
            facility_id=current_user.facility_id,
            template_id=template_id,
            user_id=current_user.user_id,
            posting_date=posting_date,
        )
    except (PeriodLockedError, UnbalancedTransactionError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return TransactionResponse.model_validate(txn)


@router.post(
    "/recurring/process-due",
    response_model=list[TransactionResponse],
)
async def trigger_recurring_processing(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FINANCE_ROLES)),
) -> list[TransactionResponse]:
    """Process all due recurring templates that don't require approval."""
    posted = await process_due_recurring(
        db, facility_id=current_user.facility_id, user_id=current_user.user_id
    )
    return [TransactionResponse.model_validate(t) for t in posted]
