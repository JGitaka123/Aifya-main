"""
Hospital performance KPI calculation.
Computes facility-wide metrics on demand from existing tables (encounters,
admissions, lab orders, billing, insurance claims, attendance).

All KPIs are computed without ETL — read from operational tables directly.
For volume facilities this should later move to a materialized view, but
the API contract stays stable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class KpiTrendPoint:
    """A single point in a KPI trend series."""

    bucket: str  # ISO date or YYYY-MM
    value: float


@dataclass(frozen=True)
class FacilityKpis:
    """All facility KPIs for a given window."""

    period_start: date
    period_end: date
    patient_volume: float                # encounters per day average
    bed_occupancy_rate: float            # 0-100 %
    average_length_of_stay: float        # days
    readmission_rate: float              # 0-100 %
    revenue_per_patient: float           # KES (whole)
    claim_rejection_rate: float          # 0-100 %
    lab_turnaround_time: float           # avg hours
    emergency_response_time: float       # avg minutes
    staff_attendance_rate: float         # 0-100 %
    patient_satisfaction: float          # 0-100 score (placeholder)
    total_encounters: int
    total_admissions: int
    total_revenue: float                 # KES whole


def _start_of_day(d: date) -> datetime:
    """Return UTC datetime for the start of a date."""
    return datetime.combine(d, time.min, tzinfo=UTC)


def _end_of_day(d: date) -> datetime:
    """Return UTC datetime for the end of a date (inclusive)."""
    return datetime.combine(d, time.max, tzinfo=UTC)


async def get_facility_kpis(
    db: AsyncSession,
    facility_id: uuid.UUID,
    start: date,
    end: date,
) -> FacilityKpis:
    """
    Compute all facility KPIs for the given window.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param start: Inclusive start date (Africa/Nairobi day)
    @param end: Inclusive end date
    @returns Computed KPIs
    """
    if end < start:
        start, end = end, start

    days = max((end - start).days + 1, 1)
    start_dt = _start_of_day(start)
    end_dt = _end_of_day(end)

    # Lazy imports to avoid circular dependencies at module import time
    from app.models.billing import Payment
    from app.models.emergency import EmergencyVisit
    from app.models.encounter import Encounter
    from app.models.hr import Attendance
    from app.models.insurance import InsuranceClaim
    from app.models.ipd import Admission, Bed
    from app.models.lab import LabOrder, LabResult

    # ── Patient volume ────────────────────────────────────────────────────
    enc_q = await db.execute(
        select(func.count(Encounter.id)).where(
            Encounter.facility_id == facility_id,
            Encounter.encounter_date >= start_dt,
            Encounter.encounter_date <= end_dt,
            Encounter.is_deleted == False,  # noqa: E712
        )
    )
    total_encounters = int(enc_q.scalar() or 0)
    patient_volume = total_encounters / days

    # ── Bed occupancy ─────────────────────────────────────────────────────
    bed_total_q = await db.execute(
        select(func.count(Bed.id)).where(
            Bed.facility_id == facility_id,
            Bed.is_deleted == False,  # noqa: E712
        )
    )
    total_beds = int(bed_total_q.scalar() or 0)

    bed_occ_q = await db.execute(
        select(func.count(Bed.id)).where(
            Bed.facility_id == facility_id,
            Bed.status == "occupied",
            Bed.is_deleted == False,  # noqa: E712
        )
    )
    occupied = int(bed_occ_q.scalar() or 0)
    bed_occupancy_rate = (occupied / total_beds * 100) if total_beds else 0.0

    # ── Length of stay & readmission ──────────────────────────────────────
    adm_q = await db.execute(
        select(
            func.count(Admission.id),
            func.avg(Admission.length_of_stay_days),
        ).where(
            Admission.facility_id == facility_id,
            Admission.discharged_at >= start_dt,
            Admission.discharged_at <= end_dt,
            Admission.is_deleted == False,  # noqa: E712
        )
    )
    adm_count, avg_los = adm_q.one()
    total_admissions = int(adm_count or 0)
    average_length_of_stay = float(avg_los or 0)

    # Readmission: same patient admitted within 30 days of a discharge in window
    readmission_count = 0
    if total_admissions:
        readmits_q = await db.execute(
            select(func.count(Admission.id)).where(
                Admission.facility_id == facility_id,
                Admission.admitted_at >= start_dt,
                Admission.admitted_at <= end_dt,
                Admission.is_deleted == False,  # noqa: E712
                Admission.patient_id.in_(
                    select(Admission.patient_id)
                    .where(
                        Admission.facility_id == facility_id,
                        Admission.discharged_at.is_not(None),
                        Admission.discharged_at >= start_dt - timedelta(days=30),
                        Admission.discharged_at < start_dt,
                        Admission.is_deleted == False,  # noqa: E712
                    )
                ),
            )
        )
        readmission_count = int(readmits_q.scalar() or 0)
    readmission_rate = (
        readmission_count / total_admissions * 100 if total_admissions else 0.0
    )

    # ── Revenue per patient ───────────────────────────────────────────────
    rev_q = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.facility_id == facility_id,
            Payment.created_at >= start_dt,
            Payment.created_at <= end_dt,
            Payment.is_deleted == False,  # noqa: E712
        )
    )
    total_revenue_cents = int(rev_q.scalar() or 0)
    total_revenue = total_revenue_cents / 100.0

    distinct_pt_q = await db.execute(
        select(func.count(func.distinct(Encounter.patient_id))).where(
            Encounter.facility_id == facility_id,
            Encounter.encounter_date >= start_dt,
            Encounter.encounter_date <= end_dt,
            Encounter.is_deleted == False,  # noqa: E712
        )
    )
    distinct_patients = int(distinct_pt_q.scalar() or 0)
    revenue_per_patient = (
        total_revenue / distinct_patients if distinct_patients else 0.0
    )

    # ── Claim rejection rate ──────────────────────────────────────────────
    claims_q = await db.execute(
        select(
            func.count(InsuranceClaim.id),
            func.sum(
                case(
                    (InsuranceClaim.status == "rejected", 1),
                    else_=0,
                )
            ),
        ).where(
            InsuranceClaim.facility_id == facility_id,
            InsuranceClaim.created_at >= start_dt,
            InsuranceClaim.created_at <= end_dt,
            InsuranceClaim.is_deleted == False,  # noqa: E712
        )
    )
    total_claims_row = claims_q.one()
    total_claims = int(total_claims_row[0] or 0)
    rejected = int(total_claims_row[1] or 0)
    claim_rejection_rate = (rejected / total_claims * 100) if total_claims else 0.0

    # ── Lab turnaround time (specimen → result) ───────────────────────────
    tat_q = await db.execute(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    LabResult.resulted_at - LabOrder.specimen_collected_at,
                )
            )
        )
        .select_from(LabResult)
        .join(LabOrder, LabOrder.id == LabResult.order_id)
        .where(
            LabOrder.facility_id == facility_id,
            LabResult.resulted_at >= start_dt,
            LabResult.resulted_at <= end_dt,
            LabOrder.specimen_collected_at.is_not(None),
            LabResult.resulted_at.is_not(None),
            LabResult.is_deleted == False,  # noqa: E712
        )
    )
    tat_seconds = float(tat_q.scalar() or 0)
    lab_turnaround_time = tat_seconds / 3600.0

    # ── ER response time (arrival → triage) ───────────────────────────────
    er_q = await db.execute(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    EmergencyVisit.triage_time - EmergencyVisit.arrival_time,
                )
            )
        ).where(
            EmergencyVisit.facility_id == facility_id,
            EmergencyVisit.arrival_time >= start_dt,
            EmergencyVisit.arrival_time <= end_dt,
            EmergencyVisit.triage_time.is_not(None),
            EmergencyVisit.is_deleted == False,  # noqa: E712
        )
    )
    er_seconds = float(er_q.scalar() or 0)
    emergency_response_time = er_seconds / 60.0

    # ── Staff attendance rate ─────────────────────────────────────────────
    att_q = await db.execute(
        select(
            func.count(Attendance.id),
            func.sum(
                case(
                    (Attendance.status == "present", 1),
                    (Attendance.status == "late", 1),
                    (Attendance.status == "half_day", 1),
                    else_=0,
                )
            ),
        ).where(
            Attendance.facility_id == facility_id,
            Attendance.attendance_date >= start,
            Attendance.attendance_date <= end,
            Attendance.is_deleted == False,  # noqa: E712
        )
    )
    att_row = att_q.one()
    total_attendance = int(att_row[0] or 0)
    present_count = int(att_row[1] or 0)
    staff_attendance_rate = (
        present_count / total_attendance * 100 if total_attendance else 0.0
    )

    # ── Patient satisfaction (placeholder) ────────────────────────────────
    # Wire to feedback table when it exists.
    patient_satisfaction = 0.0

    return FacilityKpis(
        period_start=start,
        period_end=end,
        patient_volume=round(patient_volume, 2),
        bed_occupancy_rate=round(bed_occupancy_rate, 2),
        average_length_of_stay=round(average_length_of_stay, 2),
        readmission_rate=round(readmission_rate, 2),
        revenue_per_patient=round(revenue_per_patient, 2),
        claim_rejection_rate=round(claim_rejection_rate, 2),
        lab_turnaround_time=round(lab_turnaround_time, 2),
        emergency_response_time=round(emergency_response_time, 2),
        staff_attendance_rate=round(staff_attendance_rate, 2),
        patient_satisfaction=patient_satisfaction,
        total_encounters=total_encounters,
        total_admissions=total_admissions,
        total_revenue=round(total_revenue, 2),
    )


async def get_metric_trend(
    db: AsyncSession,
    facility_id: uuid.UUID,
    metric: str,
    start: date,
    end: date,
    bucket: str = "day",
) -> list[KpiTrendPoint]:
    """
    Time-series for a single KPI.

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param metric: One of: patient_volume, revenue, bed_occupancy_rate, claim_rejection_rate
    @param start: Inclusive start date
    @param end: Inclusive end date
    @param bucket: "day" or "month"
    @returns Ordered list of trend points
    """
    from app.models.billing import Payment
    from app.models.encounter import Encounter
    from app.models.insurance import InsuranceClaim

    start_dt = _start_of_day(start)
    end_dt = _end_of_day(end)

    fmt = "%Y-%m-%d" if bucket == "day" else "%Y-%m"

    if metric == "patient_volume":
        q = await db.execute(
            select(
                func.to_char(Encounter.encounter_date, fmt).label("b"),
                func.count(Encounter.id),
            )
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_date >= start_dt,
                Encounter.encounter_date <= end_dt,
                Encounter.is_deleted == False,  # noqa: E712
            )
            .group_by("b")
            .order_by("b")
        )
        return [KpiTrendPoint(bucket=row[0], value=float(row[1])) for row in q.all()]

    if metric == "revenue":
        q = await db.execute(
            select(
                func.to_char(Payment.created_at, fmt).label("b"),
                func.coalesce(func.sum(Payment.amount_cents), 0),
            )
            .where(
                Payment.facility_id == facility_id,
                Payment.created_at >= start_dt,
                Payment.created_at <= end_dt,
                Payment.is_deleted == False,  # noqa: E712
            )
            .group_by("b")
            .order_by("b")
        )
        return [
            KpiTrendPoint(bucket=row[0], value=float(int(row[1] or 0) / 100.0))
            for row in q.all()
        ]

    if metric == "claim_rejection_rate":
        q = await db.execute(
            select(
                func.to_char(InsuranceClaim.created_at, fmt).label("b"),
                func.count(InsuranceClaim.id),
                func.sum(
                    case(
                        (InsuranceClaim.status == "rejected", 1),
                        else_=0,
                    )
                ),
            )
            .where(
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.created_at >= start_dt,
                InsuranceClaim.created_at <= end_dt,
                InsuranceClaim.is_deleted == False,  # noqa: E712
            )
            .group_by("b")
            .order_by("b")
        )
        out: list[KpiTrendPoint] = []
        for bucket_lbl, total, rejected in q.all():
            total_i = int(total or 0)
            rej_i = int(rejected or 0)
            rate = (rej_i / total_i * 100) if total_i else 0.0
            out.append(KpiTrendPoint(bucket=bucket_lbl, value=round(rate, 2)))
        return out

    if metric == "bed_occupancy_rate":
        # Bed occupancy is a snapshot — produce a flat series equal to current rate
        from app.models.ipd import Bed

        bt = await db.execute(
            select(func.count(Bed.id)).where(
                Bed.facility_id == facility_id,
                Bed.is_deleted == False,  # noqa: E712
            )
        )
        bo = await db.execute(
            select(func.count(Bed.id)).where(
                Bed.facility_id == facility_id,
                Bed.status == "occupied",
                Bed.is_deleted == False,  # noqa: E712
            )
        )
        total = int(bt.scalar() or 0)
        occ = int(bo.scalar() or 0)
        rate = (occ / total * 100) if total else 0.0
        return [KpiTrendPoint(bucket=start.isoformat(), value=round(rate, 2))]

    return []


async def compare_periods(
    db: AsyncSession,
    facility_id: uuid.UUID,
    end: date,
    compare_to: str,
) -> dict:
    """
    Compare current KPIs against a prior period (last_month or last_year).

    @param db: Async database session
    @param facility_id: Tenant facility UUID
    @param end: Anchor end date
    @param compare_to: "last_month" or "last_year"
    @returns dict with current and prior FacilityKpis-as-dicts plus % delta
    """
    if compare_to == "last_year":
        prior_end = end.replace(year=end.year - 1)
        prior_start = prior_end - timedelta(days=29)
        cur_start = end - timedelta(days=29)
    else:
        prior_end = end - timedelta(days=30)
        prior_start = prior_end - timedelta(days=29)
        cur_start = end - timedelta(days=29)

    cur = await get_facility_kpis(db, facility_id, cur_start, end)
    prior = await get_facility_kpis(db, facility_id, prior_start, prior_end)

    deltas: dict[str, float] = {}
    for field in (
        "patient_volume",
        "bed_occupancy_rate",
        "average_length_of_stay",
        "readmission_rate",
        "revenue_per_patient",
        "claim_rejection_rate",
        "lab_turnaround_time",
        "emergency_response_time",
        "staff_attendance_rate",
        "total_revenue",
    ):
        cur_v = float(getattr(cur, field))
        prior_v = float(getattr(prior, field))
        if prior_v == 0:
            deltas[field] = 0.0 if cur_v == 0 else 100.0
        else:
            deltas[field] = round((cur_v - prior_v) / prior_v * 100, 2)

    return {
        "current": cur.__dict__,
        "prior": prior.__dict__,
        "delta_pct": deltas,
        "compare_to": compare_to,
    }
