"""
Facility usage billing: what the hospital owes Aifya for the month.

The rule lives in exactly one place. This module does not decide what counts -
:class:`~app.services.aifya_usage_service.AifyaUsageService` does - it reads the
same per-day, per-patient buckets and prices them. The Reports calculator and
the HR Aifya Usage screen therefore cannot disagree about a month's usage.

Aifya charges the hospital a flat rate for each *patient-day*:

* a patient seen at reception is one patient-day,
* a patient who arrived through the emergency department is one patient-day,
* every calendar day an inpatient spends on a ward - admission day and
  discharge day included - is one patient-day.

A patient who comes through more than one of those doors on the same calendar
day is still one patient-day. It is attributed to the ward if they are in a bed,
otherwise to Emergency, otherwise to Reception. Nothing here is invoiced to the
patient. This is the platform charge the hospital pays for the volume it
handled, and the report exists so that charge can be read, checked and settled
at the end of each month rather than taken on trust.

Money is integer KES cents everywhere in Aifya.

An open month is metered live; once a month is finalized it is read from the
frozen ledger, so a figure an invoice was already raised on cannot drift.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.report import (
    UsageBillingLine,
    UsageBillingMonth,
    UsageBillingReport,
    UsageBillingTrend,
)
from app.services.aifya_usage_service import AifyaUsageService

#: Stable line keys, so the web app and any downstream export agree on names.
#: The names predate the patient-day rework and are kept so the screens and any
#: saved export keep resolving; the labels beside them carry the real meaning.
LINE_RECEPTION = "reception_registrations"
LINE_EMERGENCY = "emergency_registrations"
LINE_IPD = "ipd_bed_days"

#: Days after the end of the billing month before the charge falls due. The
#: month-end demand gives the hospital a fortnight to settle.
PAYMENT_TERMS_DAYS = 15

#: How far back the rolling trend may be asked to look.
MAX_TREND_MONTHS = 24


def month_start(month: str) -> date:
    """
    Parse a ``YYYY-MM`` billing month into its first calendar day.

    @param month: Billing month, e.g. ``2026-09``
    @returns First day of that month
    @raises ValueError: When the string is not a ``YYYY-MM`` month
    """
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"Invalid billing month {month!r}; use YYYY-MM") from exc
    return date(parsed.year, parsed.month, 1)


def month_end(first_day: date) -> date:
    """
    Return the last calendar day of the month that starts on ``first_day``.

    @param first_day: First day of the month
    @returns Last day of the same month
    """
    return first_day.replace(day=monthrange(first_day.year, first_day.month)[1])


def current_month(today: date | None = None) -> str:
    """
    Return the billing month the report defaults to.

    @param today: Reference day, defaults to today in UTC
    @returns Billing month as ``YYYY-MM``
    """
    reference = today or datetime.now(UTC).date()
    return f"{reference.year:04d}-{reference.month:02d}"


def shift_month(first_day: date, months: int) -> date:
    """
    Move a month start forward or backward by whole months.

    @param first_day: First day of the starting month
    @param months: Number of months to move (negative moves backwards)
    @returns First day of the shifted month
    """
    index = (first_day.year * 12 + (first_day.month - 1)) + months
    return date(index // 12, index % 12 + 1, 1)


class UsageBillingService:
    """
    Meter one facility's patient-days and price them for the month.

    Every read is scoped to a single facility, so a hospital can only ever be
    charged for its own registrations and admissions.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        @param db: Request-scoped database session
        """
        self.db = db

    async def build_report(
        self,
        facility_id: uuid.UUID,
        month: str,
        rate_cents: int | None = None,
        currency: str | None = None,
        today: date | None = None,
    ) -> UsageBillingReport:
        """
        Price one billing month.

        The days come from the same month view the HR Aifya Usage screen reads,
        so the two screens cannot disagree: an open month is metered live, and a
        finalized month keeps the figure its invoice was raised on. The rate
        defaults to the rate this facility is actually billed at, so opening the
        calculator without typing a rate reproduces the HR figure; passing a
        rate overrides it for a what-if run.

        @param facility_id: Facility UUID
        @param month: Billing month as ``YYYY-MM``
        @param rate_cents: Charge per patient-day in KES cents, or None for the
            facility's configured rate
        @param currency: ISO currency code for display, or None for the
            facility's configured usage currency
        @param today: Reference day for admissions still open, defaults to
            today in UTC
        @returns Priced, line-by-line usage report
        @raises ValueError: When the month is not ``YYYY-MM``
        """
        first_day = month_start(month)
        last_day = month_end(first_day)

        usage = AifyaUsageService(self.db)
        days = await usage.month_view(
            facility_id, first_day.year, first_day.month, today=today
        )
        configured_rate, configured_currency, _, _ = await usage.get_config(
            facility_id
        )

        quantities = {
            LINE_RECEPTION: sum(day.registration_patients for day in days),
            LINE_EMERGENCY: sum(day.emergency_patients for day in days),
            LINE_IPD: sum(day.inpatient_patients for day in days),
        }

        if rate_cents is None:
            # Price every day at the rate it was metered at, so a month whose
            # rate changed mid-month - or one already finalized - adds up to the
            # ledger exactly instead of to a re-priced approximation.
            amounts = {
                LINE_RECEPTION: sum(
                    day.registration_patients * day.rate_cents for day in days
                ),
                LINE_EMERGENCY: sum(
                    day.emergency_patients * day.rate_cents for day in days
                ),
                LINE_IPD: sum(day.inpatient_patients * day.rate_cents for day in days),
            }
            price = days[-1].rate_cents if days else configured_rate
        else:
            # A what-if run re-prices the same days at the rate supplied.
            price = rate_cents
            amounts = {
                key: quantity * rate_cents for key, quantity in quantities.items()
            }

        display_currency = currency or (
            days[-1].currency if days else configured_currency
        )

        lines = [
            UsageBillingLine(
                key=LINE_RECEPTION,
                label="Registration patient-days",
                quantity=quantities[LINE_RECEPTION],
                rate_cents=price,
                amount_cents=amounts[LINE_RECEPTION],
            ),
            UsageBillingLine(
                key=LINE_EMERGENCY,
                label="Emergency patient-days",
                quantity=quantities[LINE_EMERGENCY],
                rate_cents=price,
                amount_cents=amounts[LINE_EMERGENCY],
            ),
            UsageBillingLine(
                key=LINE_IPD,
                label="Inpatient bed-days",
                quantity=quantities[LINE_IPD],
                rate_cents=price,
                amount_cents=amounts[LINE_IPD],
            ),
        ]

        return UsageBillingReport(
            facility_id=facility_id,
            month=f"{first_day.year:04d}-{first_day.month:02d}",
            date_from=first_day,
            date_to=last_day,
            currency=display_currency,
            rate_cents=price,
            lines=lines,
            total_quantity=sum(quantities.values()),
            total_cents=sum(amounts.values()),
            due_date=shift_month(first_day, 1) + timedelta(days=PAYMENT_TERMS_DAYS - 1),
            generated_at=datetime.now(UTC),
        )

    async def build_trend(
        self,
        facility_id: uuid.UUID,
        months: int,
        rate_cents: int | None = None,
        end_month: str | None = None,
        currency: str | None = None,
        today: date | None = None,
    ) -> UsageBillingTrend:
        """
        Build a rolling month-by-month usage charge, oldest month first.

        @param facility_id: Facility UUID
        @param months: Number of months to include (1..MAX_TREND_MONTHS)
        @param rate_cents: Charge per patient-day in KES cents, or None for the
            facility's configured rate
        @param end_month: Last month to include, defaults to the current month
        @param currency: ISO currency code for display, or None for the
            facility's configured usage currency
        @param today: Reference day, defaults to today in UTC
        @returns Rolling usage trend
        @raises ValueError: When the month or the month count is out of range
        """
        if months < 1 or months > MAX_TREND_MONTHS:
            raise ValueError(
                f"months must be between 1 and {MAX_TREND_MONTHS}"
            )

        reference = today or datetime.now(UTC).date()
        last_month = month_start(end_month or current_month(reference))
        first_month = shift_month(last_month, -(months - 1))

        entries: list[UsageBillingMonth] = []
        total_cents = 0
        for offset in range(months):
            start = shift_month(first_month, offset)
            report = await self.build_report(
                facility_id=facility_id,
                month=f"{start.year:04d}-{start.month:02d}",
                rate_cents=rate_cents,
                currency=currency,
                today=reference,
            )
            entries.append(
                UsageBillingMonth(
                    month=report.month,
                    reception_registrations=report.lines[0].quantity,
                    emergency_registrations=report.lines[1].quantity,
                    ipd_bed_days=report.lines[2].quantity,
                    total_quantity=report.total_quantity,
                    total_cents=report.total_cents,
                )
            )
            total_cents += report.total_cents

        return UsageBillingTrend(
            currency=report.currency,
            rate_cents=report.rate_cents,
            months=entries,
            total_cents=total_cents,
        )
