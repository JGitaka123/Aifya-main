"""
Recurring transaction processor — runs daily.

For each due template that does not require approval, posts a transaction
through ``post_transaction`` using the template's event_type and advances
``next_post_date`` by the configured frequency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import RecurringTemplate, Transaction
from app.services.finance.posting_engine import post_transaction


def _advance_date(start: date_type, frequency: str) -> date_type:
    """
    Advance a date by ``frequency``.

    @param start: Current next_post_date
    @param frequency: monthly | weekly | annual
    @returns Next firing date
    """
    if frequency == "weekly":
        return date_type.fromordinal(start.toordinal() + 7)
    if frequency == "annual":
        return date_type(start.year + 1, start.month, start.day)
    # monthly
    new_month = start.month + 1
    new_year = start.year
    if new_month > 12:
        new_month = 1
        new_year += 1
    # Clamp day to month length
    import calendar

    last_day = calendar.monthrange(new_year, new_month)[1]
    return date_type(new_year, new_month, min(start.day, last_day))


async def process_due_recurring(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    today: date_type | None = None,
) -> list[Transaction]:
    """
    Find active recurring templates with ``next_post_date <= today`` and post them.

    Skips templates with ``requires_approval=True`` (returns them in audit log).

    @param db: Database session
    @param facility_id: Facility scope
    @param user_id: Posting user (typically a system service user)
    @param today: Reference date (default: today)
    @returns List of posted transactions
    """
    if today is None:
        today = date_type.today()

    result = await db.execute(
        select(RecurringTemplate).where(
            RecurringTemplate.facility_id == facility_id,
            RecurringTemplate.is_active == True,  # noqa: E712
            RecurringTemplate.is_deleted == False,  # noqa: E712
            RecurringTemplate.next_post_date <= today,
        )
    )
    templates = list(result.scalars().all())

    posted: list[Transaction] = []
    for tpl in templates:
        if tpl.requires_approval:
            # In production: send notification to finance admin.
            continue
        txn = await post_transaction(
            db=db,
            facility_id=facility_id,
            event_type=tpl.event_type,
            amount=tpl.amount,
            metadata={
                "date": tpl.next_post_date.isoformat(),
                "reference_type": "recurring_template",
                "reference_id": str(tpl.id),
                "description": tpl.name,
                "department_id": str(tpl.department_id) if tpl.department_id else None,
            },
            user_id=user_id,
        )
        tpl.last_posted_at = datetime.now(UTC)
        tpl.next_post_date = _advance_date(tpl.next_post_date, tpl.frequency)
        tpl.updated_by = user_id
        posted.append(txn)

    await db.flush()
    return posted


async def post_recurring_now(
    db: AsyncSession,
    facility_id: uuid.UUID,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    posting_date: date_type | None = None,
) -> Transaction:
    """
    Force-post a recurring template immediately (bypasses requires_approval).

    @param db: Database session
    @param facility_id: Facility scope
    @param template_id: Recurring template UUID
    @param user_id: User triggering the post
    @param posting_date: Override posting date (default: template.next_post_date)
    @returns Posted transaction
    """
    result = await db.execute(
        select(RecurringTemplate).where(
            RecurringTemplate.id == template_id,
            RecurringTemplate.facility_id == facility_id,
        )
    )
    tpl = result.scalar_one()
    if posting_date is None:
        posting_date = tpl.next_post_date

    txn = await post_transaction(
        db=db,
        facility_id=facility_id,
        event_type=tpl.event_type,
        amount=tpl.amount,
        metadata={
            "date": posting_date.isoformat(),
            "reference_type": "recurring_template",
            "reference_id": str(tpl.id),
            "description": tpl.name,
        },
        user_id=user_id,
    )
    tpl.last_posted_at = datetime.now(UTC)
    tpl.next_post_date = _advance_date(posting_date, tpl.frequency)
    tpl.updated_by = user_id
    await db.flush()
    return txn
