"""Aifya usage billing - how the hospital's own bill to Aifya is computed.

The rule, in one paragraph
--------------------------
Aifya charges the hospital, not the patient, for the days a patient uses the
system. One patient on one calendar day is one *patient-day*. A patient who
passes through Registration and is then also seen in Emergency that same day,
or who is lying in a ward that day, is a single patient-day, never two. Over a
month the daily counts add up to the patient-day total, and that total times
the facility's rate is the bill.

Where each day's usage comes from
---------------------------------
Two sources are read and then merged:

* **Encounters.** An encounter whose type is ``emergency`` marks the patient as
  having arrived through Emergency; every other encounter type marks them as
  having arrived through Registration. ``cancelled`` and soft-deleted
  encounters are ignored.
* **Admissions.** A patient occupies a bed on every calendar day from
  ``admitted_at`` to ``discharged_at`` inclusive, or to today while they are
  still admitted. This is what makes a four-day stay four patient-days even
  when only one encounter was recorded.

Because a patient can be in two sources on the same day, each day is collapsed
to one row per patient and attributed by priority - **Inpatient, then
Emergency, then Registration**. The channel counts therefore partition the
daily total rather than overlapping it, so they always sum to it exactly.

Nothing in this module touches patient invoices. It is a separate ledger for a
separate debtor.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aifya_usage import (
    DEFAULT_USAGE_CURRENCY,
    DEFAULT_USAGE_RATE_CENTS,
    AifyaUsageConfig,
    AifyaUsageDaily,
    AifyaUsageInvoice,
)
from app.models.encounter import Encounter
from app.models.facility import Facility
from app.models.ipd import Admission

#: Encounter type that means "this patient came through Emergency". Every
#: other type is treated as a Registration-channel arrival.
EMERGENCY_ENCOUNTER_TYPE = "emergency"

#: Used when the facility record carries no usable IANA timezone. The day
#: boundary has to be the hospital's midnight, not the server's.
FALLBACK_TIMEZONE = "Africa/Nairobi"

#: An encounter in this state was called off, so it is not usage.
CANCELLED_ENCOUNTER_STATUS = "cancelled"

#: How long the hospital has to settle an issued invoice.
INVOICE_TERM_DAYS = 30


def safe_timezone(value: str | None) -> str:
    """
    Return an IANA timezone name the database will accept.

    @param value: Timezone from the facility record, possibly blank or invalid
    @returns The given timezone when it resolves, otherwise the fallback
    """
    if not value:
        return FALLBACK_TIMEZONE
    try:
        ZoneInfo(value)
    except Exception:
        return FALLBACK_TIMEZONE
    return value


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """
    First and last calendar day of a month, both inclusive.

    @param year: Calendar year
    @param month: Calendar month, 1-12
    @returns Tuple of (first day, last day)
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def today_in(timezone: str) -> date:
    """
    Today's date as the hospital experiences it.

    @param timezone: IANA timezone name
    @returns The current calendar date in that timezone
    """
    return datetime.now(UTC).astimezone(ZoneInfo(timezone)).date()


def period_label(year: int, month: int) -> str:
    """
    @param year: Calendar year
    @param month: Calendar month, 1-12
    @returns Human-readable period, e.g. "September 2026"
    """
    return f"{calendar.month_name[month]} {year}"


#: Highest invoice sequence already used in a period, counting voided and
#: soft-deleted rows. Reading only the live rows would hand the same number out
#: twice after a void and collide on the unique index.
_NEXT_INVOICE_SEQ_SQL = text(
    """
    SELECT COALESCE(
               max(CAST(split_part(invoice_number, '-', 3) AS integer)), 0
           )
      FROM aifya_usage_invoices
     WHERE facility_id = CAST(:facility_id AS uuid)
       AND period_year = :year
       AND period_month = :month
    """
)


@dataclass(frozen=True)
class UsageDay:
    """
    One billed day, in the shape the API returns it.

    Built either from the stored ledger or from live metering - the caller does
    not need to know which - so that the HR usage screen and the Reports usage
    calculator show the same figure for the same month.
    """

    usage_date: date
    registration_patients: int
    emergency_patients: int
    inpatient_patients: int
    total_billable_patients: int
    rate_cents: int
    currency: str
    amount_cents: int
    is_finalized: bool
    computed_at: datetime | None = None


