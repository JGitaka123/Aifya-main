"""
Bed demand forecasting module.

Forecasts bed occupancy by department using historical admission patterns
(day-of-week multipliers, moving averages, and simple trend analysis)
over the last 90 days.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.services.analytics.models import BedDemandForecast

logger = structlog.get_logger(__name__)

# Assumed bed capacity per department when no better data is available
_DEFAULT_BED_CAPACITY = 50


async def _get_department_label(department: str | None) -> str:
    """
    Normalise department identifier to a display label.

    @param department: Raw department string (UUID or name)
    @returns Display-friendly department label
    """
    if department is None:
        return "all"
    return str(department)


async def forecast_bed_demand(
    db: AsyncSession,
    facility_id: uuid.UUID,
    department: str | None = None,
    days_ahead: int = 7,
) -> list[BedDemandForecast]:
    """
    Forecast bed demand for a department over the next N days.

    Uses 90-day historical admission data to compute a daily admission average,
    day-of-week multipliers, and a simple linear trend. Projects forward and
    returns per-day occupancy forecasts with confidence intervals.

    @param db: Async database session
    @param facility_id: Facility UUID for multi-tenant filtering
    @param department: Department name or UUID string to filter (None for all)
    @param days_ahead: Number of days to forecast (default 7)
    @returns List of BedDemandForecast, one per forecast day
    """
    log = logger.bind(facility_id=str(facility_id), department=department, days_ahead=days_ahead)
    log.info("analytics.bed_forecast.start")

    now = datetime.utcnow()
    ninety_days_ago = now - timedelta(days=90)
    today = date.today()

    # --- Query historical daily admissions over the last 90 days ---
    base_filter = [
        Encounter.facility_id == facility_id,
        Encounter.encounter_type == "ipd",
        Encounter.admission_date >= ninety_days_ago,
        Encounter.is_deleted.is_(False),
    ]
    if department is not None:
        # Allow filtering by department_id (UUID string) or fall back to text match
        try:
            dept_uuid = uuid.UUID(department)
            base_filter.append(Encounter.department_id == dept_uuid)
        except ValueError:
            # Not a valid UUID — skip department filter rather than fail
            log.warning("analytics.bed_forecast.invalid_department_uuid", department=department)

    # Daily admission count grouped by date
    daily_admissions_q = (
        select(
            func.date(Encounter.admission_date).label("admission_day"),
            func.count().label("cnt"),
        )
        .where(*base_filter)
        .group_by(func.date(Encounter.admission_date))
    )
    daily_result = await db.execute(daily_admissions_q)
    daily_rows = daily_result.all()

    # Build lookup: date -> count
    daily_counts: dict[date, int] = {}
    for row in daily_rows:
        if row.admission_day is not None:
            day = row.admission_day
            daily_counts[day] = int(row.cnt)

    # Fill missing dates with 0
    all_dates: list[date] = []
    d = (ninety_days_ago).date() if isinstance(ninety_days_ago, datetime) else ninety_days_ago
    while d <= today:
        all_dates.append(d)
        if d not in daily_counts:
            daily_counts[d] = 0
        d += timedelta(days=1)

    total_days = len(all_dates) or 1
    total_admissions = sum(daily_counts.values())
    avg_daily = total_admissions / total_days

    # --- Day-of-week multipliers ---
    dow_totals: dict[int, int] = {i: 0 for i in range(7)}
    dow_counts: dict[int, int] = {i: 0 for i in range(7)}
    for d_date in all_dates:
        dow = d_date.weekday()  # 0=Monday
        dow_totals[dow] += daily_counts.get(d_date, 0)
        dow_counts[dow] += 1

    dow_avg: dict[int, float] = {}
    for dow in range(7):
        if dow_counts[dow] > 0:
            dow_avg[dow] = dow_totals[dow] / dow_counts[dow]
        else:
            dow_avg[dow] = avg_daily

    dow_multiplier: dict[int, float] = {}
    for dow in range(7):
        if avg_daily > 0:
            dow_multiplier[dow] = dow_avg[dow] / avg_daily
        else:
            dow_multiplier[dow] = 1.0

    # --- Simple linear trend (slope over the 90-day window) ---
    # Use indexed day (0..N-1) and daily counts
    if total_days >= 2:
        sorted_dates = sorted(all_dates)
        n = len(sorted_dates)
        x_mean = (n - 1) / 2.0
        y_mean = avg_daily
        numerator = 0.0
        denominator = 0.0
        for i, d_date in enumerate(sorted_dates):
            y = daily_counts.get(d_date, 0)
            numerator += (i - x_mean) * (y - y_mean)
            denominator += (i - x_mean) ** 2
        slope = numerator / denominator if denominator != 0 else 0.0
    else:
        slope = 0.0

    # --- Current inpatients (not discharged) ---
    current_inpatient_filter = [
        Encounter.facility_id == facility_id,
        Encounter.encounter_type == "ipd",
        Encounter.status.in_(["admitted", "in_consultation", "waiting"]),
        Encounter.discharge_date.is_(None),
        Encounter.is_deleted.is_(False),
    ]
    if department is not None:
        try:
            dept_uuid = uuid.UUID(department)
            current_inpatient_filter.append(Encounter.department_id == dept_uuid)
        except ValueError:
            pass

    current_count_result = await db.execute(
        select(func.count()).select_from(Encounter).where(*current_inpatient_filter)
    )
    current_inpatients: int = current_count_result.scalar_one()
    current_occupancy_pct = min((current_inpatients / _DEFAULT_BED_CAPACITY) * 100.0, 100.0)

    # --- Project forward ---
    forecasts: list[BedDemandForecast] = []
    dept_label = await _get_department_label(department)

    for offset in range(1, days_ahead + 1):
        forecast_date = today + timedelta(days=offset)
        dow = forecast_date.weekday()

        # Projected admissions = avg + trend contribution + day-of-week adjustment
        total_days + offset
        projected_admissions = max(0.0, avg_daily + slope * offset) * dow_multiplier.get(dow, 1.0)

        # Predicted occupancy as percentage of capacity
        predicted_occupancy = min(
            ((current_inpatients + projected_admissions) / _DEFAULT_BED_CAPACITY) * 100.0,
            100.0,
        )

        # Confidence interval: +/- 15% of predicted value, clamped to [0, 100]
        margin = predicted_occupancy * 0.15
        ci_lower = max(0.0, predicted_occupancy - margin)
        ci_upper = min(100.0, predicted_occupancy + margin)

        # Recommended actions based on predicted occupancy
        actions: list[str] = []
        if predicted_occupancy >= 90:
            actions.append("Activate surge capacity and consider diverting non-urgent admissions")
            actions.append("Expedite discharge planning for stable patients")
        elif predicted_occupancy >= 75:
            actions.append("Review pending discharges and accelerate where clinically safe")
            actions.append("Pre-alert additional nursing staff for coverage")
        elif predicted_occupancy >= 50:
            actions.append("Maintain standard staffing levels")
        else:
            actions.append("Normal operations — consider elective admission scheduling")

        forecasts.append(
            BedDemandForecast(
                date=forecast_date,
                department=dept_label,
                predicted_occupancy=round(predicted_occupancy, 1),
                confidence_interval=(round(ci_lower, 1), round(ci_upper, 1)),
                current_occupancy=round(current_occupancy_pct, 1),
                recommended_actions=actions,
            )
        )

    log.info("analytics.bed_forecast.complete", forecast_count=len(forecasts))
    return forecasts
