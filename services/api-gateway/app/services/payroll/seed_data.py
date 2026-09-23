"""Seed Kenya statutory rates and default leave types.

Idempotent: skips rows that already exist (by category + effective_from).
Run once at deployment / Alembic post-migrate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import NSSFTier, PAYEBand, StatutoryRate
from app.models.payroll_extra import LeaveType

# ── Effective dates ──────────────────────────────────────────────────────────
PAYE_EFFECTIVE_FROM = date(2023, 7, 1)
NSSF_EFFECTIVE_FROM = date(2026, 2, 1)
RATE_EFFECTIVE_FROM = date(2024, 10, 1)


# ── PAYE bands (2023-07-01 onward) ──────────────────────────────────────────
PAYE_BAND_DEFAULTS: list[dict[str, Decimal | None]] = [
    {"lower_limit": Decimal("0"), "upper_limit": Decimal("24000"), "rate": Decimal("0.10")},
    {"lower_limit": Decimal("24000"), "upper_limit": Decimal("32333"), "rate": Decimal("0.25")},
    {"lower_limit": Decimal("32333"), "upper_limit": Decimal("500000"), "rate": Decimal("0.30")},
    {"lower_limit": Decimal("500000"), "upper_limit": Decimal("800000"), "rate": Decimal("0.325")},
    {"lower_limit": Decimal("800000"), "upper_limit": None, "rate": Decimal("0.35")},
]

# ── NSSF tiers (2026 Act) ───────────────────────────────────────────────────
NSSF_TIER_DEFAULTS: list[dict[str, Decimal | str]] = [
    {
        "tier": "I",
        "lower_limit": Decimal("0"),
        "upper_limit": Decimal("9000"),
        "employee_rate": Decimal("0.06"),
        "employer_rate": Decimal("0.06"),
    },
    {
        "tier": "II",
        "lower_limit": Decimal("9000"),
        "upper_limit": Decimal("108000"),
        "employee_rate": Decimal("0.06"),
        "employer_rate": Decimal("0.06"),
    },
]

# ── Statutory rates ─────────────────────────────────────────────────────────
STATUTORY_RATE_DEFAULTS: list[dict[str, Decimal | str | None]] = [
    {
        "name": "Personal Relief",
        "category": "relief",
        "rate": None,
        "fixed_amount": Decimal("2400"),
        "fixed_cap": None,
    },
    {
        "name": "SHIF",
        "category": "shif",
        "rate": Decimal("0.0275"),
        "fixed_amount": None,
        "fixed_cap": None,
    },
    {
        "name": "Housing Levy",
        "category": "housing_levy",
        "rate": Decimal("0.015"),
        "fixed_amount": None,
        "fixed_cap": None,
    },
    {
        "name": "Insurance Relief",
        "category": "relief",
        "rate": Decimal("0.15"),
        "fixed_amount": None,
        "fixed_cap": Decimal("5000"),
    },
]

# ── Default leave types ─────────────────────────────────────────────────────
LEAVE_TYPE_DEFAULTS: list[dict[str, str | int | bool | None]] = [
    {
        "name": "Annual",
        "days_entitlement": 21,
        "paid": True,
        "partial_pay": False,
        "carries_over": True,
        "max_carryover": 10,
        "notes": "21 working days; up to 10 may carry over.",
    },
    {
        "name": "Sick",
        "days_entitlement": 14,
        "paid": True,
        "partial_pay": True,
        "carries_over": False,
        "max_carryover": None,
        "notes": "First 7 days full pay, next 7 days half pay.",
    },
    {
        "name": "Maternity",
        "days_entitlement": 90,
        "paid": True,
        "partial_pay": False,
        "carries_over": False,
        "max_carryover": None,
        "notes": "Per Employment Act.",
    },
    {
        "name": "Paternity",
        "days_entitlement": 14,
        "paid": True,
        "partial_pay": False,
        "carries_over": False,
        "max_carryover": None,
        "notes": "Per Employment Act.",
    },
    {
        "name": "Compassionate",
        "days_entitlement": 3,
        "paid": True,
        "partial_pay": False,
        "carries_over": False,
        "max_carryover": None,
        "notes": "Bereavement.",
    },
    {
        "name": "Study",
        "days_entitlement": 0,
        "paid": False,
        "partial_pay": False,
        "carries_over": False,
        "max_carryover": None,
        "notes": "As approved by HR.",
    },
    {
        "name": "Unpaid",
        "days_entitlement": 0,
        "paid": False,
        "partial_pay": False,
        "carries_over": False,
        "max_carryover": None,
        "notes": "Unpaid leave: deducts daily rate from payroll.",
    },
]


async def seed_payroll_defaults(db: AsyncSession) -> None:
    """Idempotently seed global statutory rates and default leave types.

    @param db: SQLAlchemy async session (caller commits)
    @returns None
    """
    # PAYE bands
    existing_paye = (
        await db.execute(
            select(PAYEBand).where(
                PAYEBand.facility_id.is_(None),
                PAYEBand.effective_from == PAYE_EFFECTIVE_FROM,
            )
        )
    ).scalars().first()
    if existing_paye is None:
        for band in PAYE_BAND_DEFAULTS:
            db.add(
                PAYEBand(
                    facility_id=None,
                    lower_limit=band["lower_limit"],
                    upper_limit=band["upper_limit"],
                    rate=band["rate"],
                    effective_from=PAYE_EFFECTIVE_FROM,
                )
            )

    # NSSF tiers
    existing_nssf = (
        await db.execute(
            select(NSSFTier).where(
                NSSFTier.facility_id.is_(None),
                NSSFTier.effective_from == NSSF_EFFECTIVE_FROM,
            )
        )
    ).scalars().first()
    if existing_nssf is None:
        for tier in NSSF_TIER_DEFAULTS:
            db.add(
                NSSFTier(
                    facility_id=None,
                    tier=tier["tier"],
                    lower_limit=tier["lower_limit"],
                    upper_limit=tier["upper_limit"],
                    employee_rate=tier["employee_rate"],
                    employer_rate=tier["employer_rate"],
                    effective_from=NSSF_EFFECTIVE_FROM,
                )
            )

    # Statutory rates
    for rate_def in STATUTORY_RATE_DEFAULTS:
        existing = (
            await db.execute(
                select(StatutoryRate).where(
                    StatutoryRate.facility_id.is_(None),
                    StatutoryRate.category == rate_def["category"],
                    StatutoryRate.name == rate_def["name"],
                    StatutoryRate.effective_from == RATE_EFFECTIVE_FROM,
                )
            )
        ).scalars().first()
        if existing is None:
            db.add(
                StatutoryRate(
                    facility_id=None,
                    name=rate_def["name"],
                    category=rate_def["category"],
                    rate=rate_def["rate"],
                    fixed_amount=rate_def["fixed_amount"],
                    fixed_cap=rate_def["fixed_cap"],
                    effective_from=RATE_EFFECTIVE_FROM,
                )
            )

    # Leave types
    for lt in LEAVE_TYPE_DEFAULTS:
        existing_lt = (
            await db.execute(
                select(LeaveType).where(
                    LeaveType.facility_id.is_(None),
                    LeaveType.name == lt["name"],
                )
            )
        ).scalars().first()
        if existing_lt is None:
            db.add(
                LeaveType(
                    facility_id=None,
                    name=lt["name"],
                    days_entitlement=lt["days_entitlement"],
                    paid=lt["paid"],
                    partial_pay=lt["partial_pay"],
                    carries_over=lt["carries_over"],
                    max_carryover=lt["max_carryover"],
                    notes=lt["notes"],
                )
            )

    await db.flush()
