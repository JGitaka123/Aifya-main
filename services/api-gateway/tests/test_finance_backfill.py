"""D3: GL/AR reconciliation via the idempotent finance backfill."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.billing import Invoice, Payment
from app.models.finance import Account, TransactionEntry
from app.services.finance.backfill_gl import backfill_facility_gl
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _account_balance(db, facility_id: uuid.UUID, code: str) -> Decimal:
    """Balance (debit - credit) of a chart-of-accounts code from posted entries."""
    account = (
        await db.execute(
            select(Account).where(
                Account.facility_id == facility_id, Account.code == code
            )
        )
    ).scalar_one_or_none()
    if account is None:
        return Decimal("0.00")
    dr, cr = (
        await db.execute(
            select(
                func.coalesce(func.sum(TransactionEntry.debit), 0),
                func.coalesce(func.sum(TransactionEntry.credit), 0),
            ).where(TransactionEntry.account_id == account.id)
        )
    ).one()
    return Decimal(dr) - Decimal(cr)


@pytest.mark.asyncio
async def test_backfill_reconciles_ar_with_outstanding() -> None:
    """
    An unseeded facility with a finalized invoice + partial payment has an
    empty ledger. After the backfill, AR balance == outstanding invoice
    balance, and the ledger is balanced (debits == credits). Re-running the
    backfill is idempotent (no double-posting).
    """
    async with session_factory() as db:
        invoice = Invoice(
            facility_id=FACILITY_ID,
            encounter_id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            invoice_number="INV-BF-1",
            status="finalized",
            subtotal_cents=100_000,
            total_cents=100_000,
            balance_cents=60_000,
            payment_method="cash",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(invoice)
        await db.flush()
        payment = Payment(
            facility_id=FACILITY_ID,
            invoice_id=invoice.id,
            patient_id=invoice.patient_id,
            amount_cents=40_000,
            payment_method="cash",
            paid_at=datetime.now(UTC),
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(payment)
        await db.flush()

        # Ledger is empty before backfill.
        assert await _account_balance(db, FACILITY_ID, "1100") == Decimal("0.00")

        result = await backfill_facility_gl(db, FACILITY_ID, USER_ID)
        await db.flush()

        assert result.invoices_posted == 1
        assert result.payments_posted == 1

        # AR-Patient balance equals the outstanding invoice balance (600.00).
        ar = await _account_balance(db, FACILITY_ID, "1100")
        assert ar == Decimal("600.00")
        assert ar == Decimal(invoice.balance_cents) / 100

        # Ledger is balanced overall.
        totals = (
            await db.execute(
                select(
                    func.coalesce(func.sum(TransactionEntry.debit), 0),
                    func.coalesce(func.sum(TransactionEntry.credit), 0),
                ).where(TransactionEntry.facility_id == FACILITY_ID)
            )
        ).one()
        assert Decimal(totals[0]) == Decimal(totals[1])

        # Idempotent: a second run posts no new entries.
        entries_before = (
            await db.execute(
                select(func.count(TransactionEntry.id)).where(
                    TransactionEntry.facility_id == FACILITY_ID
                )
            )
        ).scalar_one()
        await backfill_facility_gl(db, FACILITY_ID, USER_ID)
        await db.flush()
        entries_after = (
            await db.execute(
                select(func.count(TransactionEntry.id)).where(
                    TransactionEntry.facility_id == FACILITY_ID
                )
            )
        ).scalar_one()
        assert entries_after == entries_before
