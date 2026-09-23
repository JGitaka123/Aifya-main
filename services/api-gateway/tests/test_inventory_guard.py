"""Tier 3: no-negative-stock guard (DB CHECK constraints)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.pharmacy import PharmacyBatch, PharmacyItem
from tests.conftest import FACILITY_ID, USER_ID, session_factory


@pytest.mark.asyncio
async def test_pharmacy_item_negative_quantity_rejected() -> None:
    """The DB refuses to store a negative on-hand quantity."""
    async with session_factory() as db:
        db.add(
            PharmacyItem(
                facility_id=FACILITY_ID,
                drug_code="NEG1",
                drug_name="Negative Test Drug",
                unit_of_measure="tablet",
                current_quantity=-1,
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()


@pytest.mark.asyncio
async def test_pharmacy_batch_negative_remaining_rejected() -> None:
    """The DB refuses to store a batch consumed below zero."""
    async with session_factory() as db:
        db.add(
            PharmacyBatch(
                facility_id=FACILITY_ID,
                pharmacy_item_id=uuid.uuid4(),
                quantity_received=10,
                quantity_remaining=-5,
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()
