"""Pure-function tests for the Kenya statutory calculators.

These tests only exercise app.services.payroll.statutory — no DB, no
fixtures required.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.payroll.statutory import (
    NSSFTierSpec,
    PAYEBandSpec,
    calc_employer_housing_levy,
    calc_employer_nssf,
    calc_housing_levy,
    calc_insurance_relief,
    calc_nssf,
    calc_paye,
    calc_shif,
)


# ── Test fixtures ──────────────────────────────────────────────────────────


def _nssf_tiers() -> list[NSSFTierSpec]:
    return [
        NSSFTierSpec(
            tier="I",
            lower_limit=Decimal("0"),
            upper_limit=Decimal("9000"),
            employee_rate=Decimal("0.06"),
            employer_rate=Decimal("0.06"),
        ),
        NSSFTierSpec(
            tier="II",
            lower_limit=Decimal("9000"),
            upper_limit=Decimal("108000"),
            employee_rate=Decimal("0.06"),
            employer_rate=Decimal("0.06"),
        ),
    ]


def _paye_bands() -> list[PAYEBandSpec]:
    return [
        PAYEBandSpec(Decimal("0"), Decimal("24000"), Decimal("0.10")),
        PAYEBandSpec(Decimal("24000"), Decimal("32333"), Decimal("0.25")),
        PAYEBandSpec(Decimal("32333"), Decimal("500000"), Decimal("0.30")),
        PAYEBandSpec(Decimal("500000"), Decimal("800000"), Decimal("0.325")),
        PAYEBandSpec(Decimal("800000"), None, Decimal("0.35")),
    ]


def _approx(actual: Decimal, expected: Decimal, tol: Decimal = Decimal("0.10")) -> bool:
    return abs(actual - expected) <= tol


# ── NSSF ───────────────────────────────────────────────────────────────────


def test_nssf_tier_i_only_when_gross_below_9000() -> None:
    """5,000 gross → 5,000 × 0.06 = 300 (Tier I only)."""
    assert calc_nssf(Decimal("5000"), _nssf_tiers()) == Decimal("300.00")


def test_nssf_tier_i_plus_partial_tier_ii() -> None:
    """50,000 gross → Tier I (9000) + Tier II (41000) all @ 6% = 3000."""
    assert calc_nssf(Decimal("50000"), _nssf_tiers()) == Decimal("3000.00")


def test_nssf_capped_at_max() -> None:
    """Above 108,000 gross → max 6,480 (= 108000 × 6%)."""
    assert calc_nssf(Decimal("200000"), _nssf_tiers()) == Decimal("6480.00")


def test_employer_nssf_mirrors_employee_under_2026_act() -> None:
    """Employer NSSF rate equals employee under 2026 Act."""
    assert calc_employer_nssf(
        Decimal("50000"), _nssf_tiers()
    ) == Decimal("3000.00")


def test_nssf_zero_gross() -> None:
    assert calc_nssf(Decimal("0"), _nssf_tiers()) == Decimal("0")


# ── PAYE ───────────────────────────────────────────────────────────────────


def test_paye_below_first_band() -> None:
    """Taxable 24,000 → 2,400 gross PAYE (10% on full chunk)."""
    assert calc_paye(Decimal("24000"), _paye_bands()) == Decimal("2400.00")


def test_paye_at_band2_boundary() -> None:
    """Taxable 32,333 → 2400 (band1) + 2083.25 (band2 chunk @25%) = 4483.25."""
    expected = Decimal("24000") * Decimal("0.10") + Decimal("8333") * Decimal("0.25")
    assert calc_paye(Decimal("32333"), _paye_bands()) == expected.quantize(Decimal("0.01"))


def test_paye_band3_chunk() -> None:
    """Taxable 100,000 → 2400 + 2083.25 + (100000-32333)*0.30 = 24,783.35."""
    expected = (
        Decimal("24000") * Decimal("0.10")
        + Decimal("8333") * Decimal("0.25")
        + (Decimal("100000") - Decimal("32333")) * Decimal("0.30")
    )
    assert calc_paye(Decimal("100000"), _paye_bands()) == expected.quantize(
        Decimal("0.01")
    )


def test_paye_band4_chunk() -> None:
    """Taxable 500,000 → fully through bands 1-3."""
    expected = (
        Decimal("24000") * Decimal("0.10")
        + Decimal("8333") * Decimal("0.25")
        + (Decimal("500000") - Decimal("32333")) * Decimal("0.30")
    )
    assert calc_paye(Decimal("500000"), _paye_bands()) == expected.quantize(
        Decimal("0.01")
    )


def test_paye_top_band() -> None:
    """Taxable 1,000,000 → bands 1-4 fully + (1M-800k)*0.35."""
    expected = (
        Decimal("24000") * Decimal("0.10")
        + Decimal("8333") * Decimal("0.25")
        + (Decimal("500000") - Decimal("32333")) * Decimal("0.30")
        + (Decimal("800000") - Decimal("500000")) * Decimal("0.325")
        + (Decimal("1000000") - Decimal("800000")) * Decimal("0.35")
    )
    assert calc_paye(Decimal("1000000"), _paye_bands()) == expected.quantize(
        Decimal("0.01")
    )


def test_paye_zero_taxable() -> None:
    assert calc_paye(Decimal("0"), _paye_bands()) == Decimal("0")


# ── SHIF / Housing Levy ────────────────────────────────────────────────────


def test_shif_default_rate() -> None:
    """100,000 gross @ 2.75% = 2,750.00."""
    assert calc_shif(Decimal("100000")) == Decimal("2750.00")


def test_shif_zero() -> None:
    assert calc_shif(Decimal("0")) == Decimal("0")


def test_housing_levy_default_rate() -> None:
    """100,000 gross @ 1.5% = 1,500.00."""
    assert calc_housing_levy(Decimal("100000")) == Decimal("1500.00")


def test_employer_housing_levy_default_rate() -> None:
    """Employer HL = 1.5% of gross."""
    assert calc_employer_housing_levy(Decimal("100000")) == Decimal("1500.00")


# ── Insurance relief ───────────────────────────────────────────────────────


def test_insurance_relief_15pct_below_cap() -> None:
    """Premium 10,000 → 1,500 relief (under 5,000 cap)."""
    assert calc_insurance_relief(Decimal("10000")) == Decimal("1500.00")


def test_insurance_relief_capped_at_5000() -> None:
    """Premium 50,000 → relief capped at 5,000."""
    assert calc_insurance_relief(Decimal("50000")) == Decimal("5000.00")


def test_insurance_relief_zero_premium() -> None:
    assert calc_insurance_relief(Decimal("0")) == Decimal("0")


# ── Mark Kamau worked example ──────────────────────────────────────────────


def test_mark_kamau_worked_example() -> None:
    """Spec sheet check: gross 112,507 — pre-relief PAYE.

    Tolerances allow ±10c for SHIF/taxable rounding differences.
    """
    gross = Decimal("112507")
    tiers = _nssf_tiers()
    bands = _paye_bands()

    nssf = calc_nssf(gross, tiers)
    shif = calc_shif(gross)
    hl = calc_housing_levy(gross)

    assert nssf == Decimal("6480.00")
    assert _approx(shif, Decimal("3094.00"))
    assert _approx(hl, Decimal("1687.61"))

    taxable = gross - nssf - shif - hl
    assert _approx(taxable, Decimal("101245.40"))

    gross_paye = calc_paye(taxable, bands)
    # Spec: 25,156.97. Tolerate ±2 KES due to band-edge rounding.
    assert _approx(gross_paye, Decimal("25156.97"), tol=Decimal("2.00"))

    paye = gross_paye - Decimal("2400")
    assert _approx(paye, Decimal("22756.97"), tol=Decimal("2.00"))


# ── Disability exemption ───────────────────────────────────────────────────


def test_disability_exemption_reduces_taxable_pay() -> None:
    """A 200,000 gross with 150,000 disability exemption → much smaller PAYE."""
    gross = Decimal("200000")
    nssf = calc_nssf(gross, _nssf_tiers())
    shif = calc_shif(gross)
    hl = calc_housing_levy(gross)

    taxable_no_ex = gross - nssf - shif - hl
    taxable_with_ex = taxable_no_ex - Decimal("150000")
    assert taxable_with_ex < taxable_no_ex
    assert calc_paye(taxable_with_ex, _paye_bands()) < calc_paye(
        taxable_no_ex, _paye_bands()
    )


# ── Edge case: empty band list ─────────────────────────────────────────────


def test_paye_empty_bands_returns_zero() -> None:
    assert calc_paye(Decimal("100000"), []) == Decimal("0")


def test_nssf_empty_tiers_returns_zero() -> None:
    assert calc_nssf(Decimal("100000"), []) == Decimal("0")
