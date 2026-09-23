"""Seed an essential-medicines formulary for a facility (QA F4).

Drug-drug interaction and allergy checking can only help clinicians if the
interacting/high-risk drugs are actually in the formulary and therefore
prescribable. The QA sweep found warfarin, aspirin, ibuprofen and other common
agents absent, so the canonical interacting pairs could not even be entered.

This idempotent seed provisions a curated Kenya Essential Medicines List (KEML)
subset — deliberately including the agents the CDS interaction engine knows
(warfarin, aspirin, ibuprofen, diclofenac, fluconazole, digoxin, tramadol, …)
plus common outpatient drugs — each with an opening stock batch so it is both
prescribable and dispensable. Safe to re-run.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pharmacy import PharmacyBatch, PharmacyItem

# code, name, generic, form, strength, unit, keml, buy_cents, sell_cents, stock
_ESSENTIAL_DRUGS: list[dict] = [
    # High-risk / interacting agents the CDS engine recognises (QA F4)
    {"code": "WARF-5", "name": "Warfarin 5mg", "generic": "Warfarin", "form": "tablet", "strength": "5mg", "uom": "tablet", "keml": True, "buy": 300, "sell": 800, "stock": 200},
    {"code": "ASP-75", "name": "Aspirin 75mg", "generic": "Acetylsalicylic acid", "form": "tablet", "strength": "75mg", "uom": "tablet", "keml": True, "buy": 100, "sell": 300, "stock": 500},
    {"code": "IBU-400", "name": "Ibuprofen 400mg", "generic": "Ibuprofen", "form": "tablet", "strength": "400mg", "uom": "tablet", "keml": True, "buy": 150, "sell": 400, "stock": 500},
    {"code": "DICLO-50", "name": "Diclofenac 50mg", "generic": "Diclofenac", "form": "tablet", "strength": "50mg", "uom": "tablet", "keml": True, "buy": 120, "sell": 350, "stock": 400},
    {"code": "FLUCO-150", "name": "Fluconazole 150mg", "generic": "Fluconazole", "form": "capsule", "strength": "150mg", "uom": "capsule", "keml": True, "buy": 400, "sell": 900, "stock": 150},
    {"code": "DIGO-0025", "name": "Digoxin 0.25mg", "generic": "Digoxin", "form": "tablet", "strength": "0.25mg", "uom": "tablet", "keml": True, "buy": 200, "sell": 500, "stock": 100},
    {"code": "TRAM-50", "name": "Tramadol 50mg", "generic": "Tramadol", "form": "capsule", "strength": "50mg", "uom": "capsule", "keml": True, "buy": 250, "sell": 600, "stock": 200},
    {"code": "AMLO-5", "name": "Amlodipine 5mg", "generic": "Amlodipine", "form": "tablet", "strength": "5mg", "uom": "tablet", "keml": True, "buy": 150, "sell": 400, "stock": 400},
    # Common outpatient formulary (weight-dosed paediatric agents included)
    {"code": "PARA-500", "name": "Paracetamol 500mg", "generic": "Paracetamol", "form": "tablet", "strength": "500mg", "uom": "tablet", "keml": True, "buy": 50, "sell": 200, "stock": 1000},
    {"code": "PARA-SYR", "name": "Paracetamol syrup 120mg/5ml", "generic": "Paracetamol", "form": "syrup", "strength": "120mg/5ml", "uom": "ml", "keml": True, "buy": 8000, "sell": 15000, "stock": 100},
    {"code": "AMOX-500", "name": "Amoxicillin 500mg", "generic": "Amoxicillin", "form": "capsule", "strength": "500mg", "uom": "capsule", "keml": True, "buy": 100, "sell": 300, "stock": 800},
    {"code": "AMOX-SUS", "name": "Amoxicillin suspension 125mg/5ml", "generic": "Amoxicillin", "form": "suspension", "strength": "125mg/5ml", "uom": "ml", "keml": True, "buy": 9000, "sell": 18000, "stock": 80},
    {"code": "METRO-400", "name": "Metronidazole 400mg", "generic": "Metronidazole", "form": "tablet", "strength": "400mg", "uom": "tablet", "keml": True, "buy": 80, "sell": 250, "stock": 600},
    {"code": "AZI-500", "name": "Azithromycin 500mg", "generic": "Azithromycin", "form": "tablet", "strength": "500mg", "uom": "tablet", "keml": True, "buy": 400, "sell": 900, "stock": 200},
    {"code": "CEFT-1G", "name": "Ceftriaxone 1g injection", "generic": "Ceftriaxone", "form": "injection", "strength": "1g", "uom": "vial", "keml": True, "buy": 6000, "sell": 12000, "stock": 100},
    {"code": "AL-2020", "name": "Artemether-Lumefantrine 20/120mg", "generic": "Artemether-Lumefantrine", "form": "tablet", "strength": "20/120mg", "uom": "tablet", "keml": True, "buy": 300, "sell": 700, "stock": 600},
    {"code": "COTRI-960", "name": "Cotrimoxazole 960mg", "generic": "Cotrimoxazole", "form": "tablet", "strength": "960mg", "uom": "tablet", "keml": True, "buy": 90, "sell": 250, "stock": 500},
    {"code": "ORS-1", "name": "Oral Rehydration Salts", "generic": "ORS", "form": "sachet", "strength": "20.5g", "uom": "sachet", "keml": True, "buy": 1500, "sell": 3000, "stock": 400},
    {"code": "ZINC-20", "name": "Zinc sulphate 20mg", "generic": "Zinc sulphate", "form": "tablet", "strength": "20mg", "uom": "tablet", "keml": True, "buy": 60, "sell": 200, "stock": 400},
    {"code": "OMEP-20", "name": "Omeprazole 20mg", "generic": "Omeprazole", "form": "capsule", "strength": "20mg", "uom": "capsule", "keml": True, "buy": 150, "sell": 400, "stock": 400},
    {"code": "METF-500", "name": "Metformin 500mg", "generic": "Metformin", "form": "tablet", "strength": "500mg", "uom": "tablet", "keml": True, "buy": 100, "sell": 300, "stock": 500},
    {"code": "ENAL-5", "name": "Enalapril 5mg", "generic": "Enalapril", "form": "tablet", "strength": "5mg", "uom": "tablet", "keml": True, "buy": 120, "sell": 350, "stock": 400},
    {"code": "HCTZ-25", "name": "Hydrochlorothiazide 25mg", "generic": "Hydrochlorothiazide", "form": "tablet", "strength": "25mg", "uom": "tablet", "keml": True, "buy": 90, "sell": 250, "stock": 400},
    {"code": "SALB-INH", "name": "Salbutamol inhaler 100mcg", "generic": "Salbutamol", "form": "inhaler", "strength": "100mcg", "uom": "inhaler", "keml": True, "buy": 25000, "sell": 45000, "stock": 60},
    {"code": "PRED-5", "name": "Prednisolone 5mg", "generic": "Prednisolone", "form": "tablet", "strength": "5mg", "uom": "tablet", "keml": True, "buy": 80, "sell": 250, "stock": 400},
]


async def seed_essential_drugs(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> int:
    """
    Ensure a facility's formulary contains the essential/high-risk drugs
    (idempotent). Each new drug gets an opening stock batch so it is both
    prescribable and dispensable.

    @param db: Async database session
    @param facility_id: Facility to seed
    @param user_id: Actor recorded on created rows
    @returns Number of drugs newly created
    """
    result = await db.execute(
        select(PharmacyItem.drug_code).where(
            PharmacyItem.facility_id == facility_id,
            PharmacyItem.is_deleted == False,  # noqa: E712
        )
    )
    existing = {row[0] for row in result.all()}
    expiry = date.today() + timedelta(days=365)

    created = 0
    for spec in _ESSENTIAL_DRUGS:
        if spec["code"] in existing:
            continue
        item = PharmacyItem(
            facility_id=facility_id,
            drug_code=spec["code"],
            drug_name=spec["name"],
            generic_name=spec["generic"],
            is_keml=spec["keml"],
            dosage_form=spec["form"],
            strength=spec["strength"],
            current_quantity=spec["stock"],
            unit_of_measure=spec["uom"],
            reorder_level=max(10, spec["stock"] // 10),
            buying_price_cents=spec["buy"],
            selling_price_cents=spec["sell"],
            expiry_date=expiry,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(item)
        await db.flush()  # need item.id for the opening batch
        db.add(
            PharmacyBatch(
                facility_id=facility_id,
                pharmacy_item_id=item.id,
                batch_number=f"OPEN-{spec['code']}",
                expiry_date=expiry,
                quantity_received=spec["stock"],
                quantity_remaining=spec["stock"],
                unit_cost_cents=spec["buy"],
                created_by=user_id,
                updated_by=user_id,
            )
        )
        created += 1

    if created:
        await db.flush()
    return created
