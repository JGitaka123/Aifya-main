"""
Stock-out prediction module.

Predicts inventory item stockout timelines by analysing dispensing history
over the last 30 days. Items are ranked by urgency based on estimated days
until stock depletion.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.models import StockoutPrediction

logger = structlog.get_logger(__name__)

# Default lead time in days for reorder calculation
_DEFAULT_LEAD_TIME_DAYS = 14

# Safety stock multiplier (1.5x average daily consumption * lead time)
_SAFETY_STOCK_MULTIPLIER = 1.5


def _classify_urgency(days_to_stockout: float) -> str:
    """
    Classify urgency level based on days until stockout.

    @param days_to_stockout: Estimated days until stock reaches zero
    @returns Urgency level: critical, high, moderate, or low
    """
    if days_to_stockout < 7:
        return "critical"
    if days_to_stockout < 14:
        return "high"
    if days_to_stockout < 30:
        return "moderate"
    return "low"


async def predict_stockouts(
    db: AsyncSession,
    facility_id: uuid.UUID,
) -> list[StockoutPrediction]:
    """
    Predict stockout timelines for all active inventory items at a facility.

    Calculates daily consumption rates from the last 30 days of inventory
    transactions, estimates days to stockout, and computes reorder quantities
    with safety stock buffers. Results are sorted by urgency (most critical first).

    @param db: Async database session
    @param facility_id: Facility UUID for multi-tenant filtering
    @returns List of StockoutPrediction sorted by urgency (critical first)
    """
    log = logger.bind(facility_id=str(facility_id))
    log.info("analytics.stockout.predict_start")

    predictions: list[StockoutPrediction] = []

    try:
        from app.models.inventory import InventoryItem, InventoryTransaction

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # --- Fetch all active inventory items ---
        items_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.facility_id == facility_id,
                InventoryItem.is_active.is_(True),
                InventoryItem.is_deleted.is_(False),
            )
        )
        items = items_result.scalars().all()

        if not items:
            log.info("analytics.stockout.no_items_found")
            return []

        # --- For each item, calculate consumption rate ---
        for item in items:
            # Sum of outgoing (negative) transactions in last 30 days
            consumption_result = await db.execute(
                select(func.coalesce(func.sum(func.abs(InventoryTransaction.quantity)), 0)).where(
                    InventoryTransaction.facility_id == facility_id,
                    InventoryTransaction.item_id == item.id,
                    InventoryTransaction.transaction_type.in_(["issue", "write_off"]),
                    InventoryTransaction.transaction_date >= thirty_days_ago,
                    InventoryTransaction.is_deleted.is_(False),
                )
            )
            total_consumed: int = consumption_result.scalar_one()

            # Daily consumption rate
            daily_rate = total_consumed / 30.0

            # Days to stockout
            if daily_rate > 0:
                days_to_stockout = item.current_stock / daily_rate
            else:
                # No consumption — effectively infinite days to stockout
                # Cap at 365 to avoid infinity in JSON serialization
                days_to_stockout = 365.0

            urgency = _classify_urgency(days_to_stockout)

            # Reorder quantity: (lead_time * daily_rate * safety_multiplier) - current_stock
            safety_stock = daily_rate * _DEFAULT_LEAD_TIME_DAYS * _SAFETY_STOCK_MULTIPLIER
            reorder_qty = max(0, int(safety_stock - item.current_stock + daily_rate * _DEFAULT_LEAD_TIME_DAYS))

            # Use the item's own reorder_quantity if our calculation yields less
            reorder_qty = max(reorder_qty, item.reorder_quantity if item.reorder_quantity else 0)

            predictions.append(
                StockoutPrediction(
                    item_code=item.item_code,
                    item_name=item.name,
                    current_stock=item.current_stock,
                    predicted_days_to_stockout=round(days_to_stockout, 1),
                    daily_consumption_rate=round(daily_rate, 2),
                    reorder_quantity=reorder_qty,
                    urgency=urgency,
                )
            )

    except Exception as exc:
        log.warning("analytics.stockout.prediction_failed", error=str(exc))
        return []

    # Sort by urgency: critical first, then high, moderate, low
    urgency_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
    predictions.sort(key=lambda p: (urgency_order.get(p.urgency, 4), p.predicted_days_to_stockout))

    log.info("analytics.stockout.predict_complete", item_count=len(predictions))
    return predictions
