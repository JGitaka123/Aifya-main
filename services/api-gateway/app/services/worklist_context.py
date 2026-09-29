"""Shared enrichment for department worklists.

Every department screen answers the same questions about the patient in front
of it: who sent them, what were they asked to do, and has that specific request
been paid for. The ordering clinician's name is resolved here so laboratory,
radiology and pharmacy share one implementation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Staff


async def staff_display_names(
    db: AsyncSession, staff_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """
    Resolve the clinicians who ordered work, in a single query.

    Order rows carry the ordering clinician's staff id, so the department sees
    "Referred by Dr. ..." instead of a UUID.

    @param db: Database session
    @param staff_ids: Staff UUIDs from the page's orders
    @returns Map of staff UUID -> display name
    """
    wanted = {staff_id for staff_id in staff_ids if staff_id is not None}
    if not wanted:
        return {}
    rows = (
        await db.execute(
            select(
                Staff.id, Staff.title, Staff.first_name, Staff.last_name
            ).where(Staff.id.in_(wanted))
        )
    ).all()
    names: dict[uuid.UUID, str] = {}
    for staff_id, title, first_name, last_name in rows:
        parts = [part for part in (title, first_name, last_name) if part]
        names[staff_id] = " ".join(parts).strip()
    return names
