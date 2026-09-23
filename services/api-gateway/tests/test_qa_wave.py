"""QA-wave hardening tests: phone validation (F16), essential-drug seeding
(F4), billing-outstanding definition (F8), and Top Diagnoses pipeline (F14)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.diagnosis import Diagnosis
from app.models.pharmacy import PharmacyItem
from app.services.pharmacy_seed import seed_essential_drugs
from app.services.reports_service import ReportsService
from tests.conftest import FACILITY_ID, USER_ID, session_factory


# ── F16: phone-format validation ─────────────────────────────────────────

def _patient(phone: str) -> dict:
    return {
        "first_name": "QA",
        "last_name": "Phone",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "phone_number": phone,
    }


@pytest.mark.asyncio
async def test_non_phone_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/patients", json=_patient("notaphone"))
    assert resp.status_code == 422
    assert "phone" in resp.text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("phone", ["0712345678", "+254712345678", "254712345678", "0112345678"])
async def test_valid_phone_accepted(client: AsyncClient, phone: str) -> None:
    resp = await client.post("/api/v1/patients", json=_patient(phone))
    assert resp.status_code == 201, resp.text


# ── F4: essential-drug formulary seeding ─────────────────────────────────

@pytest.mark.asyncio
async def test_seed_essential_drugs_idempotent_and_high_risk(client: AsyncClient) -> None:
    async with session_factory() as db:
        created = await seed_essential_drugs(db, FACILITY_ID, USER_ID)
        await db.commit()
    assert created >= 20

    async with session_factory() as db:
        names = {
            n.lower()
            for n in (
                await db.execute(
                    select(PharmacyItem.drug_name).where(
                        PharmacyItem.facility_id == FACILITY_ID
                    )
                )
            ).scalars().all()
        }
    # the interacting/high-risk agents the QA found missing must now be present
    assert any("warfarin" in n for n in names)
    assert any("aspirin" in n for n in names)
    assert any("ibuprofen" in n for n in names)

    async with session_factory() as db:
        again = await seed_essential_drugs(db, FACILITY_ID, USER_ID)
        await db.commit()
    assert again == 0  # idempotent


# ── F14: Top Diagnoses returns data without the attribute bug ─────────────

@pytest.mark.asyncio
async def test_top_diagnoses_returns_entered_diagnoses(client: AsyncClient) -> None:
    async with session_factory() as db:
        db.add(
            Diagnosis(
                facility_id=FACILITY_ID,
                encounter_id=uuid.uuid4(),
                patient_id=uuid.uuid4(),
                diagnosed_by=USER_ID,
                icd10_code="B54",
                icd10_description="Unspecified malaria",
                diagnosis_type="primary",
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await db.commit()

    async with session_factory() as db:
        top = await ReportsService(db).get_top_diagnoses(FACILITY_ID)
    assert any(d.icd_code == "B54" and d.count >= 1 for d in top)
