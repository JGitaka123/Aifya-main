"""
CDS Engine — orchestrates all clinical decision support rule checks.
Entry point for prescription, vitals, lab, and encounter evaluations.
"""

import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.diagnosis import Diagnosis
from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.vital import VitalSign
from app.services.cds.clinical_rules import (
    check_lab_trends,
    check_sepsis_risk,
    check_vitals_age_adjusted,
)
from app.services.cds.drug_rules import (
    _patient_age_years,
    check_age_safety,
    check_drug_allergies,
    check_drug_conditions,
    check_drug_interactions,
    check_duplicate_therapy,
    check_pregnancy_safety,
    check_weight_based_dose,
)
from app.services.cds.models import (
    AlertAction,
    CDSAlert,
    CDSEvaluationResponse,
)

logger = get_logger(__name__)


async def _get_patient_context(
    db: AsyncSession,
    patient_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Load patient context for CDS evaluation.

    @param db: Database session
    @param patient_id: Patient UUID
    @param facility_id: Facility UUID
    @returns Dict with allergies, conditions, dob, gender, current_meds, recent_diagnoses
    """
    patient_stmt = select(Patient).where(
        Patient.id == patient_id,
        Patient.facility_id == facility_id,
        Patient.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(patient_stmt)
    patient = result.scalar_one_or_none()

    if patient is None:
        return {}

    # Active prescriptions
    meds_stmt = select(Prescription).where(
        Prescription.patient_id == patient_id,
        Prescription.facility_id == facility_id,
        Prescription.status.in_(["pending", "dispensed", "partially_dispensed"]),
        Prescription.is_deleted == False,  # noqa: E712
    )
    meds_result = await db.execute(meds_stmt)
    active_meds = meds_result.scalars().all()

    # Recent diagnoses (active)
    dx_stmt = select(Diagnosis).where(
        Diagnosis.patient_id == patient_id,
        Diagnosis.facility_id == facility_id,
        Diagnosis.clinical_status.in_(["active", "recurrence", "relapse"]),
        Diagnosis.is_deleted == False,  # noqa: E712
    )
    dx_result = await db.execute(dx_stmt)
    diagnoses = dx_result.scalars().all()

    # Check for pregnancy (look for active ANC profile or pregnancy diagnosis)
    is_pregnant = False
    if patient.gender == "female":
        for dx in diagnoses:
            icd = (dx.icd10_code or "").upper()
            if icd.startswith("O") or icd.startswith("Z33"):
                is_pregnant = True
                break

    condition_names: list[str] = []
    if patient.chronic_conditions:
        for c in patient.chronic_conditions:
            if isinstance(c, str):
                condition_names.append(c)
            elif isinstance(c, dict) and "name" in c:
                condition_names.append(str(c["name"]))

    for dx in diagnoses:
        if dx.is_chronic and dx.icd10_description:
            condition_names.append(dx.icd10_description)

    # Most recent recorded weight (for weight-based paediatric dosing checks).
    weight_stmt = (
        select(VitalSign.weight_kg)
        .where(
            VitalSign.patient_id == patient_id,
            VitalSign.facility_id == facility_id,
            VitalSign.weight_kg.isnot(None),
            VitalSign.is_deleted == False,  # noqa: E712
        )
        .order_by(VitalSign.recorded_at.desc())
        .limit(1)
    )
    weight_kg = (await db.execute(weight_stmt)).scalars().first()

    return {
        "patient": patient,
        "allergies": patient.allergies or [],
        "chronic_conditions": condition_names,
        "dob": patient.date_of_birth,
        "gender": patient.gender,
        "is_pregnant": is_pregnant,
        "current_medications": [m.drug_name for m in active_meds],
        "active_prescriptions": active_meds,
        "active_diagnoses": diagnoses,
        "weight_kg": weight_kg,
        "age_years": _patient_age_years(patient.date_of_birth),
    }


async def evaluate_prescription(
    db: AsyncSession,
    patient_id: uuid.UUID,
    facility_id: uuid.UUID,
    drug_name: str,
    encounter_id: uuid.UUID | None = None,
    dosage_value: float | None = None,
    dosage_unit: str | None = None,
) -> CDSEvaluationResponse:
    """
    Evaluate CDS rules for a new prescription.
    Runs: drug interactions, allergy checks, condition contraindications,
    age safety, pregnancy safety, duplicate therapy, weight-based dose.

    @param db: Database session
    @param patient_id: Patient UUID
    @param facility_id: Facility UUID
    @param drug_name: Drug being prescribed
    @param encounter_id: Optional encounter UUID
    @param dosage_value: Numeric per-dose amount (for weight-based dosing)
    @param dosage_unit: Dose unit (only mg is dose-range checked)
    @returns CDSEvaluationResponse with alerts
    """
    start = time.time()
    all_alerts: list[CDSAlert] = []

    ctx = await _get_patient_context(db, patient_id, facility_id)
    if not ctx:
        return CDSEvaluationResponse(
            alerts=[],
            evaluation_time_ms=round((time.time() - start) * 1000, 1),
        )

    # 1. Drug-drug interactions
    all_alerts.extend(check_drug_interactions(drug_name, ctx["current_medications"]))

    # 2. Drug-allergy
    all_alerts.extend(check_drug_allergies(drug_name, ctx["allergies"]))

    # 3. Drug-condition
    all_alerts.extend(check_drug_conditions(drug_name, ctx["chronic_conditions"]))

    # 4. Age safety
    all_alerts.extend(check_age_safety(drug_name, ctx["dob"]))

    # 5. Pregnancy
    all_alerts.extend(check_pregnancy_safety(drug_name, ctx["is_pregnant"]))

    # 6. Duplicate therapy
    all_alerts.extend(check_duplicate_therapy(drug_name, ctx["current_medications"]))

    # 7. Weight-based paediatric dose range
    all_alerts.extend(
        check_weight_based_dose(
            drug_name,
            dosage_value,
            dosage_unit,
            ctx.get("weight_kg"),
            ctx.get("age_years"),
        )
    )

    blocking = [a for a in all_alerts if a.action == AlertAction.BLOCK]
    elapsed = round((time.time() - start) * 1000, 1)

    logger.info(
        "cds_prescription_evaluated",
        patient_id=str(patient_id),
        drug=drug_name,
        total_alerts=len(all_alerts),
        blocking_alerts=len(blocking),
        elapsed_ms=elapsed,
    )

    return CDSEvaluationResponse(
        alerts=all_alerts,
        is_blocked=len(blocking) > 0,
        blocking_alerts=blocking,
        evaluation_time_ms=elapsed,
    )


async def evaluate_vitals(
    db: AsyncSession,
    patient_id: uuid.UUID,
    facility_id: uuid.UUID,
    vitals: dict[str, Any],
) -> CDSEvaluationResponse:
    """
    Evaluate CDS rules for vital signs.
    Runs: age-adjusted thresholds, sepsis screening.

    @param db: Database session
    @param patient_id: Patient UUID
    @param facility_id: Facility UUID
    @param vitals: Vital sign values dict
    @returns CDSEvaluationResponse with alerts
    """
    start = time.time()
    all_alerts: list[CDSAlert] = []

    ctx = await _get_patient_context(db, patient_id, facility_id)
    if not ctx:
        return CDSEvaluationResponse(
            alerts=[],
            evaluation_time_ms=round((time.time() - start) * 1000, 1),
        )

    # 1. Age-adjusted vital thresholds
    all_alerts.extend(check_vitals_age_adjusted(vitals, ctx["dob"]))

    # 2. Sepsis screening
    has_infection = any(
        dx.icd10_code and dx.icd10_code.upper().startswith(("A", "B", "J"))
        for dx in ctx.get("active_diagnoses", [])
    )

    recent_labs: list[dict[str, Any]] = []
    lab_stmt = select(LabResult).join(LabOrder).where(
        LabOrder.patient_id == patient_id,
        LabOrder.facility_id == facility_id,
        LabResult.test_code == "WBC",
        LabResult.status == "final",
    ).order_by(LabResult.resulted_at.desc()).limit(1)
    lab_result = await db.execute(lab_stmt)
    wbc_result = lab_result.scalar_one_or_none()
    if wbc_result:
        recent_labs.append({
            "test_code": wbc_result.test_code,
            "result_numeric": wbc_result.result_numeric,
        })

    sepsis_alerts, sepsis_score = check_sepsis_risk(vitals, recent_labs, has_infection)
    all_alerts.extend(sepsis_alerts)

    elapsed = round((time.time() - start) * 1000, 1)

    logger.info(
        "cds_vitals_evaluated",
        patient_id=str(patient_id),
        total_alerts=len(all_alerts),
        sepsis_qsofa=sepsis_score.qsofa_score if sepsis_score else 0,
        elapsed_ms=elapsed,
    )

    return CDSEvaluationResponse(
        alerts=all_alerts,
        is_blocked=False,
        evaluation_time_ms=elapsed,
    )


async def evaluate_lab_result(
    db: AsyncSession,
    patient_id: uuid.UUID,
    facility_id: uuid.UUID,
    test_code: str,
    result_numeric: float | None,
) -> CDSEvaluationResponse:
    """
    Evaluate CDS rules for a lab result.
    Runs: trend analysis, organ dysfunction patterns.

    @param db: Database session
    @param patient_id: Patient UUID
    @param facility_id: Facility UUID
    @param test_code: Lab test code
    @param result_numeric: Numeric result value
    @returns CDSEvaluationResponse with alerts
    """
    start = time.time()
    all_alerts: list[CDSAlert] = []

    if result_numeric is None:
        return CDSEvaluationResponse(
            alerts=[],
            evaluation_time_ms=round((time.time() - start) * 1000, 1),
        )

    # Get historical results for this test
    hist_stmt = (
        select(LabResult)
        .join(LabOrder)
        .where(
            LabOrder.patient_id == patient_id,
            LabOrder.facility_id == facility_id,
            LabResult.test_code == test_code,
            LabResult.status == "final",
            LabResult.result_numeric.isnot(None),
        )
        .order_by(LabResult.resulted_at.desc())
        .limit(5)
    )
    hist_result = await db.execute(hist_stmt)
    historical = hist_result.scalars().all()

    historical_dicts = [
        {
            "test_code": r.test_code,
            "result_numeric": r.result_numeric,
            "resulted_at": str(r.resulted_at) if r.resulted_at else None,
        }
        for r in historical
    ]

    current = {"test_code": test_code, "result_numeric": result_numeric}
    all_alerts.extend(check_lab_trends(current, historical_dicts))

    elapsed = round((time.time() - start) * 1000, 1)

    logger.info(
        "cds_lab_evaluated",
        patient_id=str(patient_id),
        test_code=test_code,
        total_alerts=len(all_alerts),
        elapsed_ms=elapsed,
    )

    return CDSEvaluationResponse(
        alerts=all_alerts,
        is_blocked=False,
        evaluation_time_ms=elapsed,
    )
