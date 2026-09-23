import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Report Template ─────────────────────────────────────────────────────────


class ReportTemplateCreate(BaseModel):
    """Schema for creating a report template."""

    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=50)
    description: str | None = Field(None, max_length=2000)
    category: str = Field(
        default="operational",
        pattern=r"^(operational|clinical|financial|compliance|moh)$",
    )
    department: str | None = Field(
        None,
        pattern=r"^(opd|ipd|lab|pharmacy|radiology|mch|billing|appointments|all)$",
    )
    report_type: str = Field(
        default="tabular", pattern=r"^(tabular|chart|summary|register)$"
    )
    parameters_schema: dict | None = None
    query_config: dict | None = None
    columns_config: dict | None = None
    is_scheduled: bool = False
    schedule_cron: str | None = Field(None, max_length=50)
    moh_form_number: str | None = Field(None, max_length=20)
    reporting_period: str | None = Field(
        None, pattern=r"^(daily|weekly|monthly|quarterly|annual)$"
    )


class ReportTemplateResponse(BaseModel):
    """Schema for report template API responses."""

    id: uuid.UUID
    name: str
    code: str
    description: str | None
    category: str
    department: str | None
    report_type: str
    parameters_schema: dict | None
    columns_config: dict | None
    is_scheduled: bool
    schedule_cron: str | None
    is_active: bool
    moh_form_number: str | None
    reporting_period: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportTemplateListItem(BaseModel):
    """Report template in list view."""

    id: uuid.UUID
    name: str
    code: str
    category: str
    department: str | None
    report_type: str
    moh_form_number: str | None
    reporting_period: str | None
    is_scheduled: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ── Generated Report ────────────────────────────────────────────────────────


class ReportGenerateRequest(BaseModel):
    """Schema for generating a report."""

    template_id: uuid.UUID
    date_from: date
    date_to: date
    parameters: dict | None = None
    format: str = Field(
        default="json", pattern=r"^(json|pdf|csv|xlsx)$"
    )


class GeneratedReportResponse(BaseModel):
    """Schema for generated report API responses."""

    id: uuid.UUID
    template_id: uuid.UUID
    title: str
    report_number: str
    parameters: dict | None
    date_from: date
    date_to: date
    result_data: dict | None
    summary_data: dict | None
    row_count: int
    status: str
    format: str
    file_key: str | None
    generated_by: uuid.UUID
    generated_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class GeneratedReportListItem(BaseModel):
    """Generated report in list view."""

    id: uuid.UUID
    template_id: uuid.UUID
    title: str
    report_number: str
    date_from: date
    date_to: date
    row_count: int
    status: str
    format: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class GeneratedReportListResponse(BaseModel):
    """Paginated generated report list."""

    items: list[GeneratedReportListItem]
    total: int


# ── Dashboard Analytics ─────────────────────────────────────────────────────


class FacilityDashboard(BaseModel):
    """Facility-wide dashboard analytics."""

    # Patient stats
    total_patients: int = 0
    patients_today: int = 0
    patients_this_month: int = 0

    # OPD stats
    opd_visits_today: int = 0
    opd_visits_month: int = 0

    # IPD stats
    active_admissions: int = 0
    admissions_today: int = 0
    discharges_today: int = 0
    bed_occupancy_rate: float = 0.0

    # Appointments
    appointments_today: int = 0
    appointments_completed: int = 0
    appointments_no_show: int = 0

    # Lab
    lab_orders_today: int = 0
    lab_pending: int = 0
    lab_critical: int = 0

    # Pharmacy
    prescriptions_today: int = 0
    dispensed_today: int = 0
    stock_alerts: int = 0

    # Billing (KES cents)
    revenue_today: int = 0
    revenue_month: int = 0
    outstanding_balance: int = 0

    # Radiology
    imaging_orders_today: int = 0
    imaging_pending_reports: int = 0

    # MCH
    active_anc_profiles: int = 0
    deliveries_month: int = 0
    immunizations_month: int = 0


class DepartmentStat(BaseModel):
    """Single department statistic for trending."""

    date: date
    count: int
    label: str | None = None


class TrendData(BaseModel):
    """Trend data for chart rendering."""

    label: str
    data: list[DepartmentStat]


class DashboardTrends(BaseModel):
    """Time-series trends for dashboard charts."""

    opd_visits: list[DepartmentStat] = []
    admissions: list[DepartmentStat] = []
    revenue: list[DepartmentStat] = []
    lab_orders: list[DepartmentStat] = []
    appointments: list[DepartmentStat] = []


class TopDiagnosis(BaseModel):
    """Top diagnosis for analytics."""

    icd_code: str
    description: str
    count: int


class ReportsSummary(BaseModel):
    """Reports module summary."""

    total_templates: int = 0
    moh_templates: int = 0
    generated_today: int = 0
    generated_month: int = 0
