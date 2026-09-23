"""
Pydantic schemas for the Hospital Finance Module v2.0.

All money values are ``Decimal`` (DECIMAL(14,2) in the GL ledger).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# ── Chart of Accounts ────────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    """Schema for creating a new account."""

    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern=r"^(asset|liability|equity|income|expense)$")
    cashflow_category: str = Field(
        default="none", pattern=r"^(operating|investing|financing|none)$"
    )
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=2000)


class AccountUpdate(BaseModel):
    """Schema for editing account metadata. Type/code never editable if entries exist."""

    name: str | None = Field(None, min_length=1, max_length=200)
    cashflow_category: str | None = Field(
        None, pattern=r"^(operating|investing|financing|none)$"
    )
    parent_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


class AccountResponse(BaseModel):
    """Account API response."""

    id: uuid.UUID
    code: str
    name: str
    type: str
    cashflow_category: str
    parent_id: uuid.UUID | None
    is_system: bool
    is_active: bool
    description: str | None

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    """Paginated chart of accounts list."""

    items: list[AccountResponse]
    total: int


# ── Transactions ─────────────────────────────────────────────────────────────


class TransactionEntryResponse(BaseModel):
    """Ledger entry response."""

    id: uuid.UUID
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    department_id: uuid.UUID | None
    currency: str
    exchange_rate: Decimal

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    """Transaction header response."""

    id: uuid.UUID
    date: date
    reference_type: str | None
    reference_id: uuid.UUID | None
    event_type: str
    description: str | None
    department_id: uuid.UUID | None
    period_id: uuid.UUID
    amount: Decimal
    is_reversal: bool
    reverses_transaction_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionDetail(BaseModel):
    """Transaction with all entries."""

    transaction: TransactionResponse
    entries: list[TransactionEntryResponse]


class TransactionMetadata(BaseModel):
    """Metadata for a posting request."""

    date: date
    reference_type: str | None = Field(None, max_length=50)
    reference_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=2000)
    department_id: uuid.UUID | None = None


class PostTransactionRequest(BaseModel):
    """Manual posting request for finance admins."""

    event_type: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=Decimal("0"))
    metadata: TransactionMetadata


class ManualJournalEntry(BaseModel):
    """One line of a manually keyed journal entry."""

    account_id: uuid.UUID
    debit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))


class ManualJournalCreate(BaseModel):
    """Manually keyed double-entry journal (explicit debit/credit lines)."""

    date: date
    description: str = Field(..., min_length=1, max_length=2000)
    reference_type: str | None = Field(None, max_length=50)
    department_id: uuid.UUID | None = None
    entries: list[ManualJournalEntry] = Field(..., min_length=2)


class TransactionListResponse(BaseModel):
    """Paginated transaction list."""

    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int


# ── Periods ──────────────────────────────────────────────────────────────────


class PeriodCreate(BaseModel):
    """Schema for creating an accounting period."""

    name: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    year_end: bool = False


class PeriodResponse(BaseModel):
    """Accounting period response."""

    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str
    closed_by: uuid.UUID | None
    closed_at: datetime | None
    year_end: bool

    model_config = {"from_attributes": True}


class PeriodCloseRequest(BaseModel):
    """Schema for closing a period."""

    notes: str | None = Field(None, max_length=2000)


# ── Reports ──────────────────────────────────────────────────────────────────


class GeneralLedgerEntry(BaseModel):
    """Single GL entry row with running balance."""

    transaction_id: uuid.UUID
    date: date
    description: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class GeneralLedgerResponse(BaseModel):
    """General ledger report for a single account."""

    account_id: uuid.UUID
    account_code: str
    account_name: str
    opening_balance: Decimal
    entries: list[GeneralLedgerEntry]
    closing_balance: Decimal


class TrialBalanceRow(BaseModel):
    """One row of a trial balance."""

    account_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: str
    debit_total: Decimal
    credit_total: Decimal


class TrialBalanceResponse(BaseModel):
    """Trial balance — sums must equal."""

    period_id: uuid.UUID | None
    as_of: date
    rows: list[TrialBalanceRow]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool


class ProfitLossRow(BaseModel):
    """P&L row."""

    account_id: uuid.UUID
    account_code: str
    account_name: str
    amount: Decimal


class ProfitLossResponse(BaseModel):
    """Profit & Loss / Income Statement."""

    start_date: date
    end_date: date
    department_id: uuid.UUID | None
    income: list[ProfitLossRow]
    total_income: Decimal
    expenses: list[ProfitLossRow]
    total_expenses: Decimal
    net_profit: Decimal


class BalanceSheetSection(BaseModel):
    """Balance sheet section (assets/liabilities/equity)."""

    rows: list[ProfitLossRow]
    total: Decimal


class BalanceSheetResponse(BaseModel):
    """Balance Sheet — Assets = Liabilities + Equity."""

    as_of_date: date
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    is_balanced: bool


class CashFlowSection(BaseModel):
    """Cash flow categorisation."""

    rows: list[ProfitLossRow]
    total: Decimal


class CashFlowResponse(BaseModel):
    """Cash flow statement (direct or indirect)."""

    start_date: date
    end_date: date
    method: str
    operating: CashFlowSection
    investing: CashFlowSection
    financing: CashFlowSection
    net_change_in_cash: Decimal
    opening_cash: Decimal
    closing_cash: Decimal


class ARAgingRow(BaseModel):
    """One row of AR aging."""

    patient_id: uuid.UUID | None = None
    insurer_id: uuid.UUID | None = None
    party_name: str
    current: Decimal
    bucket_30: Decimal
    bucket_60: Decimal
    bucket_90: Decimal
    bucket_120_plus: Decimal
    total: Decimal


class ARAgingResponse(BaseModel):
    """Accounts receivable aging report."""

    as_of_date: date
    rows: list[ARAgingRow]
    total_current: Decimal
    total_30: Decimal
    total_60: Decimal
    total_90: Decimal
    total_120_plus: Decimal
    grand_total: Decimal


class BudgetVsActualRow(BaseModel):
    """Single budget vs actual comparison row."""

    account_id: uuid.UUID
    account_code: str
    account_name: str
    department_id: uuid.UUID | None
    budgeted: Decimal
    actual: Decimal
    variance: Decimal
    pct_used: Decimal


class BudgetVsActualResponse(BaseModel):
    """Budget vs actual report."""

    period_id: uuid.UUID
    rows: list[BudgetVsActualRow]


# ── Bank Reconciliation ──────────────────────────────────────────────────────


class BankStatementImportRow(BaseModel):
    """Single row of an imported bank statement."""

    transaction_date: date
    description: str | None = None
    amount: Decimal
    reference: str | None = None


class BankStatementImport(BaseModel):
    """Bulk bank statement import."""

    account_id: uuid.UUID
    statement_date: date
    rows: list[BankStatementImportRow]


class BankStatementResponse(BaseModel):
    """Bank statement line response."""

    id: uuid.UUID
    account_id: uuid.UUID
    statement_date: date
    transaction_date: date
    description: str | None
    amount: Decimal
    reference: str | None
    status: str
    matched_entry_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class ReconciliationMatch(BaseModel):
    """Auto-match suggestion."""

    statement_id: uuid.UUID
    entry_id: uuid.UUID
    confidence: str  # high|medium|low


class ReconciliationResponse(BaseModel):
    """Reconciliation report."""

    account_id: uuid.UUID
    period_id: uuid.UUID | None
    gl_balance: Decimal
    statement_balance: Decimal
    deposits_in_transit: Decimal
    outstanding_cheques: Decimal
    adjusted_balance: Decimal
    matched_count: int
    unmatched_statement_count: int
    unmatched_entry_count: int


class ManualMatchRequest(BaseModel):
    """Manual match between statement line and ledger entry."""

    entry_id: uuid.UUID


# ── Fixed Assets ─────────────────────────────────────────────────────────────


class FixedAssetCreate(BaseModel):
    """Schema for registering a fixed asset."""

    name: str = Field(..., min_length=1, max_length=200)
    asset_tag: str | None = Field(None, max_length=50)
    account_id: uuid.UUID
    accumulated_depreciation_account_id: uuid.UUID | None = None
    depreciation_expense_account_id: uuid.UUID | None = None
    purchase_date: date
    purchase_cost: Decimal = Field(..., gt=Decimal("0"))
    useful_life_months: int = Field(..., gt=0)
    salvage_value: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    depreciation_method: str = Field(
        default="straight_line",
        pattern=r"^(straight_line|declining_balance)$",
    )


class FixedAssetResponse(BaseModel):
    """Fixed asset response."""

    id: uuid.UUID
    name: str
    asset_tag: str | None
    account_id: uuid.UUID
    purchase_date: date
    purchase_cost: Decimal
    useful_life_months: int
    salvage_value: Decimal
    depreciation_method: str
    accumulated_depreciation: Decimal
    last_depreciated_at: date | None
    is_active: bool

    model_config = {"from_attributes": True}


class DepreciationRunResponse(BaseModel):
    """Result of a depreciation run."""

    period_id: uuid.UUID
    asset_count: int
    total_depreciation: Decimal
    transaction_ids: list[uuid.UUID]


# ── Tax Rates ────────────────────────────────────────────────────────────────


class TaxRateCreate(BaseModel):
    """Schema for creating a tax rate."""

    name: str = Field(..., min_length=1, max_length=100)
    rate: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    tax_type: str = Field(..., pattern=r"^(vat_output|vat_input|withholding)$")
    account_id: uuid.UUID


class TaxRateResponse(BaseModel):
    """Tax rate response."""

    id: uuid.UUID
    name: str
    rate: Decimal
    tax_type: str
    account_id: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}


# ── Budgets ──────────────────────────────────────────────────────────────────


class BudgetCreate(BaseModel):
    """Schema for creating a budget line."""

    account_id: uuid.UUID
    department_id: uuid.UUID | None = None
    period_id: uuid.UUID
    budgeted_amount: Decimal = Field(..., ge=Decimal("0"))
    notes: str | None = Field(None, max_length=2000)


class BudgetResponse(BaseModel):
    """Budget response."""

    id: uuid.UUID
    account_id: uuid.UUID
    department_id: uuid.UUID | None
    period_id: uuid.UUID
    budgeted_amount: Decimal
    notes: str | None

    model_config = {"from_attributes": True}


# ── Recurring Templates ──────────────────────────────────────────────────────


class RecurringTemplateCreate(BaseModel):
    """Schema for creating a recurring transaction template."""

    name: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=Decimal("0"))
    account_debit_id: uuid.UUID
    account_credit_id: uuid.UUID
    department_id: uuid.UUID | None = None
    frequency: str = Field(..., pattern=r"^(monthly|weekly|annual)$")
    next_post_date: date
    requires_approval: bool = False


class RecurringTemplateResponse(BaseModel):
    """Recurring template response."""

    id: uuid.UUID
    name: str
    event_type: str
    amount: Decimal
    account_debit_id: uuid.UUID
    account_credit_id: uuid.UUID
    department_id: uuid.UUID | None
    frequency: str
    next_post_date: date
    last_posted_at: datetime | None
    requires_approval: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ── Opening Balances ─────────────────────────────────────────────────────────


class OpeningBalanceCreate(BaseModel):
    """Schema for entering an opening balance."""

    account_id: uuid.UUID
    period_id: uuid.UUID
    debit_balance: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    credit_balance: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))


class OpeningBalanceResponse(BaseModel):
    """Opening balance response."""

    id: uuid.UUID
    account_id: uuid.UUID
    period_id: uuid.UUID
    debit_balance: Decimal
    credit_balance: Decimal
    entered_by: uuid.UUID | None
    approved_by: uuid.UUID | None

    model_config = {"from_attributes": True}
