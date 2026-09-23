"""Pure-function Kenya statutory calculators.

All money is Decimal. No DB access. Rates are passed in as arguments,
NEVER hardcoded — they are loaded from the `paye_bands`, `nssf_tiers`,
and `statutory_rates` tables at runtime.

References (effective rates as of 2026):
    - PAYE: 5-band progressive (10/25/30/32.5/35)
    - NSSF: Tier I (0-9,000) + Tier II (9,001-108,000) @ 6%/6%
    - SHIF: 2.75% of gross
    - Housing Levy: 1.5% of gross
    - Personal relief: KSh 2,400/month
    - Insurance relief: 15% of premium, capped at KSh 5,000/month
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_ZERO = Decimal("0")
_TWO_PLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantise to 2 decimal places, ROUND_HALF_UP."""
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class NSSFTierSpec:
    """Plain-data NSSF tier descriptor (no DB dependency)."""

    tier: str
    lower_limit: Decimal
    upper_limit: Decimal
    employee_rate: Decimal
    employer_rate: Decimal


@dataclass(frozen=True)
class PAYEBandSpec:
    """Plain-data PAYE band descriptor (no DB dependency)."""

    lower_limit: Decimal
    upper_limit: Decimal | None  # None = open upper bound
    rate: Decimal


def calc_nssf(gross_salary: Decimal, tiers: list[NSSFTierSpec]) -> Decimal:
    """Calculate the employee NSSF contribution.

    The 2026 NSSF Act caps Tier II pensionable pay at KSh 108,000. The
    function sums each tier's employee_rate * the chunk of gross that
    falls inside that tier.

    @param gross_salary: Employee gross salary for the month (Decimal)
    @param tiers: Effective NSSF tier rows (Tier I and Tier II)
    @returns Employee NSSF contribution (Decimal, 2dp)
    """
    if gross_salary <= _ZERO or not tiers:
        return _ZERO
    total = _ZERO
    # Sort by lower_limit so Tier I is applied before Tier II
    for tier in sorted(tiers, key=lambda t: t.lower_limit):
        if gross_salary <= tier.lower_limit:
            continue
        chunk_top = min(gross_salary, tier.upper_limit)
        chunk = chunk_top - tier.lower_limit
        if chunk <= _ZERO:
            continue
        total += chunk * tier.employee_rate
    return _q(total)


def calc_employer_nssf(
    gross_salary: Decimal, tiers: list[NSSFTierSpec]
) -> Decimal:
    """Calculate the employer NSSF contribution (mirrors employee under the 2026 Act)."""
    if gross_salary <= _ZERO or not tiers:
        return _ZERO
    total = _ZERO
    for tier in sorted(tiers, key=lambda t: t.lower_limit):
        if gross_salary <= tier.lower_limit:
            continue
        chunk_top = min(gross_salary, tier.upper_limit)
        chunk = chunk_top - tier.lower_limit
        if chunk <= _ZERO:
            continue
        total += chunk * tier.employer_rate
    return _q(total)


def calc_paye(taxable_pay: Decimal, bands: list[PAYEBandSpec]) -> Decimal:
    """Calculate gross PAYE (before personal/insurance relief).

    Stepped progressive: each band taxes the chunk of taxable pay that
    falls inside that band at the band's rate.

    @param taxable_pay: Pay subject to tax after pension / SHIF / HL / disability
    @param bands: Effective PAYE bands ordered from lowest lower_limit upwards
    @returns Gross PAYE before relief (Decimal, 2dp)
    """
    if taxable_pay <= _ZERO or not bands:
        return _ZERO
    total = _ZERO
    sorted_bands = sorted(bands, key=lambda b: b.lower_limit)
    for band in sorted_bands:
        if taxable_pay <= band.lower_limit:
            break
        upper = band.upper_limit if band.upper_limit is not None else taxable_pay
        chunk_top = min(taxable_pay, upper)
        chunk = chunk_top - band.lower_limit
        if chunk <= _ZERO:
            continue
        total += chunk * band.rate
    return _q(total)


def calc_shif(
    gross_salary: Decimal, rate: Decimal = Decimal("0.0275")
) -> Decimal:
    """Social Health Insurance Fund: 2.75% of gross."""
    if gross_salary <= _ZERO:
        return _ZERO
    return _q(gross_salary * rate)


def calc_housing_levy(
    gross_salary: Decimal, rate: Decimal = Decimal("0.015")
) -> Decimal:
    """Affordable Housing Levy: 1.5% of gross (employee share)."""
    if gross_salary <= _ZERO:
        return _ZERO
    return _q(gross_salary * rate)


def calc_employer_housing_levy(
    gross_salary: Decimal, rate: Decimal = Decimal("0.015")
) -> Decimal:
    """Affordable Housing Levy: 1.5% of gross (employer share)."""
    if gross_salary <= _ZERO:
        return _ZERO
    return _q(gross_salary * rate)


def calc_insurance_relief(
    premiums: Decimal,
    rate: Decimal = Decimal("0.15"),
    cap: Decimal = Decimal("5000"),
) -> Decimal:
    """Insurance relief: 15% of premium, capped at KSh 5,000/month."""
    if premiums <= _ZERO:
        return _ZERO
    relief = premiums * rate
    if relief > cap:
        relief = cap
    return _q(relief)
