"""
Readmission risk predictor.

Uses a weighted rule-based scoring system to estimate the probability of
a patient being readmitted within 30 days. Factors include prior admissions,
chronic conditions, age, active medications, length of stay, ED visits,
and follow-up scheduling.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.services.analytics.models import ReadmissionRisk

logger = structlog.get_logger(__name__)

# Scoring weights for each risk factor
_WEIGHTS: dict[str, float] = {
    "prior_admission_30d": 0.25,
    "chronic_conditions_3plus": 0.15,
    "age_over_65": 0.10,
    "medications_5plus": 0.10,
    "los_over_7d": 0.10,
    "ed_visit_30d": 0.15,
    "no_follow_up": 0.15,
}

# Map factor keys to human-readable descriptions
_FACTOR_DESCRIPTIONS: dict[str, str] = {
    "prior_admission_30d": "Prior hospital admission within the last 30 days",
    "chronic_conditions_3plus": "Three or more active chronic conditions",
    "age_over_65": "Patient age over 65 years",
    "medications_5plus": "Five or more active medications",
    "los_over_7d": "Length of stay exceeding 7 days",
    "ed_visit_30d": "Emergency department visit within the last 30 days",
    "no_follow_up": "No follow-up appointment scheduled after discharge",
}

# Map factor keys to recommended interventions
_INTERVENTIONS: dict[str, str] = {
    "prior_admission_30d": "Schedule early post-discharge follow-up within 48 hours",
    "chronic_conditions_3plus": "Coordinate multidisciplinary care plan with specialists",
    "age_over_65": "Arrange home health assessment and medication reconciliation",
    "medications_5plus": "Conduct comprehensive medication reconciliation before discharge",
    "los_over_7d": "Develop detailed transition-of-care plan with community resources",
    "ed_visit_30d": "Assign care coordinator for post-discharge monitoring",
    "no_follow_up": "Schedule follow-up appointment before discharge",
}


def _compute_risk_level(score: float) -> str:
    """
    Map a numeric risk score to a categorical level.

    @param score: Risk score between 0.0 and 1.0
    @returns Risk level string: low, moderate, or high
    """
    if score > 0.6:
        return "high"
    if score >= 0.3:
        return "moderate"
    return "low"


async def predict_readmission_risk(
    db: AsyncSession,
    patient_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> ReadmissionRisk:
    """
    Predict the 30-day readmission risk for a patient using weighted rule-based scoring.

    Queries clinical data to evaluate risk factors including prior admissions,
    chronic conditions, age, medication count, length of stay, ED visits,
    and follow-up scheduling status.

    @param db: Async database session
    @param patient_id: UUID of the patient to evaluate
    @param facility_id: Facility UUID for multi-tenant filtering
    @returns ReadmissionRisk with score, level, factors, and interventions
    """
    log = logger.bind(patient_id=str(patient_id), facility_id=str(facility_id))
    log.info("analytics.readmission.predict_start")

    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    six_months_ago = now - timedelta(days=180)

    triggered_factors: list[str] = []
    score = 0.0

    # --- Fetch patient demographics ---
    patient_result = await db.execute(
        select(Patient).where(
            Patient.facility_id == facility_id,
            Patient.id == patient_id,
            Patient.is_deleted.is_(False),
        )
    )
    patient = patient_result.scalar_one_or_none()

    if patient is None:
        log.warning("analytics.readmission.patient_not_found")
        return ReadmissionRisk(
            patient_id=patient_id,
            risk_score=0.0,
            risk_level="low",
            contributing_factors=["Patient not found — unable to assess risk"],
            recommended_interventions=[],
        )

    # --- Factor: Age > 65 ---
    if patient.date_of_birth:
        age_years = (date.today() - patient.date_of_birth).days / 365.25
        if age_years > 65:
            score += _WEIGHTS["age_over_65"]
            triggered_factors.append("age_over_65")

    # --- Factor: 3+ chronic conditions ---
    chronic_count_result = await db.execute(
        select(func.count()).select_from(Diagnosis).where(
            Diagnosis.facility_id == facility_id,
            Diagnosis.patient_id == patient_id,
            Diagnosis.is_chronic.is_(True),
            Diagnosis.clinical_status == "active",
            Diagnosis.is_deleted.is_(False),
        )
    )
    chronic_count: int = chronic_count_result.scalar_one()
    if chronic_count >= 3:
        score += _WEIGHTS["chronic_conditions_3plus"]
        triggered_factors.append("chronic_conditions_3plus")

    # --- Factor: Prior admission in last 30 days ---
    prior_admission_result = await db.execute(
        select(func.count()).select_from(Encounter).where(
            Encounter.facility_id == facility_id,
            Encounter.patient_id == patient_id,
            Encounter.encounter_type == "ipd",
            Encounter.admission_date >= thirty_days_ago,
            Encounter.is_deleted.is_(False),
        )
    )
    prior_admissions: int = prior_admission_result.scalar_one()
    if prior_admissions > 0:
        score += _WEIGHTS["prior_admission_30d"]
        triggered_factors.append("prior_admission_30d")

    # --- Factor: ED visit in last 30 days ---
    ed_visit_result = await db.execute(
        select(func.count()).select_from(Encounter).where(
            Encounter.facility_id == facility_id,
            Encounter.patient_id == patient_id,
            Encounter.encounter_type == "emergency",
            Encounter.encounter_date >= thirty_days_ago,
            Encounter.is_deleted.is_(False),
        )
    )
    ed_visits: int = ed_visit_result.scalar_one()
    if ed_visits > 0:
        score += _WEIGHTS["ed_visit_30d"]
        triggered_factors.append("ed_visit_30d")

    # --- Factor: 5+ active medications ---
    med_count_result = await db.execute(
        select(func.count()).select_from(Prescription).where(
            Prescription.facility_id == facility_id,
            Prescription.patient_id == patient_id,
            Prescription.status.in_(["pending", "dispensed", "partially_dispensed"]),
            Prescription.is_deleted.is_(False),
            Prescription.created_at >= six_months_ago,
        )
    )
    med_count: int = med_count_result.scalar_one()
    if med_count >= 5:
        score += _WEIGHTS["medications_5plus"]
        triggered_factors.append("medications_5plus")

    # --- Factor: Length of stay > 7 days (most recent IPD encounter) ---
    recent_ipd_result = await db.execute(
        select(Encounter).where(
            Encounter.facility_id == facility_id,
            Encounter.patient_id == patient_id,
            Encounter.encounter_type == "ipd",
            Encounter.is_deleted.is_(False),
        ).order_by(Encounter.admission_date.desc()).limit(1)
    )
    recent_ipd = recent_ipd_result.scalar_one_or_none()
    if recent_ipd and recent_ipd.admission_date:
        discharge = recent_ipd.discharge_date or now
        los_days = (discharge - recent_ipd.admission_date).days
        if los_days > 7:
            score += _WEIGHTS["los_over_7d"]
            triggered_factors.append("los_over_7d")

    # --- Factor: No follow-up scheduled ---
    # Check for any future appointment for this patient
    try:
        from app.models.appointment import Appointment

        future_appt_result = await db.execute(
            select(func.count()).select_from(Appointment).where(
                Appointment.facility_id == facility_id,
                Appointment.patient_id == patient_id,
                Appointment.appointment_date >= date.today(),
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.is_deleted.is_(False),
            )
        )
        future_appts: int = future_appt_result.scalar_one()
        if future_appts == 0:
            score += _WEIGHTS["no_follow_up"]
            triggered_factors.append("no_follow_up")
    except Exception as exc:
        log.warning("analytics.readmission.appointment_check_failed", error=str(exc))
        # If appointment table is unavailable, assume no follow-up
        score += _WEIGHTS["no_follow_up"]
        triggered_factors.append("no_follow_up")

    # Clamp score to [0, 1]
    score = min(score, 1.0)

    # Build human-readable factors and interventions
    contributing_factors = [_FACTOR_DESCRIPTIONS[f] for f in triggered_factors]
    recommended_interventions = [_INTERVENTIONS[f] for f in triggered_factors]

    risk_level = _compute_risk_level(score)
    log.info(
        "analytics.readmission.predict_complete",
        risk_score=score,
        risk_level=risk_level,
        factor_count=len(triggered_factors),
    )

    return ReadmissionRisk(
        patient_id=patient_id,
        risk_score=round(score, 4),
        risk_level=risk_level,
        contributing_factors=contributing_factors,
        recommended_interventions=recommended_interventions,
    )
