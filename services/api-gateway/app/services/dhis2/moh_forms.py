"""
Kenya MOH register report generators.
Generates standard MOH forms from Aifya clinical data:
  - MOH 705A: Outpatient Morbidity Summary (daily/monthly)
  - MOH 705B: Inpatient Morbidity Summary
  - MOH 710: Immunization Report
  - MOH 711: Integrated RH/HIV/TB/Malaria Summary
  - MOH 713: Lab Summary
  - MOH 718: Maternity Register Summary

All queries scoped by facility_id for multi-tenant safety.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.ipd import Admission
from app.models.lab import LabOrder, LabResult
from app.models.mch import ANCProfile, DeliveryRecord, Immunization
from app.models.patient import Patient

# ── MOH 705A — Outpatient Morbidity Summary ─────────────────────────────────


async def generate_moh_705a(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 705A — OPD disease summary grouped by ICD-10, age band, and sex.

    @param db: Async database session
    @param facility_id: Facility UUID (multi-tenant scope)
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with rows (diagnoses by age/sex), summary, metadata
    """
    result = await db.execute(
        select(
            Diagnosis.icd10_code,
            Diagnosis.icd10_description,
            # Age bands: <1, 1-4, 5-9, 10-14, 15-19, 20-59, 60+
            func.sum(
                case((Patient.date_of_birth > func.current_date() - 365, 1), else_=0)
            ).label("under_1"),
            func.sum(
                case(
                    (
                        (Patient.date_of_birth <= func.current_date() - 365)
                        & (Patient.date_of_birth > func.current_date() - 365 * 5),
                        1,
                    ),
                    else_=0,
                )
            ).label("age_1_4"),
            func.sum(
                case(
                    (
                        (Patient.date_of_birth <= func.current_date() - 365 * 5)
                        & (Patient.date_of_birth > func.current_date() - 365 * 10),
                        1,
                    ),
                    else_=0,
                )
            ).label("age_5_9"),
            func.sum(
                case(
                    (
                        (Patient.date_of_birth <= func.current_date() - 365 * 10)
                        & (Patient.date_of_birth > func.current_date() - 365 * 20),
                        1,
                    ),
                    else_=0,
                )
            ).label("age_10_19"),
            func.sum(
                case(
                    (Patient.date_of_birth <= func.current_date() - 365 * 20, 1),
                    else_=0,
                )
            ).label("age_20_plus"),
            func.sum(case((Patient.gender == "male", 1), else_=0)).label("male"),
            func.sum(case((Patient.gender == "female", 1), else_=0)).label("female"),
            func.count(Diagnosis.id).label("total"),
        )
        .join(Encounter, Diagnosis.encounter_id == Encounter.id)
        .join(Patient, Encounter.patient_id == Patient.id)
        .where(
            Diagnosis.facility_id == facility_id,
            Diagnosis.is_deleted == False,  # noqa: E712
            Encounter.encounter_type == "opd",
            func.date(Diagnosis.created_at) >= date_from,
            func.date(Diagnosis.created_at) <= date_to,
        )
        .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
        .order_by(func.count(Diagnosis.id).desc())
    )

    rows = result.all()
    data = [
        {
            "icd10_code": r.icd10_code or "Unclassified",
            "description": r.description or "",
            "under_1": r.under_1,
            "age_1_4": r.age_1_4,
            "age_5_9": r.age_5_9,
            "age_10_19": r.age_10_19,
            "age_20_plus": r.age_20_plus,
            "male": r.male,
            "female": r.female,
            "total": r.total,
        }
        for r in rows
    ]

    grand_total = sum(r.total for r in rows)

    return {
        "form": "MOH 705A",
        "title": "Outpatient Morbidity Summary",
        "period": {"from": str(date_from), "to": str(date_to)},
        "rows": data,
        "summary": {"total_diagnoses": grand_total, "unique_conditions": len(data)},
    }


# ── MOH 705B — Inpatient Morbidity Summary ──────────────────────────────────


