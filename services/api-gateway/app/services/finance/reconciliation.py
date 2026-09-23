"""
Bank reconciliation service.

Imports CSV bank statements, auto-matches against GL cash ledger entries,
and computes the reconciliation report (book-vs-bank balance).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    AccountingPeriod,
    BankStatement,
    FinanceAuditLog,
    Transaction,
    TransactionEntry,
)
from app.schemas.finance import (
    BankStatementImportRow,
    ReconciliationResponse,
)

_ZERO = Decimal("0")
_QUANT = Decimal("0.01")


def _q(value: Decimal | int | float) -> Decimal:
    """Quantise to 2dp."""
    return Decimal(value).quantize(_QUANT)


# ── CSV import ───────────────────────────────────────────────────────────────


def parse_bank_csv(csv_text: str) -> list[BankStatementImportRow]:
    """
    Parse a bank-statement CSV. Expected columns:
    ``date,description,amount,reference``.

    @param csv_text: Raw CSV file contents
    @returns Parsed rows
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[BankStatementImportRow] = []
    for record in reader:
        raw_date = record.get("date") or record.get("Date") or ""
        raw_amount = record.get("amount") or record.get("Amount") or "0"
        rows.append(
            BankStatementImportRow(
                transaction_date=date_type.fromisoformat(raw_date.strip()),
                description=(record.get("description") or record.get("Description") or "").strip()
                or None,
                amount=_q(Decimal(raw_amount.replace(",", "").strip())),
                reference=(record.get("reference") or record.get("Reference") or "").strip()
                or None,
            )
        )
    return rows


# ── Import ───────────────────────────────────────────────────────────────────


async def import_bank_statement(
    db: AsyncSession,
    facility_id: uuid.UUID,
    account_id: uuid.UUID,
    statement_date: date_type,
    rows: list[BankStatementImportRow],
    user_id: uuid.UUID | None = None,
) -> list[BankStatement]:
    """
    Insert parsed bank-statement rows into the bank_statements table.

    @param db: Database session
    @param facility_id: Facility scope
    @param account_id: GL cash/bank account
    @param statement_date: Closing date of the statement
    @param rows: Parsed rows
    @param user_id: User performing the import
    @returns List of created BankStatement rows
    """
    created: list[BankStatement] = []
    for row in rows:
        bs = BankStatement(
            facility_id=facility_id,
            account_id=account_id,
            statement_date=statement_date,
            transaction_date=row.transaction_date,
            description=row.description,
            amount=row.amount,
            reference=row.reference,
            status="unmatched",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(bs)
        created.append(bs)
    await db.flush()
    return created


# ── Auto-match ───────────────────────────────────────────────────────────────


async def auto_match(
    db: AsyncSession,
    facility_id: uuid.UUID,
    account_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """
    Match unmatched bank rows to GL cash entries by (date, amount).

    A bank credit (deposit, amount > 0) matches a debit on the cash account.
    A bank debit (amount < 0) matches a credit on the cash account.

    @param db: Database session
    @param facility_id: Facility scope
    @param account_id: GL cash account
    @param user_id: User running auto-match
    @returns Counts: matched, unmatched_statement, unmatched_entry
    """
    # Get unmatched statement rows
    stmts_result = await db.execute(
        select(BankStatement).where(
            BankStatement.facility_id == facility_id,
            BankStatement.account_id == account_id,
            BankStatement.status == "unmatched",
            BankStatement.is_deleted == False,  # noqa: E712
        )
    )
    statements = list(stmts_result.scalars().all())

    # Get GL entries on the cash account that are not yet matched
    entries_result = await db.execute(
        select(TransactionEntry, Transaction)
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
        )
    )
    entries = list(entries_result.all())

    # Build a lookup keyed by (date, signed_amount)
    used_entries: set[uuid.UUID] = set()
    matched = 0

    for stmt in statements:
        target_amt = stmt.amount  # +ve = inflow (debit cash), -ve = outflow (credit cash)
        for entry, txn in entries:
            if entry.id in used_entries:
                continue
            if txn.date != stmt.transaction_date:
                continue
            net = entry.debit - entry.credit
            if _q(net) == _q(target_amt):
                stmt.status = "matched"
                stmt.matched_entry_id = entry.id
                stmt.matched_at = datetime.now(UTC)
                stmt.matched_by = user_id
                stmt.updated_by = user_id
                used_entries.add(entry.id)
                matched += 1
                break

    await db.flush()

    unmatched_stmts = sum(1 for s in statements if s.status == "unmatched")
    unmatched_entries = sum(
        1 for entry, _ in entries if entry.id not in used_entries
    )

    return {
        "matched": matched,
        "unmatched_statement": unmatched_stmts,
        "unmatched_entry": unmatched_entries,
    }


# ── Manual match ─────────────────────────────────────────────────────────────


async def manual_match(
    db: AsyncSession,
    facility_id: uuid.UUID,
    statement_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
) -> BankStatement:
    """
    Manually link a statement row to a GL entry.

    @param db: Database session
    @param facility_id: Facility scope
    @param statement_id: Bank statement row UUID
    @param entry_id: GL entry UUID to match
    @param user_id: User performing the match
    @returns Updated BankStatement
    """
    result = await db.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.facility_id == facility_id,
        )
    )
    stmt = result.scalar_one()

    entry_result = await db.execute(
        select(TransactionEntry).where(
            TransactionEntry.id == entry_id,
            TransactionEntry.facility_id == facility_id,
        )
    )
    entry = entry_result.scalar_one()
    _ = entry  # validated existence/scope

    stmt.matched_entry_id = entry_id
    stmt.status = "matched"
    stmt.matched_at = datetime.now(UTC)
    stmt.matched_by = user_id
    stmt.updated_by = user_id

    db.add(
        FinanceAuditLog(
            facility_id=facility_id,
            action="manual_match_bank_statement",
            table_name="bank_statements",
            record_id=stmt.id,
            user_id=user_id,
            payload={
                "entry_id": str(entry_id),
                "amount": str(stmt.amount),
            },
        )
    )

    await db.flush()
    return stmt


