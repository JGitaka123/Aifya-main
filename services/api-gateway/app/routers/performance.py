"""
Hospital Performance KPI router.
Exposes facility-wide KPIs computed on demand from existing operational tables.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.services.performance.metrics import (
    compare_periods,
    get_facility_kpis,
    get_metric_trend,
)

router = APIRouter()


class FacilityKpisResponse(BaseModel):
    """API response wrapping FacilityKpis for serialization."""

    period_start: date
    period_end: date
    patient_volume: float
    bed_occupancy_rate: float
    average_length_of_stay: float
    readmission_rate: float
    revenue_per_patient: float
    claim_rejection_rate: float
    lab_turnaround_time: float
    emergency_response_time: float
    staff_attendance_rate: float
    patient_satisfaction: float
    total_encounters: int
    total_admissions: int
    total_revenue: float


class TrendPointResponse(BaseModel):
    """Single trend point."""

    bucket: str
    value: float


class TrendResponse(BaseModel):
    """Time-series for one metric."""

    metric: str
    bucket: str
    points: list[TrendPointResponse]


class PeriodComparisonResponse(BaseModel):
    """Period-over-period comparison."""

    current: dict
    prior: dict
    delta_pct: dict
    compare_to: str


def _default_window(start: date | None, end: date | None) -> tuple[date, date]:
    """Default to the last 30 days if no window is provided."""
    today = date.today()
    if end is None:
        end = today
    if start is None:
        start = end - timedelta(days=29)
    return start, end


@router.get("/kpis", response_model=FacilityKpisResponse)
async def get_kpis(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FacilityKpisResponse:
    """
    Get all facility KPIs for the given window. Defaults to last 30 days.

    @param start: Inclusive start date (defaults to 29 days before end)
    @param end: Inclusive end date (defaults to today)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Computed KPIs
    """
    s, e = _default_window(start, end)
    kpis = await get_facility_kpis(db, current_user.facility_id, s, e)
    return FacilityKpisResponse(**kpis.__dict__)


@router.get("/trends", response_model=TrendResponse)
async def get_trends(
    metric: str = Query(..., min_length=1),
    period: str = Query("last_30_days"),
    bucket: str = Query("day", pattern="^(day|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TrendResponse:
    """
    Get time-series for a single metric.

    @param metric: One of: patient_volume, revenue, bed_occupancy_rate, claim_rejection_rate
    @param period: last_7_days | last_30_days | last_quarter | last_year
    @param bucket: "day" or "month"
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Trend response
    """
    today = date.today()
    if period == "last_7_days":
        start = today - timedelta(days=6)
    elif period == "last_quarter":
        start = today - timedelta(days=89)
    elif period == "last_year":
        start = today - timedelta(days=364)
    else:
        start = today - timedelta(days=29)

    points = await get_metric_trend(
        db,
        current_user.facility_id,
        metric=metric,
        start=start,
        end=today,
        bucket=bucket,
    )
    return TrendResponse(
        metric=metric,
        bucket=bucket,
        points=[TrendPointResponse(bucket=p.bucket, value=p.value) for p in points],
    )


@router.get("/comparison", response_model=PeriodComparisonResponse)
async def get_comparison(
    compare_to: str = Query("last_month", pattern="^(last_month|last_year)$"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PeriodComparisonResponse:
    """
    Period-over-period comparison.

    @param compare_to: "last_month" or "last_year"
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Current and prior period KPIs with delta percentages
    """
    today = date.today()
    result = await compare_periods(
        db, current_user.facility_id, end=today, compare_to=compare_to
    )
    return PeriodComparisonResponse(**result)
