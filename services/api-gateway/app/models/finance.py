"""
Hospital Finance Module v2.0 — SQLAlchemy models.

QuickBooks-grade double-entry accounting engine. Money stored as
DECIMAL(14,2) using SQLAlchemy ``Numeric`` (this is a separate ledger from the
KES-cent integer-based billing module).

All tables are multi-tenant (facility_id) and inherit ``AuditMixin``
(except immutable ledger tables which use minimal audit fields).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin

# ── Chart of Accounts ────────────────────────────────────────────────────────


class Account(AuditMixin, Base):
    """
    Chart of Accounts — hierarchical account tree.
    Types: asset, liability, equity, income, expense.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("facility_id", "code", name="uq_accounts_facility_code"),
        Index("ix_accounts_facility_type", "facility_id", "type"),
        Index("ix_accounts_facility_active", "facility_id", "is_active"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # cashflow categorisation: operating | investing | financing | none
    cashflow_category: Mapped[str] = mapped_column(
        String(20), default="none", nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


# ── Accounting Periods ───────────────────────────────────────────────────────


class AccountingPeriod(AuditMixin, Base):
    """
    Fiscal accounting period (typically monthly).
    Status: open | closed | locked.
    Locked periods cannot be reopened.
    """

    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("facility_id", "name", name="uq_periods_facility_name"),
        Index("ix_periods_facility_status", "facility_id", "status"),
        Index("ix_periods_facility_dates", "facility_id", "start_date", "end_date"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    year_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ── Transactions (Header) ────────────────────────────────────────────────────


class Transaction(Base):
    """
    Transaction header (immutable). Once posted, never edited.
    To correct, post a reversing transaction.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_facility_date", "facility_id", "date"),
        Index("ix_transactions_facility_period", "facility_id", "period_id"),
        Index("ix_transactions_facility_ref", "facility_id", "reference_type", "reference_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Transaction Entries (Ledger) ─────────────────────────────────────────────


class TransactionEntry(Base):
    """
    Core double-entry ledger row. A single transaction has 2+ entries
    where SUM(debit) == SUM(credit). Each row has either debit or credit
    populated, never both.
    """

    __tablename__ = "transaction_entries"
    __table_args__ = (
        CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_entry_debit_xor_credit",
        ),
        Index("ix_entries_facility_account", "facility_id", "account_id"),
        Index("ix_entries_transaction", "transaction_id"),
        Index("ix_entries_facility_dept", "facility_id", "department_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    debit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    currency: Mapped[str] = mapped_column(String(3), default="KES", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("1.0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Posting Rules ────────────────────────────────────────────────────────────


class PostingRule(AuditMixin, Base):
    """
    Maps an event_type (e.g. ``invoice_cash``) to debit/credit account pairs.
    Multiple rules can fire for one event (e.g. tax handling).
    """

    __tablename__ = "posting_rules"
    __table_args__ = (
        Index("ix_posting_rules_facility_event", "facility_id", "event_type"),
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_order: Mapped[int] = mapped_column(default=1, nullable=False)
    debit_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    credit_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    tax_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    amount_expression: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Audit Logs ───────────────────────────────────────────────────────────────


class FinanceAuditLog(Base):
    """
    Immutable audit log for finance actions (postings, period close, etc.).
    Separate from clinical event store for clarity.
    """

    __tablename__ = "finance_audit_logs"
    __table_args__ = (
        Index("ix_finance_audit_facility_action", "facility_id", "action"),
        Index("ix_finance_audit_record", "table_name", "record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    payload: Mapped[dict | None] = mapped_column(JSONB)


# ── Idempotency Keys ─────────────────────────────────────────────────────────


class IdempotencyKey(Base):
    """Idempotency tracking for retry-safe POST operations."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Opening Balances ─────────────────────────────────────────────────────────


class OpeningBalance(AuditMixin, Base):
    """Opening balances at the start of an accounting period."""

    __tablename__ = "opening_balances"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "account_id", "period_id",
            name="uq_opening_account_period",
        ),
        Index("ix_opening_facility_period", "facility_id", "period_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    debit_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    credit_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    entered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Bank Statements ──────────────────────────────────────────────────────────


class BankStatement(AuditMixin, Base):
    """Imported bank statement line for reconciliation."""

    __tablename__ = "bank_statements"
    __table_args__ = (
        Index("ix_bank_facility_account", "facility_id", "account_id"),
        Index("ix_bank_facility_status", "facility_id", "status"),
        Index("ix_bank_facility_date", "facility_id", "transaction_date"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="unmatched", nullable=False)
    matched_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transaction_entries.id")
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matched_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


# ── Insurance Claims (Finance ledger) ────────────────────────────────────────


class InsuranceClaimFinance(AuditMixin, Base):
    """
    Finance-side insurance claims tracker (separate from clinical
    insurance_claims). Tracks AR-Insurance lifecycle.
    """

    __tablename__ = "insurance_claims_finance"
    __table_args__ = (
        Index("ix_insclaim_finance_facility_status", "facility_id", "status"),
        Index("ix_insclaim_finance_facility_due", "facility_id", "due_date"),
    )

    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id")
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    insurer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount_claimed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_approved: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    rejection_reason: Mapped[str | None] = mapped_column(Text)


# ── Fixed Assets ─────────────────────────────────────────────────────────────


class FixedAsset(AuditMixin, Base):
    """Fixed asset register with depreciation parameters."""

    __tablename__ = "fixed_assets"
    __table_args__ = (
        Index("ix_fixed_assets_facility_active", "facility_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_tag: Mapped[str | None] = mapped_column(String(50))
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    accumulated_depreciation_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    depreciation_expense_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id")
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    useful_life_months: Mapped[int] = mapped_column(nullable=False)
    salvage_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    depreciation_method: Mapped[str] = mapped_column(
        String(30), default="straight_line", nullable=False
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    last_depreciated_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Tax Rates ────────────────────────────────────────────────────────────────


class TaxRate(AuditMixin, Base):
    """Tax rates (VAT, withholding) tied to a posting account."""

    __tablename__ = "tax_rates"
    __table_args__ = (
        Index("ix_tax_rates_facility_type", "facility_id", "tax_type"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Inventory Lots (FIFO valuation) ──────────────────────────────────────────


class InventoryLot(AuditMixin, Base):
    """Inventory lot tracking for FIFO/weighted-average valuation."""

    __tablename__ = "inventory_lots"
    __table_args__ = (
        Index("ix_inv_lots_facility_item", "facility_id", "item_id"),
        Index("ix_inv_lots_facility_received", "facility_id", "received_date"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id")
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lot_number: Mapped[str | None] = mapped_column(String(50))


# ── Budgets ──────────────────────────────────────────────────────────────────


class Budget(AuditMixin, Base):
    """Budgeted amounts per account/department/period."""

    __tablename__ = "budgets"
    __table_args__ = (
        Index("ix_budgets_facility_period", "facility_id", "period_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_periods.id"), nullable=False
    )
    budgeted_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)


# ── Recurring Transactions ───────────────────────────────────────────────────


class RecurringTemplate(AuditMixin, Base):
    """Recurring transaction template (rent, salaries, etc.)."""

    __tablename__ = "recurring_templates"
    __table_args__ = (
        Index("ix_recurring_facility_active", "facility_id", "is_active"),
        Index("ix_recurring_facility_next", "facility_id", "next_post_date"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    account_debit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    account_credit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    next_post_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