async def generate_moh_705b(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 705B — Inpatient morbidity summary: diagnoses from admitted patients.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with inpatient diagnoses grouped by ICD-10 and sex
    """
    result = await db.execute(
        select(
            Diagnosis.icd10_code,
            Diagnosis.icd10_description,
            func.sum(case((Patient.gender == "male", 1), else_=0)).label("male"),
            func.sum(case((Patient.gender == "female", 1), else_=0)).label("female"),
            func.count(Diagnosis.id).label("total"),
        )
        .join(Encounter, Diagnosis.encounter_id == Encounter.id)
        .join(Patient, Encounter.patient_id == Patient.id)
        .join(Admission, Admission.encounter_id == Encounter.id)
        .where(
            Diagnosis.facility_id == facility_id,
            Diagnosis.is_deleted == False,  # noqa: E712
            func.date(Admission.admitted_at) >= date_from,
            func.date(Admission.admitted_at) <= date_to,
        )
        .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
        .order_by(func.count(Diagnosis.id).desc())
    )

    rows = result.all()
    data = [
        {
            "icd10_code": r.icd10_code or "Unclassified",
            "description": r.description or "",
            "male": r.male,
            "female": r.female,
            "total": r.total,
        }
        for r in rows
    ]

    return {
        "form": "MOH 705B",
        "title": "Inpatient Morbidity Summary",
        "period": {"from": str(date_from), "to": str(date_to)},
        "rows": data,
        "summary": {"total_diagnoses": sum(r.total for r in rows), "unique_conditions": len(data)},
    }


# ── MOH 710 — Immunization Summary ──────────────────────────────────────────


async def generate_moh_710(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 710 — Immunization report grouped by vaccine name and dose number.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with immunization counts by vaccine
    """
    result = await db.execute(
        select(
            Immunization.vaccine_name,
            Immunization.dose_number,
            func.count(Immunization.id).label("doses_given"),
        )
        .where(
            Immunization.facility_id == facility_id,
            Immunization.is_deleted == False,  # noqa: E712
            func.date(Immunization.date_given) >= date_from,
            func.date(Immunization.date_given) <= date_to,
        )
        .group_by(Immunization.vaccine_name, Immunization.dose_number)
        .order_by(Immunization.vaccine_name, Immunization.dose_number)
    )

    rows = result.all()
    data = [
        {
            "vaccine": r.vaccine_name,
            "dose_number": r.dose_number,
            "doses_given": r.doses_given,
        }
        for r in rows
    ]

    return {
        "form": "MOH 710",
        "title": "Immunization Report",
        "period": {"from": str(date_from), "to": str(date_to)},
        "rows": data,
        "summary": {"total_doses": sum(r.doses_given for r in rows), "unique_vaccines": len({r.vaccine_name for r in rows})},
    }


# ── MOH 711 — Integrated RH/HIV/TB/Malaria Summary ─────────────────────────


async def generate_moh_711(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 711 — Integrated summary: ANC attendance, deliveries, family planning,
    HIV/TB/Malaria indicators derived from encounters and MCH records.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with integrated indicators
    """
    # ANC new registrations
    anc_new = await db.execute(
        select(func.count(ANCProfile.id)).where(
            ANCProfile.facility_id == facility_id,
            ANCProfile.is_deleted == False,  # noqa: E712
            func.date(ANCProfile.created_at) >= date_from,
            func.date(ANCProfile.created_at) <= date_to,
        )
    )

    # Deliveries
    deliveries = await db.execute(
        select(
            func.count(DeliveryRecord.id).label("total"),
            func.sum(case((DeliveryRecord.mode_of_delivery.in_(["elective_cs", "emergency_cs"]), 1), else_=0)).label("caesarean"),
            func.sum(case((DeliveryRecord.mode_of_delivery == "svd", 1), else_=0)).label("normal"),
        ).where(
            DeliveryRecord.facility_id == facility_id,
            DeliveryRecord.is_deleted == False,  # noqa: E712
            func.date(DeliveryRecord.delivery_date) >= date_from,
            func.date(DeliveryRecord.delivery_date) <= date_to,
        )
    )

    # Disease indicators — diagnoses containing HIV, TB, Malaria
    disease_counts = {}
    for keyword in ["HIV", "TB", "Tuberculosis", "Malaria"]:
        count_result = await db.execute(
            select(func.count(Diagnosis.id)).where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                Diagnosis.icd10_description.ilike(f"%{keyword}%"),
                func.date(Diagnosis.created_at) >= date_from,
                func.date(Diagnosis.created_at) <= date_to,
            )
        )
        disease_counts[keyword.lower()] = count_result.scalar() or 0

    anc_count = anc_new.scalar() or 0
    del_row = deliveries.one()

    return {
        "form": "MOH 711",
        "title": "Integrated Summary",
        "period": {"from": str(date_from), "to": str(date_to)},
        "indicators": {
            "anc_new_registrations": anc_count,
            "total_deliveries": del_row.total or 0,
            "normal_deliveries": del_row.normal or 0,
            "caesarean_deliveries": del_row.caesarean or 0,
            "hiv_positive": disease_counts.get("hiv", 0),
            "tb_cases": disease_counts.get("tb", 0) + disease_counts.get("tuberculosis", 0),
            "malaria_cases": disease_counts.get("malaria", 0),
        },
        "summary": {"report_sections": 7},
    }


# ── MOH 713 — Laboratory Summary ────────────────────────────────────────────


async def generate_moh_713(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 713 — Lab summary: tests ordered, completed, results by category.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with lab test summary
    """
    # Tests by panel/category
    result = await db.execute(
        select(
            LabResult.test_name,
            func.count(LabResult.id).label("total"),
            func.sum(case((LabResult.status == "final", 1), else_=0)).label("completed"),
            func.sum(case((LabResult.is_critical == True, 1), else_=0)).label("critical"),  # noqa: E712
        )
        .join(LabOrder, LabResult.order_id == LabOrder.id)
        .where(
            LabOrder.facility_id == facility_id,
            LabResult.is_deleted == False,  # noqa: E712
            func.date(LabResult.created_at) >= date_from,
            func.date(LabResult.created_at) <= date_to,
        )
        .group_by(LabResult.test_name)
        .order_by(func.count(LabResult.id).desc())
    )

    rows = result.all()
    data = [
        {
            "test_name": r.test_name,
            "total": r.total,
            "completed": r.completed,
            "critical": r.critical,
        }
        for r in rows
    ]

    return {
        "form": "MOH 713",
        "title": "Laboratory Summary",
        "period": {"from": str(date_from), "to": str(date_to)},
        "rows": data,
        "summary": {
            "total_tests": sum(r.total for r in rows),
            "completed": sum(r.completed for r in rows),
            "critical_results": sum(r.critical for r in rows),
        },
    }


# ── MOH 718 — Maternity Register Summary ────────────────────────────────────


async def generate_moh_718(
    db: AsyncSession,
    facility_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """
    MOH 718 — Maternity summary: deliveries by outcome, complications, newborn status.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param date_from: Report period start
    @param date_to: Report period end
    @returns Dict with maternity indicators
    """
    result = await db.execute(
        select(
            func.count(DeliveryRecord.id).label("total"),
            func.sum(case((DeliveryRecord.mode_of_delivery == "svd", 1), else_=0)).label("normal"),
            func.sum(case((DeliveryRecord.mode_of_delivery.in_(["elective_cs", "emergency_cs"]), 1), else_=0)).label("caesarean"),
            func.sum(case((DeliveryRecord.mode_of_delivery == "assisted_vaginal", 1), else_=0)).label("assisted"),
            func.sum(case((DeliveryRecord.baby_outcome == "live_birth", 1), else_=0)).label("live_births"),
            func.sum(case((DeliveryRecord.baby_outcome == "stillbirth", 1), else_=0)).label("stillbirths"),
            func.sum(case((DeliveryRecord.maternal_complications.isnot(None), 1), else_=0)).label("with_complications"),
        ).where(
            DeliveryRecord.facility_id == facility_id,
            DeliveryRecord.is_deleted == False,  # noqa: E712
            func.date(DeliveryRecord.delivery_date) >= date_from,
            func.date(DeliveryRecord.delivery_date) <= date_to,
        )
    )

    row = result.one()

    return {
        "form": "MOH 718",
        "title": "Maternity Register Summary",
        "period": {"from": str(date_from), "to": str(date_to)},
        "indicators": {
            "total_deliveries": row.total or 0,
            "normal_deliveries": row.normal or 0,
            "caesarean_deliveries": row.caesarean or 0,
            "assisted_deliveries": row.assisted or 0,
            "live_births": row.live_births or 0,
            "stillbirths": row.stillbirths or 0,
            "with_complications": row.with_complications or 0,
        },
        "summary": {"caesarean_rate": round(((row.caesarean or 0) / max(row.total or 1, 1)) * 100, 1)},
    }
