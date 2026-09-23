"""Hospital Finance Module v2.0 — double-entry GL.

Revision ID: 002
Revises: 001
Create Date: 2026-05-07

Creates finance tables:
  accounts, accounting_periods, transactions, transaction_entries,
  posting_rules, finance_audit_logs, idempotency_keys, opening_balances,
  bank_statements, insurance_claims_finance, fixed_assets, tax_rates,
  inventory_lots, budgets, recurring_templates.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    """Return AuditMixin columns shared across most finance tables."""
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    """Create all finance tables."""

    # ── Accounts (Chart of Accounts) ───────────────────────────────────────
    op.create_table(
        "accounts",
        *_audit_columns(),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("cashflow_category", sa.String(20), nullable=False, server_default="none"),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text),
        sa.UniqueConstraint("facility_id", "code", name="uq_accounts_facility_code"),
    )
    op.create_index("ix_accounts_facility_type", "accounts", ["facility_id", "type"])
    op.create_index("ix_accounts_facility_active", "accounts", ["facility_id", "is_active"])

    # ── Accounting Periods ─────────────────────────────────────────────────
    op.create_table(
        "accounting_periods",
        *_audit_columns(),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closed_by", UUID(as_uuid=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("year_end", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("facility_id", "name", name="uq_periods_facility_name"),
    )
    op.create_index("ix_periods_facility_status", "accounting_periods", ["facility_id", "status"])
    op.create_index(
        "ix_periods_facility_dates",
        "accounting_periods",
        ["facility_id", "start_date", "end_date"],
    )

    # ── Transactions (Header) ──────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("reference_type", sa.String(50)),
        sa.Column("reference_id", UUID(as_uuid=True)),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_reversal", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("reverses_transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id")),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_facility_date", "transactions", ["facility_id", "date"])
    op.create_index("ix_transactions_facility_period", "transactions", ["facility_id", "period_id"])
    op.create_index(
        "ix_transactions_facility_ref",
        "transactions",
        ["facility_id", "reference_type", "reference_id"],
    )

    # ── Transaction Entries (Ledger) ───────────────────────────────────────
    op.create_table(
        "transaction_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("exchange_rate", sa.Numeric(10, 6), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)",
            name="ck_entry_debit_xor_credit",
        ),
    )
    op.create_index("ix_entries_facility_account", "transaction_entries", ["facility_id", "account_id"])
    op.create_index("ix_entries_transaction", "transaction_entries", ["transaction_id"])
    op.create_index("ix_entries_facility_dept", "transaction_entries", ["facility_id", "department_id"])

    # ── Posting Rules ──────────────────────────────────────────────────────
    op.create_table(
        "posting_rules",
        *_audit_columns(),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("rule_order", sa.Integer, nullable=False, server_default="1"),
        sa.Column("debit_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("credit_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("tax_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("amount_expression", sa.String(100)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_posting_rules_facility_event", "posting_rules", ["facility_id", "event_type"])

    # ── Finance Audit Logs ─────────────────────────────────────────────────
    op.create_table(
        "finance_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("table_name", sa.String(50), nullable=False),
        sa.Column("record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", JSONB),
    )
    op.create_index("ix_finance_audit_facility_action", "finance_audit_logs", ["facility_id", "action"])
    op.create_index("ix_finance_audit_record", "finance_audit_logs", ["table_name", "record_id"])

    # ── Idempotency Keys ───────────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Opening Balances ───────────────────────────────────────────────────
    op.create_table(
        "opening_balances",
        *_audit_columns(),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("debit_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("entered_by", UUID(as_uuid=True)),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("facility_id", "account_id", "period_id", name="uq_opening_account_period"),
    )
    op.create_index("ix_opening_facility_period", "opening_balances", ["facility_id", "period_id"])

    # ── Bank Statements ────────────────────────────────────────────────────
    op.create_table(
        "bank_statements",
        *_audit_columns(),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("statement_date", sa.Date, nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False, server_default="unmatched"),
        sa.Column("matched_entry_id", UUID(as_uuid=True), sa.ForeignKey("transaction_entries.id")),
        sa.Column("matched_at", sa.DateTime(timezone=True)),
        sa.Column("matched_by", UUID(as_uuid=True)),
    )
    op.create_index("ix_bank_facility_account", "bank_statements", ["facility_id", "account_id"])
    op.create_index("ix_bank_facility_status", "bank_statements", ["facility_id", "status"])
    op.create_index("ix_bank_facility_date", "bank_statements", ["facility_id", "transaction_date"])

    # ── Insurance Claims Finance ───────────────────────────────────────────
    op.create_table(
        "insurance_claims_finance",
        *_audit_columns(),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id")),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("insurer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount_claimed", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_approved", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_date", sa.Date),
        sa.Column("rejection_reason", sa.Text),
    )
    op.create_index("ix_insclaim_finance_facility_status", "insurance_claims_finance", ["facility_id", "status"])
    op.create_index("ix_insclaim_finance_facility_due", "insurance_claims_finance", ["facility_id", "due_date"])

    # ── Fixed Assets ───────────────────────────────────────────────────────
    op.create_table(
        "fixed_assets",
        *_audit_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_tag", sa.String(50)),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("accumulated_depreciation_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("depreciation_expense_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column("purchase_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("useful_life_months", sa.Integer, nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("depreciation_method", sa.String(30), nullable=False, server_default="straight_line"),
        sa.Column("accumulated_depreciation", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("last_depreciated_at", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_fixed_assets_facility_active", "fixed_assets", ["facility_id", "is_active"])

    # ── Tax Rates ──────────────────────────────────────────────────────────
    op.create_table(
        "tax_rates",
        *_audit_columns(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("tax_type", sa.String(20), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_tax_rates_facility_type", "tax_rates", ["facility_id", "tax_type"])

    # ── Inventory Lots ─────────────────────────────────────────────────────
    op.create_table(
        "inventory_lots",
        *_audit_columns(),
        sa.Column("item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False),
        sa.Column("received_date", sa.Date, nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("accounting_periods.id")),
        sa.Column("supplier_id", UUID(as_uuid=True)),
        sa.Column("lot_number", sa.String(50)),
    )
    op.create_index("ix_inv_lots_facility_item", "inventory_lots", ["facility_id", "item_id"])
    op.create_index("ix_inv_lots_facility_received", "inventory_lots", ["facility_id", "received_date"])

    # ── Budgets ────────────────────────────────────────────────────────────
    op.create_table(
        "budgets",
        *_audit_columns(),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("period_id", UUID(as_uuid=True), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("budgeted_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_budgets_facility_period", "budgets", ["facility_id", "period_id"])

    # ── Recurring Templates ────────────────────────────────────────────────
    op.create_table(
        "recurring_templates",
        *_audit_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("account_debit_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("account_credit_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("next_post_date", sa.Date, nullable=False),
        sa.Column("last_posted_at", sa.DateTime(timezone=True)),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_recurring_facility_active", "recurring_templates", ["facility_id", "is_active"])
    op.create_index("ix_recurring_facility_next", "recurring_templates", ["facility_id", "next_post_date"])


def downgrade() -> None:
    """Drop all finance tables (reverse FK order)."""
    op.drop_table("recurring_templates")
    op.drop_table("budgets")
    op.drop_table("inventory_lots")
    op.drop_table("tax_rates")
    op.drop_table("fixed_assets")
    op.drop_table("insurance_claims_finance")
    op.drop_table("bank_statements")
    op.drop_table("opening_balances")
    op.drop_table("idempotency_keys")
    op.drop_table("finance_audit_logs")
    op.drop_table("posting_rules")
    op.drop_table("transaction_entries")
    op.drop_table("transactions")
    op.drop_table("accounting_periods")
    op.drop_table("accounts")
