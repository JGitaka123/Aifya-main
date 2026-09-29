"""Point-of-care test pricing for OPD point-of-sale collection.

A nurse runs screening tests (malaria RDT, urinalysis, HIV, pregnancy, blood
glucose, hepatitis B) in the OPD room. Those tests are part of the visit, so
the bill and the receipt handed to the patient must itemise what was actually
run rather than show a single lump sum.

Prices are resolved per facility from facilities.settings["point_of_care_prices"]:

    {
      "point_of_care_prices": {
        "default_cents": 20000,
        "by_test_code": {"MRDT": 20000, "HIV": 0}
      }
    }

Precedence: exact test code -> facility default -> built-in test default ->
built-in fallback. A resolved price of 0 means the test is not charged (a free
screening, or point-of-care billing switched off), so the line never reaches
the bill and the patient is never surprised at the desk.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Built-in defaults (KES cents) for the tests the OPD panel offers. HIV
# screening is free, matching the lab catalogue default; the rest mirror the
# point-of-care tests the laboratory prices.
DEFAULT_TEST_PRICES_CENTS: dict[str, int] = {
    "HIV": 0,
    "MRDT": 20_000,
    "URIN": 20_000,
    "PREG": 20_000,
    "GLU": 15_000,
    "HBSAG": 30_000,
}

# Custom or unlisted tests are not charged unless the facility prices them.
DEFAULT_FALLBACK_CENTS = 0


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
    Read an override price from a code-to-cents mapping.

    @param mapping: Configured override mapping
    @param key: Test code to look up
    @returns Price in cents, or None when unset
    """
    if not isinstance(mapping, dict) or not key:
        return None
    return _as_cents(mapping.get(key))


def resolve_point_of_care_price_cents(
    settings: dict | None, *, test_code: str | None
) -> int:
    """
    Resolve the price of one point-of-care test.

    @param settings: Facility settings JSONB document
    @param test_code: Test code the OPD panel sent, e.g. MRDT
    @returns Price in KES cents
    """
    settings = settings or {}
    config = settings.get("point_of_care_prices")
    config = config if isinstance(config, dict) else {}

    raw_key = (test_code or "").strip() or None
    code_key = raw_key.upper() if raw_key else None

    price = _lookup(config.get("by_test_code"), raw_key)
    if price is None:
        price = _lookup(config.get("by_test_code"), code_key)
    if price is None:
        price = _as_cents(config.get("default_cents"))
    if price is None:
        price = DEFAULT_TEST_PRICES_CENTS.get(
            code_key or "", DEFAULT_FALLBACK_CENTS
        )
    return price


async def load_point_of_care_price_cents(
    db: AsyncSession, facility_id: uuid.UUID, *, test_code: str | None
) -> int:
    """
    Read facility settings and resolve a point-of-care test price.

    @param db: Database session
    @param facility_id: Facility UUID
    @param test_code: Test code the OPD panel sent
    @returns Price in KES cents
    """
    from app.models.facility import Facility

    result = await db.execute(
        select(Facility.settings).where(Facility.id == facility_id)
    )
    return resolve_point_of_care_price_cents(
        result.scalar_one_or_none(), test_code=test_code
    )