# ── Reconciliation report ────────────────────────────────────────────────────


async def get_reconciliation_report(
    db: AsyncSession,
    facility_id: uuid.UUID,
    account_id: uuid.UUID,
    period_id: uuid.UUID | None = None,
) -> ReconciliationResponse:
    """
    Compute the reconciliation: GL Cash + Deposits in Transit
    - Outstanding Cheques = Bank Statement balance.

    @param db: Database session
    @param facility_id: Facility scope
    @param account_id: GL cash account
    @param period_id: Optional period (defaults to all-time)
    @returns Reconciliation snapshot
    """
    # Period date range
    period_end: date_type | None = None
    if period_id is not None:
        period_result = await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.id == period_id,
                AccountingPeriod.facility_id == facility_id,
            )
        )
        period = period_result.scalar_one()
        period_end = period.end_date

    # GL balance
    gl_stmt = (
        select(
            func.coalesce(func.sum(TransactionEntry.debit), 0)
            - func.coalesce(func.sum(TransactionEntry.credit), 0)
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
        )
    )
    if period_end:
        gl_stmt = gl_stmt.where(Transaction.date <= period_end)
    gl_balance = _q(Decimal((await db.execute(gl_stmt)).scalar() or 0))

    # Bank statement balance
    bank_stmt_result = await db.execute(
        select(func.coalesce(func.sum(BankStatement.amount), 0)).where(
            BankStatement.facility_id == facility_id,
            BankStatement.account_id == account_id,
            BankStatement.is_deleted == False,  # noqa: E712
        )
    )
    bank_balance = _q(Decimal(bank_stmt_result.scalar() or 0))

    # Deposits in transit: GL DR entries with no matching statement
    dit_stmt = (
        select(
            func.coalesce(func.sum(TransactionEntry.debit), 0)
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .outerjoin(
            BankStatement, BankStatement.matched_entry_id == TransactionEntry.id
        )
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
            TransactionEntry.debit > 0,
            BankStatement.id.is_(None),
        )
    )
    if period_end:
        dit_stmt = dit_stmt.where(Transaction.date <= period_end)
    deposits_in_transit = _q(Decimal((await db.execute(dit_stmt)).scalar() or 0))

    # Outstanding cheques: GL CR entries with no matching statement
    oc_stmt = (
        select(
            func.coalesce(func.sum(TransactionEntry.credit), 0)
        )
        .join(Transaction, TransactionEntry.transaction_id == Transaction.id)
        .outerjoin(
            BankStatement, BankStatement.matched_entry_id == TransactionEntry.id
        )
        .where(
            TransactionEntry.facility_id == facility_id,
            Transaction.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
            TransactionEntry.credit > 0,
            BankStatement.id.is_(None),
        )
    )
    if period_end:
        oc_stmt = oc_stmt.where(Transaction.date <= period_end)
    outstanding_cheques = _q(Decimal((await db.execute(oc_stmt)).scalar() or 0))

    adjusted = _q(gl_balance + deposits_in_transit - outstanding_cheques)

    matched_q = await db.execute(
        select(func.count(BankStatement.id)).where(
            BankStatement.facility_id == facility_id,
            BankStatement.account_id == account_id,
            BankStatement.status == "matched",
            BankStatement.is_deleted == False,  # noqa: E712
        )
    )
    unmatched_stmt_q = await db.execute(
        select(func.count(BankStatement.id)).where(
            BankStatement.facility_id == facility_id,
            BankStatement.account_id == account_id,
            BankStatement.status == "unmatched",
            BankStatement.is_deleted == False,  # noqa: E712
        )
    )

    # Unmatched ledger entries on the cash account (proxy for unmatched_entry_count)
    unmatched_entry_q = await db.execute(
        select(func.count(TransactionEntry.id))
        .outerjoin(
            BankStatement,
            (BankStatement.matched_entry_id == TransactionEntry.id)
            & (BankStatement.facility_id == facility_id),
        )
        .where(
            TransactionEntry.facility_id == facility_id,
            TransactionEntry.account_id == account_id,
            BankStatement.id.is_(None),
        )
    )

    return ReconciliationResponse(
        account_id=account_id,
        period_id=period_id,
        gl_balance=gl_balance,
        statement_balance=bank_balance,
        deposits_in_transit=deposits_in_transit,
        outstanding_cheques=outstanding_cheques,
        adjusted_balance=adjusted,
        matched_count=int(matched_q.scalar() or 0),
        unmatched_statement_count=int(unmatched_stmt_q.scalar() or 0),
        unmatched_entry_count=int(unmatched_entry_q.scalar() or 0),
    )
