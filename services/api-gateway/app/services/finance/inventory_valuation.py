"""
Inventory valuation — FIFO consumption + weighted-average cost.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import InventoryLot

_ZERO = Decimal("0")
_QUANT = Decimal("0.0001")  # 4dp for unit cost
_AMT_QUANT = Decimal("0.01")


def _q_amt(value: Decimal) -> Decimal:
    """Quantise to currency precision (2dp)."""
    return Decimal(value).quantize(_AMT_QUANT)


async def post_inventory_usage(
    db: AsyncSession,
    facility_id: uuid.UUID,
    item_id: uuid.UUID,
    quantity_used: Decimal,
) -> Decimal:
    """
    Consume inventory via FIFO — oldest lots first.
    Returns the total cost of goods used (used by COGS posting).

    @param db: Database session
    @param facility_id: Facility scope
    @param item_id: Inventory item UUID
    @param quantity_used: Quantity to consume (DECIMAL(12,2))
    @returns Total cost of consumed inventory
    @raises ValueError: When insufficient stock is available
    """
    qty_remaining = Decimal(quantity_used)
    if qty_remaining <= 0:
        return _ZERO

    lots_result = await db.execute(
        select(InventoryLot)
        .where(
            InventoryLot.facility_id == facility_id,
            InventoryLot.item_id == item_id,
            InventoryLot.remaining_quantity > 0,
            InventoryLot.is_deleted == False,  # noqa: E712
        )
        .order_by(InventoryLot.received_date.asc(), InventoryLot.created_at.asc())
        .with_for_update()
    )
    lots = list(lots_result.scalars().all())

    total_cost = _ZERO
    for lot in lots:
        if qty_remaining <= 0:
            break
        take = min(qty_remaining, lot.remaining_quantity)
        cost = take * lot.unit_cost
        total_cost += cost
        lot.remaining_quantity = lot.remaining_quantity - take
        qty_remaining -= take

    if qty_remaining > 0:
        raise ValueError(
            f"Insufficient stock for item {item_id}: short by {qty_remaining}"
        )

    await db.flush()
    return _q_amt(total_cost)


async def get_weighted_average_cost(
    db: AsyncSession,
    facility_id: uuid.UUID,
    item_id: uuid.UUID,
) -> Decimal:
    """
    Compute weighted-average unit cost = SUM(remaining_qty*unit_cost)/SUM(remaining_qty).

    @param db: Database session
    @param facility_id: Facility scope
    @param item_id: Inventory item UUID
    @returns Weighted average unit cost (4dp), or zero if no remaining stock
    """
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(InventoryLot.remaining_quantity * InventoryLot.unit_cost),
                0,
            ),
            func.coalesce(func.sum(InventoryLot.remaining_quantity), 0),
        ).where(
            InventoryLot.facility_id == facility_id,
            InventoryLot.item_id == item_id,
            InventoryLot.is_deleted == False,  # noqa: E712
        )
    )
    total_value, total_qty = result.first() or (0, 0)
    if not total_qty or Decimal(total_qty) == 0:
        return _ZERO
    return (Decimal(total_value) / Decimal(total_qty)).quantize(_QUANT)
