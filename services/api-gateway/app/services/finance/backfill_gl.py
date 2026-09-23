"""
Idempotent GL backfill — re-post historical billing to the general ledger.

Fixes facilities whose invoices/payments never reached the GL because the
facility was never seeded with a chart of accounts / accounting period, so
every posting was silently skipped (the QA D3 symptom: all-zero ledger while
Billing shows outstanding invoices).

Safe to re-run: ``seed_facility_finance`` skips existing accounts/rules,
accounting periods self-provision, and every GL post is keyed by a stable
``idempotency_key`` (``invoice_finalized:{id}`` / ``payment_received:{id}``),
so already-posted documents are skipped, never double-posted.

Run against a live DB:

    python -m app.services.finance.backfill_gl
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, Payment
from app.models.facility import Facility
from app.services.billing_service import BillingService
from app.services.finance.seed_data import seed_facility_finance
from app.services.lab_catalog import seed_default_lab_catalog
from app.services.pharmacy_seed import seed_essential_drugs
from app.services.theatre_seed import seed_default_theatres


@dataclass
class BackfillResult:
    """Summary of a single facility's GL backfill."""

    facility_id: str
    accounts_seeded: int = 0
    rules_seeded: int = 0
    lab_tests_seeded: int = 0
    theatres_seeded: int = 0
    drugs_seeded: int = 0
    invoices_posted: int = 0
    payments_posted: int = 0


async def backfill_facility_gl(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> BackfillResult:
    """
    Seed finance infrastructure and re-post a facility's billing to the GL.

    @param db: Database session (caller commits)
    @param facility_id: Facility to backfill
    @param user_id: Posting user recorded on backfilled entries
    @returns Counts of what was seeded/posted
    """
    result = BackfillResult(facility_id=str(facility_id))

    summary = await seed_facility_finance(db, facility_id, user_id)
    result.accounts_seeded = int(summary.get("accounts_created", 0))
    result.rules_seeded = int(summary.get("rules_created", 0))
    result.lab_tests_seeded = await seed_default_lab_catalog(db, facility_id, user_id)
    result.theatres_seeded = await seed_default_theatres(db, facility_id, user_id)
    result.drugs_seeded = await seed_essential_drugs(db, facility_id, user_id)

    billing = BillingService(db)

    invoices = (
        await db.execute(
            select(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.status != "draft",
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    for invoice in invoices:
        await billing._post_invoice_gl(
            invoice=invoice, facility_id=facility_id, user_id=user_id
        )
        result.invoices_posted += 1

    payments = (
        await db.execute(
            select(Payment).where(
                Payment.facility_id == facility_id,
                Payment.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    for payment in payments:
        pay_invoice = (
            await db.execute(select(Invoice).where(Invoice.id == payment.invoice_id))
        ).scalar_one_or_none()
        if pay_invoice is None:
            continue
        await billing._post_payment_gl(
            payment=payment,
            invoice=pay_invoice,
            facility_id=facility_id,
            user_id=user_id,
        )
        result.payments_posted += 1

    return result


async def backfill_all(
    db: AsyncSession, user_id: uuid.UUID | None = None
) -> list[BackfillResult]:
    """
    Backfill the GL for every facility.

    @param db: Database session (caller commits)
    @param user_id: Posting user recorded on backfilled entries
    @returns Per-facility backfill summaries
    """
    facilities = (await db.execute(select(Facility))).scalars().all()
    results: list[BackfillResult] = []
    for facility in facilities:
        results.append(await backfill_facility_gl(db, facility.id, user_id))
    return results


async def _main() -> None:
    """Run the backfill across all facilities and commit."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        results = await backfill_all(db)
        await db.commit()

    for r in results:
        print(
            f"facility={r.facility_id} accounts+{r.accounts_seeded} "
            f"rules+{r.rules_seeded} labtests+{r.lab_tests_seeded} "
            f"theatres+{r.theatres_seeded} drugs+{r.drugs_seeded} "
            f"invoices={r.invoices_posted} payments={r.payments_posted}"
        )
    print(f"Backfilled {len(results)} facilities.")


if __name__ == "__main__":
    asyncio.run(_main())
