"""Seed a default operating theatre for a facility (Tier 3 setup gap).

Surgical scheduling cannot be configured until a facility has at least one
operating theatre. This idempotent seeder provisions a general theatre so the
theatre module is usable out of the box; it is safe to re-run.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.theatre import OperatingTheatre

_DEFAULT_THEATRES = [
    {"name": "Main Theatre", "code": "OT-1", "theatre_type": "general", "floor": "1"},
    {"name": "Minor Procedures Room", "code": "OT-2", "theatre_type": "minor", "floor": "1"},
]


async def seed_default_theatres(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> int:
    """
    Ensure a facility has default operating theatres (idempotent).

    @param db: Async database session
    @param facility_id: Facility to seed
    @param user_id: Actor recorded on created rows
    @returns Number of theatres newly created
    """
    result = await db.execute(
        select(OperatingTheatre.code).where(
            OperatingTheatre.facility_id == facility_id,
            OperatingTheatre.is_deleted == False,  # noqa: E712
        )
    )
    existing = {row[0] for row in result.all()}

    created = 0
    for spec in _DEFAULT_THEATRES:
        if spec["code"] in existing:
            continue
        db.add(
            OperatingTheatre(
                facility_id=facility_id,
                name=spec["name"],
                code=spec["code"],
                theatre_type=spec["theatre_type"],
                status="available",
                floor=spec["floor"],
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
        )
        created += 1

    if created:
        await db.flush()
    return created
