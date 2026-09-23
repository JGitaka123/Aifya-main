"""
Tax utilities — VAT and Withholding Tax calculations.

Posting rules apply tax via their ``tax_account_id`` and an
``amount_expression`` (extension point). These helpers compute the tax
component when a caller already knows which rate applies.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import TaxRate

_QUANT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantise to 2dp."""
    return Decimal(value).quantize(_QUANT)


def calc_vat_inclusive(gross_amount: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """
    Split a VAT-inclusive amount into ``(net, vat)``.

    @param gross_amount: VAT-inclusive total
    @param rate: VAT rate (e.g. 0.16 for 16%)
    @returns (net_amount, vat_amount)
    """
    factor = Decimal("1") + rate
    net = gross_amount / factor
    vat = gross_amount - net
    return _q(net), _q(vat)


def calc_vat_exclusive(net_amount: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """
    Compute VAT on a net amount.

    @param net_amount: Net (excluding VAT) total
    @param rate: VAT rate
    @returns (gross_amount, vat_amount)
    """
    vat = net_amount * rate
    return _q(net_amount + vat), _q(vat)


def calc_withholding(
    gross_amount: Decimal, rate: Decimal
) -> tuple[Decimal, Decimal]:
    """
    Compute withholding tax — supplier receives ``net``, ``wht`` goes to authority.

    @param gross_amount: Pre-withholding amount
    @param rate: WHT rate (e.g. 0.05 for 5%)
    @returns (amount_to_supplier, withheld_amount)
    """
    wht = _q(gross_amount * rate)
    return _q(gross_amount - wht), wht


# ── Lookup helpers ───────────────────────────────────────────────────────────


async def get_active_tax_rate(
    db: AsyncSession,
    facility_id: uuid.UUID,
    tax_type: str,
) -> TaxRate | None:
    """
    Return the active tax rate matching ``tax_type``.

    @param db: Database session
    @param facility_id: Facility scope
    @param tax_type: vat_output | vat_input | withholding
    @returns TaxRate or None if no active rate configured
    """
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.facility_id == facility_id,
            TaxRate.tax_type == tax_type,
            TaxRate.is_active == True,  # noqa: E712
            TaxRate.is_deleted == False,  # noqa: E712
        )
    )
    return result.scalars().first()
