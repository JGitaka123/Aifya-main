"""
Fixed-asset depreciation engine.

Supports straight-line and declining-balance methods.
``post_monthly_depreciation`` posts a single transaction per asset per period
through the standard ``post_transaction`` engine using the ``depreciation`` event_type.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    AccountingPeriod,
    FixedAsset,
)
from app.services.finance.posting_engine import post_transaction

_ZERO = Decimal("0")
_QUANT = Decimal("0.01")


def _q(value: Decimal | int | float) -> Decimal:
    """Quantise to 2dp."""
    return Decimal(value).quantize(_QUANT)


def calc_depreciation(asset: FixedAsset) -> Decimal:
    """
    Compute one period's depreciation.

    Straight line:    (cost - salvage) / useful_life_months
    Declining balance: NBV * (2 / useful_life_months)

    @param asset: FixedAsset record
    @returns Monthly depreciation in DECIMAL(14,2)
    """
    if not asset.is_active or asset.useful_life_months <= 0:
        return _ZERO

    cost = Decimal(asset.purchase_cost)
    salvage = Decimal(asset.salvage_value)
    accumulated = Decimal(asset.accumulated_depreciation)

    if asset.depreciation_method == "straight_line":
        depreciable = max(cost - salvage, _ZERO)
        monthly = depreciable / Decimal(asset.useful_life_months)
        # Don't depreciate beyond depreciable base
        remaining = depreciable - accumulated
        return _q(min(monthly, remaining)) if remaining > 0 else _ZERO

    # Declining balance (200%)
    nbv = cost - accumulated
    if nbv <= salvage:
        return _ZERO
    rate = Decimal(2) / Decimal(asset.useful_life_months)
    monthly = nbv * rate
    # Don't drop NBV below salvage
    max_dep = nbv - salvage
    return _q(min(monthly, max_dep))


async def post_monthly_depreciation(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_id: uuid.UUID,
    user_id: uuid.UUID,
    posting_date: date_type | None = None,
) -> dict:
    """
    Post depreciation for every active asset for the given period.

    For each asset:
      DR Depreciation Expense (asset.depreciation_expense_account_id)
      CR Accumulated Depreciation (asset.accumulated_depreciation_account_id)

    These postings go through ``post_transaction`` using the
    ``depreciation`` event_type — posting_rules for that event must be seeded
    OR each asset's accounts are used directly via custom rule lookup.

    To keep posting_rules simple, we post per-asset via post_transaction
    with event_type ``depreciation`` and rely on a single seeded rule that
    uses generic Depreciation Expense + Accumulated Depreciation accounts.
    Asset-specific account overrides aren't honoured here — extend if needed.

    @param db: Database session
    @param facility_id: Facility scope
    @param period_id: Period to depreciate into
    @param user_id: User posting the run
    @param posting_date: Date for the depreciation postings (default: period end)
    @returns Summary {asset_count, total_depreciation, transaction_ids}
    """
    period_result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.facility_id == facility_id,
        )
    )
    period = period_result.scalar_one()
    if posting_date is None:
        posting_date = period.end_date

    assets_result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.facility_id == facility_id,
            FixedAsset.is_active == True,  # noqa: E712
            FixedAsset.is_deleted == False,  # noqa: E712
        )
    )
    assets = list(assets_result.scalars().all())

    transaction_ids: list[uuid.UUID] = []
    total_depreciation = _ZERO
    asset_count = 0

    for asset in assets:
        amount = calc_depreciation(asset)
        if amount <= 0:
            continue
        txn = await post_transaction(
            db=db,
            facility_id=facility_id,
            event_type="depreciation",
            amount=amount,
            metadata={
                "date": posting_date.isoformat(),
                "reference_type": "fixed_asset",
                "reference_id": str(asset.id),
                "description": f"Depreciation: {asset.name}",
            },
            user_id=user_id,
        )
        transaction_ids.append(txn.id)
        asset.accumulated_depreciation = _q(asset.accumulated_depreciation + amount)
        asset.last_depreciated_at = posting_date
        asset.updated_by = user_id
        total_depreciation += amount
        asset_count += 1

    await db.flush()

    return {
        "period_id": period_id,
        "asset_count": asset_count,
        "total_depreciation": _q(total_depreciation),
        "transaction_ids": transaction_ids,
    }
