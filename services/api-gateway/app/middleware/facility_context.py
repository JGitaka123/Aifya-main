"""
Middleware to set PostgreSQL session variable for Row-Level Security.
Sets `app.current_facility_id` so RLS policies can filter rows at the DB level.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_facility_context(db: AsyncSession, facility_id: str) -> None:
    """
    Set the facility context for the current DB session.
    This enables RLS policies to filter rows by facility.

    @param db: Async database session
    @param facility_id: Facility UUID string from JWT
    """
    normalized_facility_id = str(uuid.UUID(str(facility_id)))
    db.info["facility_id"] = normalized_facility_id

    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return

    await db.execute(
        text("SELECT set_config('app.current_facility_id', :facility_id, true)"),
        {"facility_id": normalized_facility_id},
    )
