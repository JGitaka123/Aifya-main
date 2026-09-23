"""
Analytics orchestrator.

Assembles the unified analytics dashboard by calling all prediction modules
and combining their results into a single response.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.services.analytics.bed_forecast import forecast_bed_demand
from app.services.analytics.models import (
    AnalyticsDashboard,
    NoShowPrediction,
    ReadmissionRisk,
)
from app.services.analytics.readmission import predict_readmission_risk
from app.services.analytics.revenue import forecast_revenue
from app.services.analytics.stockout import predict_stockouts

logger = structlog.get_logger(__name__)

# Dashboard limits
_TOP_READMISSION_LIMIT = 10
_TOP_NO_SHOW_LIMIT = 10


async def get_analytics_dashboard(
    db: AsyncSession,
    facility_id: uuid.UUID,
) -> AnalyticsDashboard:
    """
    Generate a combined analytics dashboard for the facility.

    Assembles predictions from all analytics modules:
    - Top readmission risks (up to 10 recently discharged patients)
    - 7-day bed demand forecast
    - Upcoming appointment no-show risks (up to 10)
    - Critical and high-urgency stockout predictions
    - 3-month revenue forecast

    @param db: Async database session
    @param facility_id: Facility UUID for multi-tenant filtering
    @returns AnalyticsDashboard with all prediction summaries
    """
    log = logger.bind(facility_id=str(facility_id))
    log.info("analytics.dashboard.build_start")

    generated_at = datetime.utcnow().isoformat() + "Z"

    # --- Top readmission risks: recently discharged patients ---
    # NOTE: PostgreSQL rejects SELECT DISTINCT ... ORDER BY discharge_date
    # (the ORDER BY column is not in the select list), which also aborts
    # the shared DB transaction. Fetch ordered ids and de-duplicate in
    # Python instead, keeping the most recent discharge per patient.
    readmission_risks: list[ReadmissionRisk] = []
    try:
        recent_discharged_result = await db.execute(
            select(Encounter.patient_id)
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "ipd",
                Encounter.disposition == "discharged",
                Encounter.discharge_date.isnot(None),
                Encounter.is_deleted.is_(False),
            )
            .order_by(Encounter.discharge_date.desc())
            .limit(_TOP_READMISSION_LIMIT * 5)
        )
        discharged_patient_ids: list[uuid.UUID] = []
        seen_patient_ids: set[uuid.UUID] = set()
        for (patient_id,) in recent_discharged_result.all():
            if patient_id in seen_patient_ids:
                continue
            seen_patient_ids.add(patient_id)
            discharged_patient_ids.append(patient_id)
            if len(discharged_patient_ids) >= _TOP_READMISSION_LIMIT:
                break

        for pid in discharged_patient_ids:
            try:
                risk = await predict_readmission_risk(db, pid, facility_id)
                readmission_risks.append(risk)
            except Exception as exc:
                log.warning(
                    "analytics.dashboard.readmission_patient_failed",
                    patient_id=str(pid),
                    error=str(exc),
                )

        # Sort by risk score descending
        readmission_risks.sort(key=lambda r: r.risk_score, reverse=True)
    except Exception as exc:
        await db.rollback()
        log.warning("analytics.dashboard.readmission_failed", error=str(exc))

    # --- Bed forecast: next 7 days, all departments ---
    try:
        bed_forecasts = await forecast_bed_demand(
            db, facility_id, department=None, days_ahead=7
        )
    except Exception as exc:
        # Roll back so a failed block does not poison the shared session.
        await db.rollback()
        log.warning("analytics.dashboard.bed_forecast_failed", error=str(exc))
        bed_forecasts = []

    # --- Upcoming no-shows ---
    no_show_predictions: list[NoShowPrediction] = []
    try:
        from app.models.appointment import Appointment
        from app.services.analytics.no_show import predict_no_show

        upcoming_result = await db.execute(
            select(Appointment.id)
            .where(
                Appointment.facility_id == facility_id,
                Appointment.appointment_date >= date.today(),
                Appointment.appointment_date <= date.today() + timedelta(days=7),
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.is_deleted.is_(False),
            )
            .order_by(Appointment.appointment_date)
            .limit(_TOP_NO_SHOW_LIMIT)
        )
        upcoming_appt_ids: list[uuid.UUID] = [row[0] for row in upcoming_result.all()]

        for appt_id in upcoming_appt_ids:
            prediction = await predict_no_show(db, appt_id, facility_id)
            no_show_predictions.append(prediction)

        # Sort by no-show probability descending
        no_show_predictions.sort(key=lambda p: p.no_show_probability, reverse=True)
    except Exception as exc:
        await db.rollback()
        log.warning("analytics.dashboard.no_show_failed", error=str(exc))

    # --- Critical stockouts ---
    all_stockouts = await predict_stockouts(db, facility_id)
    critical_stockouts = [
        s for s in all_stockouts if s.urgency in ("critical", "high")
    ]

    # --- Revenue forecast: next 3 months ---
    revenue_forecasts = await forecast_revenue(db, facility_id, months_ahead=3)

    dashboard = AnalyticsDashboard(
        top_readmission_risks=readmission_risks,
        bed_forecast_7d=bed_forecasts,
        upcoming_no_shows=no_show_predictions,
        critical_stockouts=critical_stockouts,
        revenue_forecast_3m=revenue_forecasts,
        generated_at=generated_at,
    )

    log.info(
        "analytics.dashboard.build_complete",
        readmission_count=len(readmission_risks),
        bed_forecast_count=len(bed_forecasts),
        no_show_count=len(no_show_predictions),
        stockout_count=len(critical_stockouts),
        revenue_count=len(revenue_forecasts),
    )

    return dashboard
