"""Imaging (radiology) study pricing for point-of-sale collection.

Study prices are resolved per facility from facilities.settings["imaging_prices"]:

    {
      "imaging_prices": {
        "default_cents": 200000,
        "by_modality": {"xray": 150000, "ct": 900000},
        "by_study": {"chest x-ray pa": 150000}
      }
    }

Precedence: exact study description -> modality -> facility default ->
built-in modality default -> built-in fallback. A resolved price of 0 means the
study is not charged, so a facility can switch imaging billing off.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Built-in defaults (KES cents) used when the facility configured nothing.
DEFAULT_FALLBACK_CENTS = 200_000
DEFAULT_MODALITY_PRICES_CENTS: dict[str, int] = {
    "ecg": 100_000,
    "echo": 350_000,
    "xray": 150_000,
    "ultrasound": 200_000,
    "mammography": 500_000,
    "fluoroscopy": 600_000,
    "ct": 900_000,
    "mri": 1_500_000,
}


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


def _lookup(mapping: object, key: str | None) -> int | None:
    """
    Read an override price from a key-to-cents mapping.

    @param mapping: Configured override mapping
    @param key: Lookup key (modality or normalised study description)
    @returns Price in cents, or None when unset
    """
    if not isinstance(mapping, dict) or not key:
        return None
    return _as_cents(mapping.get(key))


def resolve_imaging_price_cents(
    settings: dict | None,
    *,
    modality: str | None,
    study_description: str | None = None,
) -> int:
    """
    Resolve the price of an imaging study.

    @param settings: Facility settings JSONB document
    @param modality: Study modality (xray, ct, mri, ...)
    @param study_description: Free-text study name as ordered
    @returns Price in KES cents
    """
    settings = settings or {}
    config = settings.get("imaging_prices")
    config = config if isinstance(config, dict) else {}

    modality_key = (modality or "").strip().lower() or None
    study_key = (study_description or "").strip().lower() or None

    price = _lookup(config.get("by_study"), study_key)
    if price is None:
        price = _lookup(config.get("by_modality"), modality_key)
    if price is None:
        price = _as_cents(config.get("default_cents"))
    if price is None:
        price = DEFAULT_MODALITY_PRICES_CENTS.get(
            modality_key or "", DEFAULT_FALLBACK_CENTS
        )
    return price


async def load_imaging_price_cents(
    db: AsyncSession,
    facility_id: uuid.UUID,
    *,
    modality: str | None,
    study_description: str | None = None,
) -> int:
    """
    Read facility settings and resolve an imaging study price.

    @param db: Database session
    @param facility_id: Facility UUID
    @param modality: Study modality
    @param study_description: Free-text study name as ordered
    @returns Price in KES cents
    """
    from app.models.facility import Facility

    result = await db.execute(
        select(Facility.settings).where(Facility.id == facility_id)
    )
    return resolve_imaging_price_cents(
        result.scalar_one_or_none(),
        modality=modality,
        study_description=study_description,
    )
