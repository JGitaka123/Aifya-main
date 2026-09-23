"""
No-show prediction module.

Predicts the probability that a patient will miss a scheduled appointment
using a weighted rule-based scoring system. Factors include historical
no-show rate, day of week, time of day, appointment type, and lead time.
"""

from __future__ import annotations

import uuid
from datetime import date, time

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.models import NoShowPrediction

logger = structlog.get_logger(__name__)

# Scoring weights for no-show risk factors
_WEIGHTS: dict[str, float] = {
    "high_historical_no_show": 0.30,
    "monday_or_friday": 0.10,
    "afternoon_slot": 0.05,
    "long_lead_time": 0.15,
    "no_reminder_sent": 0.15,
    "follow_up_type": 0.10,
    "prior_cancellations": 0.15,
}

# Factor descriptions
_FACTOR_DESCRIPTIONS: dict[str, str] = {
    "high_historical_no_show": "Patient has a high historical no-show rate (>20%)",
    "monday_or_friday": "Appointment scheduled on Monday or Friday (higher no-show days)",
    "afternoon_slot": "Afternoon appointment slot (higher no-show than morning)",
    "long_lead_time": "Appointment booked more than 14 days in advance",
    "no_reminder_sent": "No appointment reminder has been sent to the patient",
    "follow_up_type": "Follow-up appointment type (higher no-show than initial visits)",
    "prior_cancellations": "Patient has prior appointment cancellations",
}


def _determine_action(probability: float) -> str:
    """
    Determine the recommended action based on no-show probability.

    @param probability: No-show probability between 0.0 and 1.0
    @returns Recommended action string
    """
    if probability >= 0.6:
        return "Call patient to confirm attendance and consider double-booking slot"
    if probability >= 0.3:
        return "Send SMS/WhatsApp reminder 24 hours before appointment"
    return "Standard appointment — no additional action required"


async def predict_no_show(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> NoShowPrediction:
    """
    Predict the no-show probability for a specific appointment.

    Evaluates risk factors including the patient's historical no-show rate,
    appointment scheduling patterns, reminder status, and lead time.

    @param db: Async database session
    @param appointment_id: UUID of the appointment to evaluate
    @param facility_id: Facility UUID for multi-tenant filtering
    @returns NoShowPrediction with probability, factors, and recommended action
    """
    log = logger.bind(appointment_id=str(appointment_id), facility_id=str(facility_id))
    log.info("analytics.no_show.predict_start")

    triggered_factors: list[str] = []
    score = 0.0

    try:
        from app.models.appointment import Appointment

        # --- Fetch the target appointment ---
        appt_result = await db.execute(
            select(Appointment).where(
                Appointment.facility_id == facility_id,
                Appointment.id == appointment_id,
                Appointment.is_deleted.is_(False),
            )
        )
        appointment = appt_result.scalar_one_or_none()

        if appointment is None:
            log.warning("analytics.no_show.appointment_not_found")
            return NoShowPrediction(
                appointment_id=appointment_id,
                patient_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                no_show_probability=0.0,
                risk_factors=["Appointment not found — unable to assess risk"],
                recommended_action="Verify appointment exists in the system",
            )

        patient_id = appointment.patient_id

        # --- Factor: Historical no-show rate ---
        total_past_result = await db.execute(
            select(func.count()).select_from(Appointment).where(
                Appointment.facility_id == facility_id,
                Appointment.patient_id == patient_id,
                Appointment.appointment_date < date.today(),
                Appointment.is_deleted.is_(False),
            )
        )
        total_past: int = total_past_result.scalar_one()

        no_show_count_result = await db.execute(
            select(func.count()).select_from(Appointment).where(
                Appointment.facility_id == facility_id,
                Appointment.patient_id == patient_id,
                Appointment.status == "no_show",
                Appointment.is_deleted.is_(False),
            )
        )
        no_show_count: int = no_show_count_result.scalar_one()

        if total_past > 0 and (no_show_count / total_past) > 0.2:
            score += _WEIGHTS["high_historical_no_show"]
            triggered_factors.append("high_historical_no_show")

        # --- Factor: Monday or Friday ---
        appt_dow = appointment.appointment_date.weekday()
        if appt_dow in (0, 4):  # Monday=0, Friday=4
            score += _WEIGHTS["monday_or_friday"]
            triggered_factors.append("monday_or_friday")

        # --- Factor: Afternoon slot ---
        if appointment.start_time >= time(12, 0):
            score += _WEIGHTS["afternoon_slot"]
            triggered_factors.append("afternoon_slot")

        # --- Factor: Long lead time (> 14 days from booking to appointment) ---
        if appointment.appointment_date:
            days_until = (appointment.appointment_date - date.today()).days
            if days_until > 14:
                score += _WEIGHTS["long_lead_time"]
                triggered_factors.append("long_lead_time")

        # --- Factor: No reminder sent ---
        if not appointment.reminder_sent:
            score += _WEIGHTS["no_reminder_sent"]
            triggered_factors.append("no_reminder_sent")

        # --- Factor: Follow-up appointment type ---
        if appointment.appointment_type == "follow_up":
            score += _WEIGHTS["follow_up_type"]
            triggered_factors.append("follow_up_type")

        # --- Factor: Prior cancellations ---
        cancel_count_result = await db.execute(
            select(func.count()).select_from(Appointment).where(
                Appointment.facility_id == facility_id,
                Appointment.patient_id == patient_id,
                Appointment.status == "cancelled",
                Appointment.is_deleted.is_(False),
            )
        )
        cancel_count: int = cancel_count_result.scalar_one()
        if cancel_count >= 2:
            score += _WEIGHTS["prior_cancellations"]
            triggered_factors.append("prior_cancellations")

    except Exception as exc:
        log.warning("analytics.no_show.prediction_failed", error=str(exc))
        return NoShowPrediction(
            appointment_id=appointment_id,
            patient_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            no_show_probability=0.0,
            risk_factors=["Unable to compute prediction — appointment data unavailable"],
            recommended_action="Send standard appointment reminder",
        )

    # Clamp score
    score = min(score, 1.0)

    contributing_factors = [_FACTOR_DESCRIPTIONS[f] for f in triggered_factors]
    recommended_action = _determine_action(score)

    log.info(
        "analytics.no_show.predict_complete",
        no_show_probability=score,
        factor_count=len(triggered_factors),
    )

    return NoShowPrediction(
        appointment_id=appointment_id,
        patient_id=patient_id,
        no_show_probability=round(score, 4),
        risk_factors=contributing_factors,
        recommended_action=recommended_action,
    )
