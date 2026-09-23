"""Consultation-fee resolution for front-desk (reception) collections.

A patient settles a consultation fee at reception before seeing a doctor. The
amount is resolved per facility with this precedence:

1. a per-doctor override
2. a per-department override
3. the facility-wide default

Overrides live in ``facilities.settings["consultation_fees"]``::

    {
      "consultation_fees": {
        "default_cents": 100000,
        "by_department": {"<department uuid>": 150000},
        "by_doctor": {"<staff uuid>": 200000}
      }
    }

A resolved amount of ``0`` disables automatic consultation invoicing, matching
the pre-existing behaviour of ``settings.consultation_fee_cents``. That legacy
key is still honoured as the default when the new block is absent.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Fallback consultation fee (KES 1,000.00 in cents) used when the facility has
# configured nothing at all.
DEFAULT_CONSULTATION_FEE_CENTS = 100000


def _as_cents(value: object) -> int | None:
    """
    Coerce a configured fee to a non-negative int.

    @param value: Raw value from facility settings
    @returns Fee in cents, or None when the value is unusable
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _lookup(mapping: object, key: str | None) -> int | None:
    """
    Read a fee override from a ``{key: cents}`` mapping.

    @param mapping: Configured override mapping
    @param key: Lookup key (UUID or code); skipped when None
    @returns Fee in cents, or None when unset
    """
    if not isinstance(mapping, dict) or not key:
        return None
    return _as_cents(mapping.get(key))


def resolve_consultation_fee_cents(
    settings: dict | None,
    *,
    department_id: uuid.UUID | str | None = None,
    doctor_id: uuid.UUID | str | None = None,
) -> int:
    """
    Resolve the consultation fee for a department / doctor combination.

    @param settings: Facility settings JSONB document
    @param department_id: Target department UUID (or code)
    @param doctor_id: Target doctor's staff UUID
    @returns Fee in KES cents
    """
    settings = settings or {}
    config = settings.get("consultation_fees")
    config = config if isinstance(config, dict) else {}

    doctor_key = str(doctor_id) if doctor_id else None
    department_key = str(department_id) if department_id else None

    override = _lookup(config.get("by_doctor"), doctor_key)
    if override is None:
        override = _lookup(config.get("by_department"), department_key)
    if override is not None:
        return override

    default = _as_cents(config.get("default_cents"))
    if default is None:
        default = _as_cents(settings.get("consultation_fee_cents"))
    if default is None:
        default = DEFAULT_CONSULTATION_FEE_CENTS
    return default


async def load_consultation_fee_cents(
    db: AsyncSession,
    facility_id: uuid.UUID,
    *,
    department_id: uuid.UUID | None = None,
    doctor_id: uuid.UUID | None = None,
) -> int:
    """
    Read facility settings and resolve the consultation fee.

    @param db: Database session
    @param facility_id: Facility UUID
    @param department_id: Target department UUID
    @param doctor_id: Target doctor's staff UUID
    @returns Fee in KES cents
    """
    from app.models.facility import Facility

    result = await db.execute(
        select(Facility.settings).where(Facility.id == facility_id)
    )
    return resolve_consultation_fee_cents(
        result.scalar_one_or_none(),
        department_id=department_id,
        doctor_id=doctor_id,
    )