class AifyaUsageService:
    """Reads, recomputes and bills the facility's Aifya usage ledger."""

    def __init__(self, db: AsyncSession) -> None:
        """
        @param db: Request-scoped session. The caller commits; this service
            only flushes, because the tenant context is transaction-local.
        """
        self.db = db

    # -- configuration --------------------------------------------------

    async def get_config(
        self, facility_id: uuid.UUID
    ) -> tuple[int, str, bool, str | None]:
        """
        Current rate for the facility.

        @param facility_id: Facility UUID
        @returns (rate_cents, currency, is_configured, notes)
        """
        row = (
            await self.db.execute(
                select(AifyaUsageConfig).where(
                    AifyaUsageConfig.facility_id == facility_id,
                    AifyaUsageConfig.is_deleted.is_(False),
                )
            )
        ).scalars().first()
        if row is None:
            return DEFAULT_USAGE_RATE_CENTS, DEFAULT_USAGE_CURRENCY, False, None
        return row.rate_cents, row.currency, True, row.notes

    async def set_config(
        self,
        facility_id: uuid.UUID,
        rate_cents: int,
        currency: str,
        notes: str | None,
        actor_id: uuid.UUID | None = None,
    ) -> AifyaUsageConfig:
        """
        Create or update the facility's rate.

        @param facility_id: Facility UUID
        @param rate_cents: New price of one patient-day, in cents
        @param currency: ISO currency code
        @param notes: Free-text note explaining the rate
        @param actor_id: Staff member making the change
        @returns The stored configuration row
        """
        row = (
            await self.db.execute(
                select(AifyaUsageConfig).where(
                    AifyaUsageConfig.facility_id == facility_id
                )
            )
        ).scalars().first()
        if row is None:
            row = AifyaUsageConfig(
                facility_id=facility_id,
                rate_cents=rate_cents,
                currency=currency,
                notes=notes,
                created_by=actor_id,
            )
            self.db.add(row)
        else:
            row.rate_cents = rate_cents
            row.currency = currency
            row.notes = notes
            row.updated_by = actor_id
            row.is_deleted = False
        await self.db.flush()
        return row

    # -- computation ----------------------------------------------------

    async def _facility_timezone(self, facility_id: uuid.UUID) -> str:
        """
        @param facility_id: Facility UUID
        @returns An IANA timezone name safe to hand to the database
        """
        value = (
            await self.db.execute(
                select(Facility.timezone).where(Facility.id == facility_id)
            )
        ).scalar_one_or_none()
        return safe_timezone(value)

    async def _day_buckets(
        self,
        facility_id: uuid.UUID,
        start_date: date,
        end_date: date,
        timezone: str,
        *,
        today: date | None = None,
    ) -> dict[date, tuple[int, int, int, int]]:
        """
        Distinct patients per day, split by channel.

        Encounters decide how a patient arrived; admissions decide whether they
        held a bed. Both sources are collapsed to one row per (day, patient)
        and then attributed by priority - the ward first, then Emergency, then
        Registration - so the three channels partition the day rather than
        overlapping it.

        The comparison is deliberately done on the hospital's local calendar
        date, so a night shift's 23:00 admission belongs to the day the ward
        staff would call it. Rows are fetched with a one-day margin either side
        of the window and then filtered here, because the local date cannot be
        expressed portably in SQL.

        @param facility_id: Facility UUID
        @param start_date: First day, inclusive
        @param end_date: Last day, inclusive
        @param timezone: Facility timezone used for the day boundary
        @param today: Reference day for admissions still open; defaults to the
            current day in the facility timezone
        @returns Mapping of day -> (registration, emergency, inpatient, total)
        """

        def utc_midnight(day: date) -> datetime:
            """@return Midnight UTC on the given calendar day."""
            return datetime(day.year, day.month, day.day, tzinfo=UTC)

        zone = ZoneInfo(timezone)
        reference = today or today_in(timezone)
        margin = timedelta(days=1)

        # -- how each patient arrived, by local day ----------------------
        arrival: dict[tuple[date, uuid.UUID], list[bool]] = {}
        encounter_rows = (
            await self.db.execute(
                select(
                    Encounter.patient_id,
                    Encounter.encounter_date,
                    Encounter.encounter_type,
                ).where(
                    Encounter.facility_id == facility_id,
                    Encounter.is_deleted.is_(False),
                    Encounter.status != CANCELLED_ENCOUNTER_STATUS,
                    Encounter.encounter_date >= utc_midnight(start_date - margin),
                    Encounter.encounter_date
                    < utc_midnight(end_date + margin + timedelta(days=1)),
                )
            )
        ).all()
        for patient_id, occurred_at, encounter_type in encounter_rows:
            usage_date = occurred_at.astimezone(zone).date()
            if usage_date < start_date or usage_date > end_date:
                continue
            flags = arrival.setdefault((usage_date, patient_id), [False, False])
            if encounter_type == EMERGENCY_ENCOUNTER_TYPE:
                flags[1] = True
            else:
                flags[0] = True

        # -- who held a bed, by local day --------------------------------
        bed_days: set[tuple[date, uuid.UUID]] = set()
        admission_rows = (
            await self.db.execute(
                select(
                    Admission.patient_id,
                    Admission.admitted_at,
                    Admission.discharged_at,
                ).where(
                    Admission.facility_id == facility_id,
                    Admission.is_deleted.is_(False),
                    Admission.admitted_at < utc_midnight(end_date + margin + margin),
                    or_(
                        Admission.discharged_at.is_(None),
                        Admission.discharged_at >= utc_midnight(start_date - margin),
                    ),
                )
            )
        ).all()
        for patient_id, admitted_at, discharged_at in admission_rows:
            first = max(admitted_at.astimezone(zone).date(), start_date)
            left_on = (
                discharged_at.astimezone(zone).date()
                if discharged_at is not None
                else reference
            )
            last = min(left_on, end_date)
            usage_date = first
            while usage_date <= last:
                bed_days.add((usage_date, patient_id))
                usage_date += timedelta(days=1)

        # -- one row per patient per day, then attributed by priority ----
        # A patient can arrive more than one way in a day; the ward wins,
        # then Emergency, then Registration, so the channels stay a partition.
        patients_by_day: dict[date, set[uuid.UUID]] = {}
        for usage_date, patient_id in set(arrival) | bed_days:
            patients_by_day.setdefault(usage_date, set()).add(patient_id)

        buckets: dict[date, tuple[int, int, int, int]] = {}
        for usage_date, patients in patients_by_day.items():
            registration = emergency = inpatient = 0
            for patient_id in patients:
                # arrival flags are [seen at reception, seen in emergency]
                flags = arrival.get((usage_date, patient_id), (False, False))
                if (usage_date, patient_id) in bed_days:
                    inpatient += 1
                elif flags[1]:
                    emergency += 1
                else:
                    registration += 1
            buckets[usage_date] = (
                registration,
                emergency,
                inpatient,
                registration + emergency + inpatient,
            )
        return buckets

    async def day_buckets(
        self,
        facility_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        today: date | None = None,
    ) -> dict[date, tuple[int, int, int, int]]:
        """
        Distinct patients per day for a range, split by channel.

        This is the single definition in Aifya of what a billable day is. Both
        the HR usage ledger and the Reports usage calculator read it, which is
        what keeps the two surfaces showing the same figure.

        @param facility_id: Facility UUID
        @param start_date: First day, inclusive
        @param end_date: Last day, inclusive
        @param today: Reference day for admissions still open; defaults to the
            current day in the facility timezone
        @returns Mapping of day -> (registration, emergency, inpatient, total)
        """
        timezone = await self._facility_timezone(facility_id)
        return await self._day_buckets(
            facility_id, start_date, end_date, timezone, today=today
        )

    async def recompute_range(
        self,
        facility_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        force: bool = False,
        actor_id: uuid.UUID | None = None,
    ) -> list[AifyaUsageDaily]:
        """
        Recompute and store the ledger for every day in a range.

        Idempotent: running it twice over the same range produces the same
        rows. Days already finalized are left alone unless ``force`` is set.

        @param facility_id: Facility UUID
        @param start_date: First day, inclusive
        @param end_date: Last day, inclusive
        @param force: Recompute even finalized days
        @param actor_id: Staff member triggering the recompute
        @returns The ledger rows for the range, oldest first
        """
        if end_date < start_date:
            raise ValueError("end_date must not be before start_date")

        timezone = await self._facility_timezone(facility_id)
        rate_cents, currency, _, _ = await self.get_config(facility_id)
        buckets = await self._day_buckets(
            facility_id, start_date, end_date, timezone
        )

        existing_rows = (
            await self.db.execute(
                select(AifyaUsageDaily).where(
                    AifyaUsageDaily.facility_id == facility_id,
                    AifyaUsageDaily.usage_date >= start_date,
                    AifyaUsageDaily.usage_date <= end_date,
                )
            )
        ).scalars().all()
        existing = {row.usage_date: row for row in existing_rows}

        now = datetime.now(UTC)
        touched: list[AifyaUsageDaily] = []
        day = start_date
        while day <= end_date:
            registration, emergency, inpatient, total = buckets.get(
                day, (0, 0, 0, 0)
            )
            row = existing.get(day)

            if row is not None and row.is_finalized and not force:
                touched.append(row)
                day += timedelta(days=1)
                continue

            # A day with no usage and no history needs no ledger row; keeping
            # the ledger to days that actually happened keeps the report
            # readable. A day that *had* usage and lost it is still corrected
            # below, because its row already exists.
            if row is None and total == 0:
                day += timedelta(days=1)
                continue

            if row is None:
                row = AifyaUsageDaily(
                    facility_id=facility_id,
                    usage_date=day,
                    created_by=actor_id,
                )
                self.db.add(row)

            row.registration_patients = registration
            row.emergency_patients = emergency
            row.inpatient_patients = inpatient
            row.total_billable_patients = total
            row.rate_cents = rate_cents
            row.currency = currency
            row.amount_cents = total * rate_cents
            row.updated_by = actor_id
            row.computed_at = now
            touched.append(row)
            day += timedelta(days=1)

        await self.db.flush()
        touched.sort(key=lambda item: item.usage_date)
        return touched

    # -- reporting ------------------------------------------------------

    async def ledger_for_month(
        self, facility_id: uuid.UUID, year: int, month: int
    ) -> list[AifyaUsageDaily]:
        """
        Stored ledger rows for one calendar month, oldest first.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @returns Ledger rows
        """
        start_date, end_date = month_bounds(year, month)
        return await self.ledger_for_range(facility_id, start_date, end_date)

    async def ledger_for_range(
        self, facility_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[AifyaUsageDaily]:
        """
        Stored ledger rows between two days inclusive, oldest first.

        @param facility_id: Facility UUID
        @param start_date: First day, inclusive
        @param end_date: Last day, inclusive
        @returns Ledger rows
        """
        rows = (
            await self.db.execute(
                select(AifyaUsageDaily)
                .where(
                    AifyaUsageDaily.facility_id == facility_id,
                    AifyaUsageDaily.usage_date >= start_date,
                    AifyaUsageDaily.usage_date <= end_date,
                    AifyaUsageDaily.is_deleted.is_(False),
                )
                .order_by(AifyaUsageDaily.usage_date.asc())
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    def totals(rows: list[AifyaUsageDaily]) -> dict[str, int | bool]:
        """
        Sum a set of ledger rows.

        Amounts are summed per row rather than recomputed from the total,
        because days may legitimately carry different snapshotted rates.

        @param rows: Ledger rows
        @returns Aggregate totals
        """
        return {
            "total_patient_days": sum(r.total_billable_patients for r in rows),
            "registration_patient_days": sum(r.registration_patients for r in rows),
            "emergency_patient_days": sum(r.emergency_patients for r in rows),
            "inpatient_patient_days": sum(r.inpatient_patients for r in rows),
            "total_amount_cents": sum(r.amount_cents for r in rows),
            "is_finalized": bool(rows) and all(r.is_finalized for r in rows),
        }

    async def month_view(
        self,
        facility_id: uuid.UUID,
        year: int,
        month: int,
        *,
        today: date | None = None,
    ) -> list[UsageDay]:
        """
        A month's billable days, already priced.

        An open month is metered live, so the figure is current without anyone
        having to run an accrual first. A month that has been finalized is read
        from the frozen ledger, so a figure an invoice was already raised on
        cannot drift. Both the HR usage screen and the Reports usage calculator
        call this, which is what keeps the two showing one number.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @param today: Reference day for admissions still open; defaults to
            today in the facility timezone
        @returns Priced days, oldest first; days with no usage are omitted
        """
        stored = await self.ledger_for_month(facility_id, year, month)
        if any(row.is_finalized for row in stored):
            return [
                UsageDay(
                    usage_date=row.usage_date,
                    registration_patients=row.registration_patients,
                    emergency_patients=row.emergency_patients,
                    inpatient_patients=row.inpatient_patients,
                    total_billable_patients=row.total_billable_patients,
                    rate_cents=row.rate_cents,
                    currency=row.currency,
                    amount_cents=row.amount_cents,
                    is_finalized=row.is_finalized,
                    computed_at=row.computed_at,
                )
                for row in stored
            ]

        rate_cents, currency, _, _ = await self.get_config(facility_id)
        start_date, end_date = month_bounds(year, month)
        buckets = await self.day_buckets(
            facility_id, start_date, end_date, today=today
        )
        computed_at = datetime.now(UTC)
        days: list[UsageDay] = []
        for usage_date in sorted(buckets):
            registration, emergency, inpatient, total = buckets[usage_date]
            if total == 0:
                continue
            days.append(
                UsageDay(
                    usage_date=usage_date,
                    registration_patients=registration,
                    emergency_patients=emergency,
                    inpatient_patients=inpatient,
                    total_billable_patients=total,
                    rate_cents=rate_cents,
                    currency=currency,
                    amount_cents=total * rate_cents,
                    is_finalized=False,
                    computed_at=computed_at,
                )
            )
        return days

    async def finalize_month(
        self,
        facility_id: uuid.UUID,
        year: int,
        month: int,
        actor_id: uuid.UUID | None = None,
    ) -> list[AifyaUsageDaily]:
        """
        Close a month so its figures can no longer drift.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @param actor_id: Staff member closing the month
        @returns The finalized rows
        """
        rows = await self.ledger_for_month(facility_id, year, month)
        now = datetime.now(UTC)
        for row in rows:
            row.is_finalized = True
            row.finalized_at = now
            row.updated_by = actor_id
        await self.db.flush()
        return rows

    # -- invoicing ------------------------------------------------------

    async def list_invoices(
        self, facility_id: uuid.UUID
    ) -> list[AifyaUsageInvoice]:
        """
        Every invoice raised for the facility, newest period first.

        @param facility_id: Facility UUID
        @returns Invoice rows
        """
        rows = (
            await self.db.execute(
                select(AifyaUsageInvoice)
                .where(
                    AifyaUsageInvoice.facility_id == facility_id,
                    AifyaUsageInvoice.is_deleted.is_(False),
                )
                .order_by(
                    AifyaUsageInvoice.period_year.desc(),
                    AifyaUsageInvoice.period_month.desc(),
                )
            )
        ).scalars().all()
        return list(rows)

    async def get_invoice(
        self, facility_id: uuid.UUID, invoice_id: uuid.UUID
    ) -> AifyaUsageInvoice | None:
        """
        @param facility_id: Facility UUID
        @param invoice_id: Invoice UUID
        @returns The invoice, or None when it does not exist for this facility
        """
        return (
            await self.db.execute(
                select(AifyaUsageInvoice).where(
                    AifyaUsageInvoice.facility_id == facility_id,
                    AifyaUsageInvoice.id == invoice_id,
                    AifyaUsageInvoice.is_deleted.is_(False),
                )
            )
        ).scalars().first()

    async def invoice_for_month(
        self, facility_id: uuid.UUID, year: int, month: int
    ) -> AifyaUsageInvoice | None:
        """
        The live invoice for a period, if one has been raised.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @returns The invoice, or None
        """
        return (
            await self.db.execute(
                select(AifyaUsageInvoice).where(
                    AifyaUsageInvoice.facility_id == facility_id,
                    AifyaUsageInvoice.period_year == year,
                    AifyaUsageInvoice.period_month == month,
                    AifyaUsageInvoice.status != "void",
                    AifyaUsageInvoice.is_deleted.is_(False),
                )
            )
        ).scalars().first()

    async def _next_invoice_number(
        self, facility_id: uuid.UUID, year: int, month: int
    ) -> str:
        """
        Next unused invoice number for a period.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @returns Number of the form AIU-YYYYMM-NNNN
        """
        used = (
            await self.db.execute(
                _NEXT_INVOICE_SEQ_SQL,
                {
                    "facility_id": str(facility_id),
                    "year": year,
                    "month": month,
                },
            )
        ).scalar_one()
        return "AIU-%04d%02d-%04d" % (year, month, int(used) + 1)

    async def generate_invoice(
        self,
        facility_id: uuid.UUID,
        year: int,
        month: int,
        *,
        notes: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> AifyaUsageInvoice:
        """
        Raise, or refresh, the invoice for a calendar month from the ledger.

        A draft is refreshed so it tracks any late ledger corrections. An
        invoice that has already been issued is returned untouched, because by
        then it is a statement of what was billed rather than a live view.

        @param facility_id: Facility UUID
        @param year: Calendar year
        @param month: Calendar month, 1-12
        @param notes: Free-text note carried on the invoice
        @param actor_id: Staff member raising the invoice
        @returns The invoice
        @raises ValueError: When the month holds no usage to invoice
        """
        rows = await self.ledger_for_month(facility_id, year, month)
        if not rows:
            raise ValueError("no usage recorded for this period")

        agg = self.totals(rows)
        rates = {row.rate_cents for row in rows}
        existing = await self.invoice_for_month(facility_id, year, month)

        if existing is not None and existing.status != "draft":
            return existing

        invoice = existing
        if invoice is None:
            invoice = AifyaUsageInvoice(
                facility_id=facility_id,
                invoice_number=await self._next_invoice_number(
                    facility_id, year, month
                ),
                period_year=year,
                period_month=month,
                status="draft",
                created_by=actor_id,
            )
            self.db.add(invoice)

        invoice.patient_days = int(agg["total_patient_days"])
        invoice.registration_patient_days = int(agg["registration_patient_days"])
        invoice.emergency_patient_days = int(agg["emergency_patient_days"])
        invoice.inpatient_patient_days = int(agg["inpatient_patient_days"])
        invoice.rate_cents = rows[0].rate_cents if len(rates) == 1 else None
        invoice.amount_cents = int(agg["total_amount_cents"])
        invoice.currency = rows[0].currency
        if notes is not None:
            invoice.notes = notes
        invoice.updated_by = actor_id
        await self.db.flush()
        return invoice

    async def issue_invoice(
        self,
        facility_id: uuid.UUID,
        invoice_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
    ) -> AifyaUsageInvoice | None:
        """
        Mark a draft invoice as issued and start its payment term.

        @param facility_id: Facility UUID
        @param invoice_id: Invoice UUID
        @param actor_id: Staff member issuing it
        @returns The invoice, or None when it does not exist
        """
        invoice = await self.get_invoice(facility_id, invoice_id)
        if invoice is None:
            return None
        if invoice.status == "draft":
            now = datetime.now(UTC)
            invoice.status = "issued"
            invoice.issued_at = now
            invoice.due_at = now + timedelta(days=INVOICE_TERM_DAYS)
            invoice.updated_by = actor_id
            await self.db.flush()
        return invoice

    async def record_invoice_payment(
        self,
        facility_id: uuid.UUID,
        invoice_id: uuid.UUID,
        amount_cents: int,
        reference: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> AifyaUsageInvoice | None:
        """
        Record money received against an issued invoice.

        The invoice flips to paid only once the payments cover it in full, so a
        partial settlement leaves it visibly outstanding.

        @param facility_id: Facility UUID
        @param invoice_id: Invoice UUID
        @param amount_cents: Amount received, in cents
        @param reference: Bank or M-Pesa reference
        @param actor_id: Staff member recording it
        @returns The invoice, or None when it does not exist
        @raises ValueError: When the invoice cannot lawfully receive payment
        """
        invoice = await self.get_invoice(facility_id, invoice_id)
        if invoice is None:
            return None
        if invoice.status == "draft":
            raise ValueError("issue the invoice before recording payment")
        if invoice.status == "void":
            raise ValueError("a voided invoice cannot receive payment")

        invoice.paid_cents += amount_cents
        if reference:
            invoice.payment_reference = reference
        if invoice.paid_cents >= invoice.amount_cents:
            invoice.paid_cents = invoice.amount_cents
            invoice.status = "paid"
            invoice.paid_at = datetime.now(UTC)
        invoice.updated_by = actor_id
        await self.db.flush()
        return invoice

    async def void_invoice(
        self,
        facility_id: uuid.UUID,
        invoice_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
    ) -> AifyaUsageInvoice | None:
        """
        Cancel an invoice that has taken no money.

        @param facility_id: Facility UUID
        @param invoice_id: Invoice UUID
        @param actor_id: Staff member voiding it
        @returns The invoice, or None when it does not exist
        @raises ValueError: When money has already been received against it
        """
        invoice = await self.get_invoice(facility_id, invoice_id)
        if invoice is None:
            return None
        if invoice.paid_cents > 0:
            raise ValueError("an invoice with payments recorded cannot be voided")
        invoice.status = "void"
        invoice.updated_by = actor_id
        await self.db.flush()
        return invoice
