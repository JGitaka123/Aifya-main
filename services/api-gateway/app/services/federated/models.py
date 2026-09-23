"""
Federated analytics models.
Data structures for anonymized aggregation, disease surveillance,
and outbreak detection across facilities.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SurveillanceAlertLevel(StrEnum):
    """Disease surveillance alert levels."""
    NORMAL = "normal"
    WATCH = "watch"
    ALERT = "alert"
    OUTBREAK = "outbreak"


class AggregationPeriod(StrEnum):
    """Time period for data aggregation."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DiseaseSurveillanceEntry(BaseModel):
    """
    Single disease surveillance data point.

    @param condition: Disease/condition name
    @param icd10_code: ICD-10 code
    @param case_count: Number of cases in period
    @param previous_period_count: Cases in previous period (for trend)
    @param percent_change: Percentage change from previous period
    @param alert_level: Surveillance alert level
    @param county: County name (if county-level data)
    """
    condition: str
    icd10_code: str | None = None
    case_count: int
    previous_period_count: int = 0
    percent_change: float = 0.0
    alert_level: SurveillanceAlertLevel = SurveillanceAlertLevel.NORMAL
    county: str | None = None


class OutbreakAlert(BaseModel):
    """
    Outbreak detection alert.

    @param condition: Disease/condition
    @param icd10_code: ICD-10 code
    @param alert_level: Alert severity
    @param current_cases: Cases in current period
    @param expected_cases: Expected baseline cases
    @param excess_ratio: current/expected ratio
    @param affected_facilities: Number of facilities reporting
    @param recommendation: Public health recommendation
    """
    condition: str
    icd10_code: str | None = None
    alert_level: SurveillanceAlertLevel
    current_cases: int
    expected_cases: int
    excess_ratio: float
    affected_facilities: int = 1
    recommendation: str


class AnonymizedFacilityReport(BaseModel):
    """
    Anonymized facility-level data for county aggregation.
    Contains NO patient-identifiable information.

    @param facility_id: Facility UUID (known to the county)
    @param period_start: Aggregation period start (ISO date)
    @param period_end: Aggregation period end (ISO date)
    @param total_opd_visits: Total OPD visits
    @param total_ipd_admissions: Total inpatient admissions
    @param total_deliveries: Total deliveries
    @param diagnosis_counts: Aggregated diagnosis counts by ICD-10
    @param mortality_count: Total deaths
    @param lab_tests_count: Total lab tests performed
    @param immunizations_count: Total immunizations given
    """
    facility_id: str
    period_start: str
    period_end: str
    total_opd_visits: int = 0
    total_ipd_admissions: int = 0
    total_deliveries: int = 0
    diagnosis_counts: dict[str, int] = {}
    mortality_count: int = 0
    lab_tests_count: int = 0
    immunizations_count: int = 0


class CountyDashboard(BaseModel):
    """
    County-level aggregated dashboard data.

    @param county: County name
    @param period: Aggregation period
    @param facilities_reporting: Number of facilities
    @param total_opd_visits: Total OPD visits across facilities
    @param total_admissions: Total admissions
    @param total_deliveries: Total deliveries
    @param top_conditions: Top conditions by case count
    @param surveillance_alerts: Active surveillance alerts
    @param outbreak_alerts: Active outbreak alerts
    """
    county: str
    period: str
    facilities_reporting: int
    total_opd_visits: int = 0
    total_admissions: int = 0
    total_deliveries: int = 0
    top_conditions: list[DiseaseSurveillanceEntry] = []
    surveillance_alerts: list[DiseaseSurveillanceEntry] = []
    outbreak_alerts: list[OutbreakAlert] = []
