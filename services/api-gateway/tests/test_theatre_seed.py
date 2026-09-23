"""Tier 3: default operating theatre seeding (setup gap)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.theatre import OperatingTheatre
from app.services.theatre_seed import seed_default_theatres
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest.mark.asyncio
async def test_seed_creates_theatres_and_is_idempotent() -> None:
    async with session_factory() as db:
        created = await seed_default_theatres(db, FACILITY_ID, USER_ID)
        await db.commit()
        assert created >= 1

    async with session_factory() as db:
        rows = (
            await db.execute(
                select(OperatingTheatre).where(
                    OperatingTheatre.facility_id == FACILITY_ID
                )
            )
        ).scalars().all()
        assert len(rows) == created
        assert any(t.status == "available" for t in rows)

    # Re-running must not duplicate.
    async with session_factory() as db:
        again = await seed_default_theatres(db, FACILITY_ID, USER_ID)
        await db.commit()
        assert again == 0
