"""Antenatal care (ANC) visit pricing.

Every ANC visit is a service the maternal clinic renders, so the encounter's
bill itemises it instead of folding it into a lump sum. Prices are resolved per
facility from facilities.settings["anc_visit_fees"]:

    {
      "anc_visit_fees": {
        "default_cents": 20000,
        "by_risk_level": {"high": 0},
        "enforce_payment": false
      }
    }

Precedence: risk level -> facility default -> built-in default. A resolved
price of 0 means the visit is not charged (free antenatal care, or ANC billing
switched off), so no line ever reaches the bill. ``enforce_payment`` only
decides whether an outstanding ANC balance blocks a further visit while the
encounter is still open; it never invents a charge of its own.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

#: Built-in fee for one ANC visit when the facility configures nothing (KES 200).
DEFAULT_ANC_VISIT_FEE_CENTS = 20_000


def _as_cents(value: object) -> int | None:
    """
    Coerce a configured price to a non-negative int.

    @param value: Raw value from facility settings
    @returns Price in cents, or None when the value is unusable
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _as_bool(value: object) -> bool | None:
    """
    Coerce a configured switch to a bool.

    @param value: Raw value from facility settings
    @returns The boolean, or None when the value is unusable
    """
    if isinstance(value, bool):
        return value
    return None


def _anc_config(settings: dict | None) -> dict:
    """
    Read the ANC fee block out of a facility's settings document.

    @param settings: Facility settings JSONB document
    @returns The configuration mapping, or an empty mapping
    """
    settings = settings or {}
    config = settings.get("anc_visit_fees")
    return config if isinstance(config, dict) else {}


def resolve_anc_visit_fee_cents(
    settings: dict | None, *, risk_level: str | None = None
) -> int:
    """
    Resolve the fee for one ANC visit.

    @param settings: Facility settings JSONB document
    @param risk_level: The profile's current risk level, e.g. high
    @returns Price in KES cents; 0 when the visit is not charged
    """
    config = _anc_config(settings)
    by_risk = config.get("by_risk_level")
    if isinstance(by_risk, dict) and risk_level:
        override = _as_cents(by_risk.get(risk_level))
        if override is not None:
            return override
    configured = _as_cents(config.get("default_cents"))
    if configured is not None:
        return configured
    return DEFAULT_ANC_VISIT_FEE_CENTS


def resolve_anc_visit_enforce_payment(settings: dict | None) -> bool:
    """
    Whether an unpaid ANC balance blocks a further visit.

    @param settings: Facility settings JSONB document
    @returns True when the facility enforces ANC payment
    """
    return _as_bool(_anc_config(settings).get("enforce_payment")) is True


async def load_anc_visit_fee_cents(
    db: AsyncSession, facility_id: uuid.UUID, *, risk_level: str | None = None
) -> int:
    """
    Read facility settings and resolve an ANC visit price.

    @param db: Database session
    @param facility_id: Facility UUID
    @param risk_level: The profile's current risk level
    @returns Price in KES cents
    """
    from app.models.facility import Facility

    result = await db.execute(
        select(Facility.settings).where(Facility.id == facility_id)
    )
    return resolve_anc_visit_fee_cents(
        result.scalar_one_or_none(), risk_level=risk_level
    )


async def load_anc_visit_enforce_payment(
    db: AsyncSession, facility_id: uuid.UUID
) -> bool:
    """
    Read facility settings and report whether ANC payment is enforced.

    @param db: Database session
    @param facility_id: Facility UUID
    @returns True when the facility enforces ANC payment
    """
    from app.models.facility import Facility

    result = await db.execute(
        select(Facility.settings).where(Facility.id == facility_id)
    )
    return resolve_anc_visit_enforce_payment(result.scalar_one_or_none())
