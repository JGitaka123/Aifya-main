"""
Revenue forecasting module.

Projects monthly revenue using 12-month historical billing data with
linear trend analysis and seasonal adjustment. Provides per-department
breakdowns and confidence intervals.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.models import RevenueForecast

logger = structlog.get_logger(__name__)

# Confidence interval width as a fraction of the predicted value
_CONFIDENCE_MARGIN = 0.20


async def forecast_revenue(
    db: AsyncSession,
    facility_id: uuid.UUID,
    months_ahead: int = 3,
) -> list[RevenueForecast]:
    """
    Forecast monthly revenue for the next N months.

    Queries the last 12 months of invoice data, calculates a linear trend
    and seasonal (month-of-year) adjustment, then projects forward.
    Includes per-department breakdowns and confidence intervals.

    @param db: Async database session
    @param facility_id: Facility UUID for multi-tenant filtering
    @param months_ahead: Number of months to forecast (default 3)
    @returns List of RevenueForecast, one per projected month
    """
    log = logger.bind(facility_id=str(facility_id), months_ahead=months_ahead)
    log.info("analytics.revenue.forecast_start")

    forecasts: list[RevenueForecast] = []

    try:
        from app.models.billing import Invoice, InvoiceItem

        twelve_months_ago = datetime.utcnow() - timedelta(days=365)
        today = date.today()

        # --- Monthly revenue totals over the last 12 months ---
        monthly_q = (
            select(
                extract("year", Invoice.created_at).label("yr"),
                extract("month", Invoice.created_at).label("mo"),
                func.coalesce(func.sum(Invoice.total_cents), 0).label("revenue"),
            )
            .where(
                Invoice.facility_id == facility_id,
                Invoice.status.in_(["finalized", "partially_paid", "paid"]),
                Invoice.created_at >= twelve_months_ago,
                Invoice.is_deleted.is_(False),
            )
            .group_by(
                extract("year", Invoice.created_at),
                extract("month", Invoice.created_at),
            )
            .order_by(
                extract("year", Invoice.created_at),
                extract("month", Invoice.created_at),
            )
        )
        monthly_result = await db.execute(monthly_q)
        monthly_rows = monthly_result.all()

        # Build monthly revenue series
        monthly_data: list[tuple[int, int, int]] = []  # (year, month, revenue_cents)
        for row in monthly_rows:
            yr = int(row.yr) if row.yr else today.year
            mo = int(row.mo) if row.mo else today.month
            rev = int(row.revenue) if row.revenue else 0
            monthly_data.append((yr, mo, rev))

        if not monthly_data:
            log.info("analytics.revenue.no_historical_data")
            # Return zero forecasts for the requested months
            for offset in range(1, months_ahead + 1):
                forecast_month = _add_months(today, offset)
                period_str = forecast_month.strftime("%Y-%m")
                forecasts.append(
                    RevenueForecast(
                        period=period_str,
                        predicted_revenue_cents=0,
                        confidence_lower=0,
                        confidence_upper=0,
                        components={},
                    )
                )
            return forecasts

        # --- Linear trend ---
        n = len(monthly_data)
        revenues = [d[2] for d in monthly_data]
        avg_revenue = sum(revenues) / n

        if n >= 2:
            x_mean = (n - 1) / 2.0
            numerator = 0.0
            denominator = 0.0
            for i, (_, _, rev) in enumerate(monthly_data):
                numerator += (i - x_mean) * (rev - avg_revenue)
                denominator += (i - x_mean) ** 2
            slope = numerator / denominator if denominator != 0 else 0.0
        else:
            slope = 0.0

        # --- Seasonal index (month-of-year multiplier) ---
        month_totals: dict[int, list[int]] = {}
        for _, mo, rev in monthly_data:
            month_totals.setdefault(mo, []).append(rev)

        month_avg: dict[int, float] = {}
        for mo, revs in month_totals.items():
            month_avg[mo] = sum(revs) / len(revs) if revs else avg_revenue

        seasonal_index: dict[int, float] = {}
        for mo in range(1, 13):
            if avg_revenue > 0 and mo in month_avg:
                seasonal_index[mo] = month_avg[mo] / avg_revenue
            else:
                seasonal_index[mo] = 1.0

        # --- Department breakdown from recent data (last 3 months) ---
        three_months_ago = datetime.utcnow() - timedelta(days=90)
        dept_q = (
            select(
                InvoiceItem.item_type,
                func.coalesce(func.sum(InvoiceItem.total_cents), 0).label("dept_rev"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.status.in_(["finalized", "partially_paid", "paid"]),
                Invoice.created_at >= three_months_ago,
                Invoice.is_deleted.is_(False),
            )
            .group_by(InvoiceItem.item_type)
        )
        dept_result = await db.execute(dept_q)
        dept_rows = dept_result.all()

        # Calculate department proportions
        dept_proportions: dict[str, float] = {}
        total_dept_rev = sum(int(r.dept_rev) for r in dept_rows)
        if total_dept_rev > 0:
            for dept_row in dept_rows:
                item_type = str(dept_row.item_type) if dept_row.item_type else "other"
                dept_proportions[item_type] = int(dept_row.dept_rev) / total_dept_rev

        # --- Project forward ---
        for offset in range(1, months_ahead + 1):
            forecast_month = _add_months(today, offset)
            period_str = forecast_month.strftime("%Y-%m")
            mo = forecast_month.month

            # Base prediction: last data point + trend
            base_prediction = revenues[-1] + slope * offset

            # Apply seasonal adjustment
            season = seasonal_index.get(mo, 1.0)
            predicted = max(0, int(base_prediction * season))

            # Confidence interval
            margin = int(predicted * _CONFIDENCE_MARGIN)
            confidence_lower = max(0, predicted - margin)
            confidence_upper = predicted + margin

            # Department breakdown based on proportions
            components: dict[str, int] = {}
            for dept, proportion in dept_proportions.items():
                components[dept] = int(predicted * proportion)

            forecasts.append(
                RevenueForecast(
                    period=period_str,
                    predicted_revenue_cents=predicted,
                    confidence_lower=confidence_lower,
                    confidence_upper=confidence_upper,
                    components=components,
                )
            )

    except Exception as exc:
        log.warning("analytics.revenue.forecast_failed", error=str(exc))
        # Return empty forecasts on failure
        for offset in range(1, months_ahead + 1):
            forecast_month = _add_months(date.today(), offset)
            period_str = forecast_month.strftime("%Y-%m")
            forecasts.append(
                RevenueForecast(
                    period=period_str,
                    predicted_revenue_cents=0,
                    confidence_lower=0,
                    confidence_upper=0,
                    components={},
                )
            )

    log.info("analytics.revenue.forecast_complete", forecast_count=len(forecasts))
    return forecasts


def _add_months(base_date: date, months: int) -> date:
    """
    Add a number of months to a date, handling year rollover.

    @param base_date: Starting date
    @param months: Number of months to add
    @returns New date with months added
    """
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    # Clamp day to valid range for the target month
    import calendar

    max_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, max_day)
    return date(year, month, day)
