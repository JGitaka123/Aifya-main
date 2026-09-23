"""
Seed default Chart of Accounts and posting rules for a new facility.

The default CoA covers 27 accounts spanning the 5 standard account types,
chosen to support hospital workflows: cash, AR (cash + insurance),
inventory, fixed assets, payroll & statutory liabilities, VAT,
revenue streams, and operating expenses.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import Account, PostingRule

# Code, Name, Type, Cashflow Category
DEFAULT_ACCOUNTS: list[tuple[str, str, str, str]] = [
    # Assets (1xxx)
    ("1010", "Cash on Hand", "asset", "operating"),
    ("1020", "Bank Account", "asset", "operating"),
    ("1100", "Accounts Receivable - Patient", "asset", "operating"),
    ("1110", "Accounts Receivable - Insurance", "asset", "operating"),
    ("1200", "Inventory - Pharmacy", "asset", "operating"),
    ("1210", "Inventory - Medical Supplies", "asset", "operating"),
    ("1500", "Fixed Assets - Equipment", "asset", "investing"),
    ("1510", "Accumulated Depreciation - Equipment", "asset", "investing"),
    ("1520", "Fixed Assets - Buildings", "asset", "investing"),
    # Liabilities (2xxx)
    ("2010", "Accounts Payable - Suppliers", "liability", "operating"),
    ("2100", "VAT Output (Payable)", "liability", "operating"),
    ("2110", "VAT Input (Receivable)", "asset", "operating"),
    ("2200", "PAYE Payable", "liability", "operating"),
    ("2210", "NSSF Payable", "liability", "operating"),
    ("2220", "SHIF Payable", "liability", "operating"),
    ("2230", "Housing Levy Payable", "liability", "operating"),
    ("2300", "Withholding Tax Payable", "liability", "operating"),
    # Equity (3xxx)
    ("3000", "Owner's Capital", "equity", "financing"),
    ("3010", "Retained Earnings", "equity", "none"),
    # Income (4xxx)
    ("4000", "Consultation Revenue", "income", "operating"),
    ("4010", "Pharmacy Revenue", "income", "operating"),
    ("4020", "Laboratory Revenue", "income", "operating"),
    ("4030", "Procedure Revenue", "income", "operating"),
    # Expenses (5xxx)
    ("5000", "Salaries & Wages", "expense", "operating"),
    ("5010", "Cost of Goods Sold", "expense", "operating"),
    ("5020", "Depreciation Expense", "expense", "operating"),
    ("5030", "Operating Expenses", "expense", "operating"),
]


# Event type -> (debit_code, credit_code, tax_code | None)
DEFAULT_RULES: list[tuple[str, str, str, str | None]] = [
    # Patient pays cash for consult
    ("invoice_cash", "1010", "4000", None),
    # Patient on insurance — receivable booked
    ("invoice_insurance", "1110", "4000", None),
    # Patient invoice on credit (private debtors)
    ("invoice_credit", "1100", "4000", None),
    # Cash payment received against AR-Patient
    ("payment_received", "1010", "1100", None),
    # Insurer remits payment
    ("insurance_payment_received", "1020", "1110", None),
    # Cash expense (e.g. utility paid)
    ("expense_paid", "5030", "1010", None),
    # Inventory purchase (cash)
    ("inventory_purchase", "1200", "1010", None),
    # Inventory consumption (COGS recognition)
    ("inventory_usage", "5010", "1200", None),
    # Monthly depreciation
    ("depreciation", "5020", "1510", None),
    # Year-end close placeholder (handled by year-end engine)
    ("year_end_close", "3010", "3010", None),
    # Payroll: gross salary paid via bank
    ("payroll_run", "5000", "1020", None),
    # Employer statutory (NSSF / SHIF / Housing etc.)
    ("employer_statutory", "5000", "2210", None),
]


async def seed_default_chart_of_accounts(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict[str, uuid.UUID]:
    """
    Create the default 27-account Chart of Accounts for a facility.
    Skips accounts that already exist (idempotent).

    @param db: Database session
    @param facility_id: Facility scope
    @param user_id: Creator
    @returns Map {code: account_id} for all default accounts
    """
    existing_result = await db.execute(
        select(Account).where(Account.facility_id == facility_id)
    )
    existing_by_code = {a.code: a for a in existing_result.scalars().all()}

    code_to_id: dict[str, uuid.UUID] = {}
    for code, name, atype, cashflow in DEFAULT_ACCOUNTS:
        if code in existing_by_code:
            code_to_id[code] = existing_by_code[code].id
            continue
        account = Account(
            facility_id=facility_id,
            code=code,
            name=name,
            type=atype,
            cashflow_category=cashflow,
            is_system=True,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(account)
        await db.flush()
        code_to_id[code] = account.id

    return code_to_id


async def seed_default_posting_rules(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[PostingRule]:
    """
    Seed default posting rules. Requires that the chart of accounts is
    already seeded for ``facility_id``.

    @param db: Database session
    @param facility_id: Facility scope
    @param user_id: Creator
    @returns List of created PostingRule rows
    """
    accounts_result = await db.execute(
        select(Account).where(Account.facility_id == facility_id)
    )
    by_code: dict[str, Account] = {
        a.code: a for a in accounts_result.scalars().all()
    }

    existing_result = await db.execute(
        select(PostingRule).where(PostingRule.facility_id == facility_id)
    )
    existing_event_types = {r.event_type for r in existing_result.scalars().all()}

    created: list[PostingRule] = []
    for event_type, debit_code, credit_code, tax_code in DEFAULT_RULES:
        if event_type in existing_event_types:
            continue
        if debit_code not in by_code or credit_code not in by_code:
            continue
        rule = PostingRule(
            facility_id=facility_id,
            event_type=event_type,
            rule_order=1,
            debit_account_id=by_code[debit_code].id,
            credit_account_id=by_code[credit_code].id,
            tax_account_id=by_code[tax_code].id if tax_code and tax_code in by_code else None,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(rule)
        created.append(rule)

    await db.flush()
    return created


async def seed_facility_finance(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict:
    """
    Convenience: seed both the CoA and the default posting rules.

    @param db: Database session
    @param facility_id: Facility scope
    @param user_id: Creator
    @returns Summary {accounts_created, rules_created}
    """
    code_to_id = await seed_default_chart_of_accounts(db, facility_id, user_id)
    rules = await seed_default_posting_rules(db, facility_id, user_id)
    return {
        "accounts_created": len(code_to_id),
        "rules_created": len(rules),
    }
