"""
Lab test catalog service (D6): default seed, search, and price lookup.

The catalog is the authoritative source of orderable tests and their managed
prices, so lab charges reach the patient invoice consistently (D2).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab import LabTestCatalog

# (test_code, test_name, specimen_type, price_cents). Prices are KES cents;
# adjust per facility via the catalog API. Malaria RDT at KES 200 matches the
# QA reproduction.
DEFAULT_LAB_TESTS: list[tuple[str, str, str, int]] = [
    ("MRDT", "Malaria RDT", "blood", 20_000),
    ("MPS", "Malaria Microscopy (BS for MPS)", "blood", 30_000),
    ("CBC", "Complete Blood Count", "blood", 50_000),
    ("HB", "Haemoglobin", "blood", 15_000),
    ("RBS", "Random Blood Sugar", "blood", 15_000),
    ("UECS", "Urea / Electrolytes / Creatinine", "blood", 80_000),
    ("LFT", "Liver Function Test", "blood", 90_000),
    ("URINALYSIS", "Urinalysis", "urine", 20_000),
    ("STOOL", "Stool Ova & Cysts", "stool", 20_000),
    ("BLOODGROUP", "Blood Grouping", "blood", 30_000),
    ("WIDAL", "Widal Test", "blood", 40_000),
    ("HIV", "HIV Rapid Test", "blood", 0),
]


async def seed_default_lab_catalog(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> int:
    """
    Seed the default lab-test catalog for a facility. Idempotent — existing
    test codes are left untouched.

    @param db: Database session
    @param facility_id: Facility scope
    @param user_id: Creator
    @returns Number of catalog rows created
    """
    existing = (
        await db.execute(
            select(LabTestCatalog.test_code).where(
                LabTestCatalog.facility_id == facility_id
            )
        )
    ).scalars().all()
    have = set(existing)

    created = 0
    for code, name, specimen, price in DEFAULT_LAB_TESTS:
        if code in have:
            continue
        db.add(
            LabTestCatalog(
                facility_id=facility_id,
                test_code=code,
                test_name=name,
                specimen_type=specimen,
                price_cents=price,
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created


async def get_catalog_by_codes(
    db: AsyncSession, facility_id: uuid.UUID, codes: list[str]
) -> dict[str, LabTestCatalog]:
    """
    Resolve catalog rows for a set of test codes.

    @param db: Database session
    @param facility_id: Facility scope
    @param codes: Test codes to resolve
    @returns Map of test_code -> catalog row (only codes that exist)
    """
    if not codes:
        return {}
    rows = (
        await db.execute(
            select(LabTestCatalog).where(
                LabTestCatalog.facility_id == facility_id,
                LabTestCatalog.test_code.in_(codes),
                LabTestCatalog.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    return {r.test_code: r for r in rows}


async def search_catalog(
    db: AsyncSession, facility_id: uuid.UUID, query: str | None, limit: int = 20
) -> list[LabTestCatalog]:
    """
    Type-ahead search over the catalog by code or name.

    @param db: Database session
    @param facility_id: Facility scope
    @param query: Optional search term (code or name)
    @param limit: Max rows
    @returns Matching active catalog rows
    """
    stmt = select(LabTestCatalog).where(
        LabTestCatalog.facility_id == facility_id,
        LabTestCatalog.is_active == True,  # noqa: E712
        LabTestCatalog.is_deleted == False,  # noqa: E712
    )
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            func.lower(LabTestCatalog.test_code).like(like)
            | func.lower(LabTestCatalog.test_name).like(like)
        )
    stmt = stmt.order_by(LabTestCatalog.test_name.asc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
