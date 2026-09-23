"""
Predictive analytics API router.

Provides endpoints for readmission risk, bed demand forecasting, no-show
prediction, inventory stockout alerts, revenue forecasting, and a combined
analytics dashboard.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.services.analytics.bed_forecast import forecast_bed_demand
from app.services.analytics.engine import get_analytics_dashboard
from app.services.analytics.models import (
    AnalyticsDashboard,
    BedDemandForecast,
    NoShowPrediction,
    ReadmissionRisk,
    RevenueForecast,
    StockoutPrediction,
)
from app.services.analytics.no_show import predict_no_show
from app.services.analytics.readmission import predict_readmission_risk
from app.services.analytics.revenue import forecast_revenue
from app.services.analytics.stockout import predict_stockouts

router = APIRouter(dependencies=[Depends(require_module("analytics"))])


@router.get(
    "/readmission-risk/{patient_id}",
    response_model=ReadmissionRisk,
)
async def get_readmission_risk(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReadmissionRisk:
    """
    Get 30-day readmission risk prediction for a single patient.

    Uses weighted rule-based scoring across clinical factors including
    prior admissions, chronic conditions, age, medications, and more.

    @param patient_id: UUID of the patient to evaluate
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns ReadmissionRisk with score, level, factors, and interventions
    """
    return await predict_readmission_risk(db, patient_id, current_user.facility_id)


@router.get(
    "/bed-forecast",
    response_model=list[BedDemandForecast],
)
async def get_bed_forecast(
    department: str | None = Query(None, description="Department UUID or name to filter"),
    days_ahead: int = Query(7, ge=1, le=90, description="Number of days to forecast"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BedDemandForecast]:
    """
    Forecast bed demand for a department over the next N days.

    Uses 90-day historical admission data with day-of-week multipliers
    and linear trend analysis.

    @param department: Optional department filter (UUID string or name)
    @param days_ahead: Days to forecast (1-90, default 7)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of daily BedDemandForecast predictions
    """
    return await forecast_bed_demand(
        db, current_user.facility_id, department=department, days_ahead=days_ahead
    )


@router.get(
    "/no-show/{appointment_id}",
    response_model=NoShowPrediction,
)
async def get_no_show_prediction(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NoShowPrediction:
    """
    Predict no-show probability for a single appointment.

    Evaluates patient history, appointment timing, reminders, and
    scheduling patterns to estimate no-show likelihood.

    @param appointment_id: UUID of the appointment to evaluate
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns NoShowPrediction with probability, factors, and recommended action
    """
    return await predict_no_show(db, appointment_id, current_user.facility_id)


@router.get(
    "/stockout-predictions",
    response_model=list[StockoutPrediction],
)
async def get_stockout_predictions(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[StockoutPrediction]:
    """
    Get stockout predictions for all active inventory items.

    Analyses 30-day dispensing history to calculate consumption rates
    and estimate days until stockout. Sorted by urgency.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of StockoutPrediction sorted by urgency (critical first)
    """
    return await predict_stockouts(db, current_user.facility_id)


@router.get(
    "/revenue-forecast",
    response_model=list[RevenueForecast],
)
async def get_revenue_forecast(
    months_ahead: int = Query(3, ge=1, le=12, description="Number of months to forecast"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RevenueForecast]:
    """
    Forecast monthly revenue for the next N months.

    Uses 12-month historical billing data with linear trend and
    seasonal adjustment. Includes per-department breakdowns.

    @param months_ahead: Months to forecast (1-12, default 3)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of monthly RevenueForecast predictions
    """
    return await forecast_revenue(db, current_user.facility_id, months_ahead=months_ahead)


@router.get(
    "/dashboard",
    response_model=AnalyticsDashboard,
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AnalyticsDashboard:
    """
    Get the combined predictive analytics dashboard.

    Aggregates results from all prediction modules: readmission risks,
    bed demand, no-show predictions, stockout alerts, and revenue forecasts.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AnalyticsDashboard with all prediction summaries
    """
    return await get_analytics_dashboard(db, current_user.facility_id)
