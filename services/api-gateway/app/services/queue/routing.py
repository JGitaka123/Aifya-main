"""Resolve the unit a waiting patient belongs in.

A facility names its own units: one hospital calls the lab Laboratory, the
next calls it Pathology. Queue routing matches on a short code first and
falls back to a name hint, so a patient reaches the right waiting room however
the estate is labelled.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Department


async def find_department_id(
    db: AsyncSession,
    *,
    facility_id: uuid.UUID,
    codes: tuple[str, ...] = (),
    name_hints: tuple[str, ...] = (),
) -> uuid.UUID | None:
    """Find the active unit matching a code, then a name hint.

    @param db: The session to search with
    @param facility_id: Facility whose units are searched
    @param codes: Department codes to try, most specific first
    @param name_hints: Lower-case substrings to fall back on
    @returns The matching unit id, or None when the facility has none
    """

    rows = (
        await db.execute(
            select(Department.id, Department.code, Department.name).where(
                Department.facility_id == facility_id,
                Department.is_deleted == False,  # noqa: E712
                Department.is_active == True,  # noqa: E712
            )
        )
    ).all()
    if not rows:
        return None

    by_code = {(code or "").upper(): dept_id for dept_id, code, _name in rows}
    for code in codes:
        match = by_code.get(code.upper())
        if match is not None:
            return match

    for dept_id, _code, name in rows:
        lowered = (name or "").lower()
        if any(hint in lowered for hint in name_hints):
            return dept_id
    return None
