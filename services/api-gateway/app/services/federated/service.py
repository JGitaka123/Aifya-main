"""
Federated Analytics service.
Generates anonymized facility reports, detects disease outbreaks,
and provides county-level aggregated surveillance data.

All data is anonymized — NO patient-identifiable information leaves the facility.
Complies with Kenya Data Protection Act (DPA) and ODPC requirements.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.ipd import Admission
from app.models.lab import LabOrder
from app.models.mch import DeliveryRecord, Immunization
from app.services.federated.models import (
    AnonymizedFacilityReport,
    DiseaseSurveillanceEntry,
    OutbreakAlert,
    SurveillanceAlertLevel,
)

logger = get_logger(__name__)

# Outbreak detection thresholds
OUTBREAK_RATIO_ALERT = 1.5  # 50% above baseline → alert
OUTBREAK_RATIO_OUTBREAK = 2.0  # 100% above baseline → outbreak
WATCH_RATIO = 1.2  # 20% above baseline → watch

# Notifiable diseases per Kenya Public Health Act
NOTIFIABLE_DISEASES = {
    "A00": "Cholera",
    "A01": "Typhoid",
    "A09": "Diarrhoea",
    "A15": "Tuberculosis",
    "A90": "Dengue",
    "B50": "Malaria",
    "B20": "HIV",
    "J09": "Influenza",
    "J10": "Influenza",
    "A23": "Brucellosis",
    "A82": "Rabies",
    "A20": "Plague",
    "P35": "Measles",
    "B05": "Measles",
    "A33": "Neonatal Tetanus",
}


class FederatedAnalyticsService:
    """
    Federated analytics service.
    Generates anonymized aggregations and detects disease outbreaks.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the service.

        @param db: Async database session
        """
        self.db = db

    async def generate_facility_report(
        self,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> AnonymizedFacilityReport:
        """
        Generate an anonymized facility report for county-level aggregation.
        Contains aggregate counts only — NO patient identifiers.

        @param facility_id: Facility UUID
        @param date_from: Period start
        @param date_to: Period end
        @returns Anonymized facility report
        """
        # OPD visits
        opd_result = await self.db.execute(
            select(func.count(Encounter.id)).where(
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) >= date_from,
                func.date(Encounter.encounter_date) <= date_to,
            )
        )
        opd_visits = opd_result.scalar() or 0

        # IPD admissions
        ipd_result = await self.db.execute(
            select(func.count(Admission.id)).where(
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
                func.date(Admission.admitted_at) >= date_from,
                func.date(Admission.admitted_at) <= date_to,
            )
        )
        ipd_admissions = ipd_result.scalar() or 0

        # Deliveries
        del_result = await self.db.execute(
            select(func.count(DeliveryRecord.id)).where(
                DeliveryRecord.facility_id == facility_id,
                DeliveryRecord.is_deleted == False,  # noqa: E712
                func.date(DeliveryRecord.delivery_date) >= date_from,
                func.date(DeliveryRecord.delivery_date) <= date_to,
            )
        )
        deliveries = del_result.scalar() or 0

        # Diagnosis counts by ICD-10 (top 50)
        dx_result = await self.db.execute(
            select(
                Diagnosis.icd10_code,
                func.count(Diagnosis.id).label("cnt"),
            )
            .where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                func.date(Diagnosis.created_at) >= date_from,
                func.date(Diagnosis.created_at) <= date_to,
            )
            .group_by(Diagnosis.icd10_code)
            .order_by(func.count(Diagnosis.id).desc())
            .limit(50)
        )
        dx_rows = dx_result.all()
        diagnosis_counts = {(r.icd10_code or "unknown"): r.count for r in dx_rows}

        # Lab tests
        lab_result = await self.db.execute(
            select(func.count(LabOrder.id)).where(
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
                func.date(LabOrder.created_at) >= date_from,
                func.date(LabOrder.created_at) <= date_to,
            )
        )
        lab_tests = lab_result.scalar() or 0

        # Immunizations
        imm_result = await self.db.execute(
            select(func.count(Immunization.id)).where(
                Immunization.facility_id == facility_id,
                Immunization.is_deleted == False,  # noqa: E712
                func.date(Immunization.date_given) >= date_from,
                func.date(Immunization.date_given) <= date_to,
            )
        )
        immunizations = imm_result.scalar() or 0

        return AnonymizedFacilityReport(
            facility_id=str(facility_id),
            period_start=str(date_from),
            period_end=str(date_to),
            total_opd_visits=opd_visits,
            total_ipd_admissions=ipd_admissions,
            total_deliveries=deliveries,
            diagnosis_counts=diagnosis_counts,
            lab_tests_count=lab_tests,
            immunizations_count=immunizations,
        )

    async def detect_outbreaks(
        self,
        facility_id: uuid.UUID,
        current_period_days: int = 7,
    ) -> list[OutbreakAlert]:
        """
        Detect disease outbreaks by comparing current period case counts
        against historical baseline (previous 4 weeks average).

        @param facility_id: Facility UUID
        @param current_period_days: Current surveillance window (default 7 days)
        @returns List of outbreak alerts
        """
        today = date.today()
        current_start = today - timedelta(days=current_period_days)

        # Baseline: average of 4 previous equivalent periods
        baseline_start = today - timedelta(days=current_period_days * 5)
        baseline_end = current_start - timedelta(days=1)

        # Current period counts for notifiable diseases
        alerts: list[OutbreakAlert] = []

        for icd10_prefix, disease_name in NOTIFIABLE_DISEASES.items():
            # Current count
            current_result = await self.db.execute(
                select(func.count(Diagnosis.id)).where(
                    Diagnosis.facility_id == facility_id,
                    Diagnosis.is_deleted == False,  # noqa: E712
                    Diagnosis.icd10_code.startswith(icd10_prefix),
                    func.date(Diagnosis.created_at) >= current_start,
                    func.date(Diagnosis.created_at) <= today,
                )
            )
            current_count = current_result.scalar() or 0

            if current_count == 0:
                continue

            # Baseline average
            baseline_result = await self.db.execute(
                select(func.count(Diagnosis.id)).where(
                    Diagnosis.facility_id == facility_id,
                    Diagnosis.is_deleted == False,  # noqa: E712
                    Diagnosis.icd10_code.startswith(icd10_prefix),
                    func.date(Diagnosis.created_at) >= baseline_start,
                    func.date(Diagnosis.created_at) <= baseline_end,
                )
            )
            baseline_total = baseline_result.scalar() or 0
            # Average per equivalent period (4 periods)
            expected = max(baseline_total / 4, 1)
            ratio = current_count / expected

            if ratio >= WATCH_RATIO:
                if ratio >= OUTBREAK_RATIO_OUTBREAK:
                    level = SurveillanceAlertLevel.OUTBREAK
                    recommendation = (
                        f"OUTBREAK DETECTED: {disease_name} cases {ratio:.1f}x above baseline. "
                        "Initiate outbreak investigation. Notify County CDSC immediately."
                    )
                elif ratio >= OUTBREAK_RATIO_ALERT:
                    level = SurveillanceAlertLevel.ALERT
                    recommendation = (
                        f"ALERT: {disease_name} cases elevated {ratio:.1f}x above baseline. "
                        "Enhanced surveillance recommended. Prepare outbreak response."
                    )
                else:
                    level = SurveillanceAlertLevel.WATCH
                    recommendation = (
                        f"WATCH: {disease_name} cases trending up ({ratio:.1f}x baseline). "
                        "Monitor closely over next reporting period."
                    )

                alerts.append(OutbreakAlert(
                    condition=disease_name,
                    icd10_code=icd10_prefix,
                    alert_level=level,
                    current_cases=current_count,
                    expected_cases=int(expected),
                    excess_ratio=round(ratio, 2),
                    recommendation=recommendation,
                ))

        return sorted(alerts, key=lambda a: a.excess_ratio, reverse=True)

    async def get_disease_surveillance(
        self,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
        limit: int = 20,
    ) -> list[DiseaseSurveillanceEntry]:
        """
        Get disease surveillance data — top conditions with trend comparison.

        @param facility_id: Facility UUID
        @param date_from: Current period start
        @param date_to: Current period end
        @param limit: Max conditions to return
        @returns Surveillance entries with trend data
        """
        period_length = (date_to - date_from).days
        prev_from = date_from - timedelta(days=period_length)
        prev_to = date_from - timedelta(days=1)

        # Current period
        current = await self.db.execute(
            select(
                Diagnosis.icd10_code,
                Diagnosis.icd10_description,
                func.count(Diagnosis.id).label("cnt"),
            )
            .where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                func.date(Diagnosis.created_at) >= date_from,
                func.date(Diagnosis.created_at) <= date_to,
            )
            .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
            .order_by(func.count(Diagnosis.id).desc())
            .limit(limit)
        )
        current_rows = current.all()

        entries: list[DiseaseSurveillanceEntry] = []
        for row in current_rows:
            # Previous period count for this condition
            prev_result = await self.db.execute(
                select(func.count(Diagnosis.id)).where(
                    Diagnosis.facility_id == facility_id,
                    Diagnosis.is_deleted == False,  # noqa: E712
                    Diagnosis.icd10_code == row.icd10_code,
                    func.date(Diagnosis.created_at) >= prev_from,
                    func.date(Diagnosis.created_at) <= prev_to,
                )
            )
            prev_count = prev_result.scalar() or 0

            pct_change = ((row.cnt - prev_count) / max(prev_count, 1)) * 100

            # Determine alert level
            if row.cnt > 0 and prev_count > 0:
                ratio = row.cnt / prev_count
                if ratio >= OUTBREAK_RATIO_OUTBREAK:
                    alert = SurveillanceAlertLevel.OUTBREAK
                elif ratio >= OUTBREAK_RATIO_ALERT:
                    alert = SurveillanceAlertLevel.ALERT
                elif ratio >= WATCH_RATIO:
                    alert = SurveillanceAlertLevel.WATCH
                else:
                    alert = SurveillanceAlertLevel.NORMAL
            else:
                alert = SurveillanceAlertLevel.NORMAL

            entries.append(DiseaseSurveillanceEntry(
                condition=row.description or row.icd10_code or "Unknown",
                icd10_code=row.icd10_code,
                case_count=row.count,
                previous_period_count=prev_count,
                percent_change=round(pct_change, 1),
                alert_level=alert,
            ))

        return entries
