import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.report import (
    DashboardTrends,
    FacilityDashboard,
    GeneratedReportListResponse,
    GeneratedReportResponse,
    ReportGenerateRequest,
    ReportsSummary,
    ReportTemplateCreate,
    ReportTemplateListItem,
    ReportTemplateResponse,
    TopDiagnosis,
)
from app.services.reports_service import ReportsService

router = APIRouter(dependencies=[Depends(require_module("reports"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=ReportsSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportsSummary:
    """
    Get reports module summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Reports summary
    """
    service = ReportsService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Facility Dashboard ──────────────────────────────────────────────────────


@router.get("/dashboard", response_model=FacilityDashboard)
async def get_facility_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FacilityDashboard:
    """
    Get facility-wide dashboard analytics.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Facility dashboard stats
    """
    service = ReportsService(db)
    return await service.get_facility_dashboard(facility_id=current_user.facility_id)


@router.get("/dashboard/trends", response_model=DashboardTrends)
async def get_dashboard_trends(
    days: int = Query(14, ge=1, le=90, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DashboardTrends:
    """
    Get time-series trend data for dashboard charts.

    @param days: Lookback period in days
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Trend data
    """
    service = ReportsService(db)
    return await service.get_dashboard_trends(
        facility_id=current_user.facility_id, days=days
    )


@router.get("/dashboard/top-diagnoses", response_model=list[TopDiagnosis])
async def get_top_diagnoses(
    date_from: date | None = Query(None, description="Start date"),
    date_to: date | None = Query(None, description="End date"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TopDiagnosis]:
    """
    Get top diagnoses by frequency for analytics charts.

    @param date_from: Optional start date
    @param date_to: Optional end date
    @param limit: Max results
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of top diagnoses
    """
    service = ReportsService(db)
    return await service.get_top_diagnoses(
        facility_id=current_user.facility_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


# ── Report Templates ────────────────────────────────────────────────────────


@router.get("/templates", response_model=list[ReportTemplateListItem])
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    department: str | None = Query(None, description="Filter by department"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ReportTemplateListItem]:
    """
    Get report templates with optional filters.

    @param category: Optional category filter
    @param department: Optional department filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of templates
    """
    service = ReportsService(db)
    return await service.get_templates(
        facility_id=current_user.facility_id,
        category=category,
        department=department,
    )


@router.post(
    "/templates",
    response_model=ReportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: ReportTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> ReportTemplateResponse:
    """
    Create a report template.

    @param data: Template data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created template
    """
    service = ReportsService(db)
    template = await service.create_template(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return ReportTemplateResponse.model_validate(template)


@router.get("/templates/{template_id}", response_model=ReportTemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportTemplateResponse:
    """
    Get a single report template by ID.

    @param template_id: Template UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Template detail
    """
    service = ReportsService(db)
    template = await service.get_template(
        template_id=template_id,
        facility_id=current_user.facility_id,
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report template not found",
        )
    return ReportTemplateResponse.model_validate(template)


# ── Report Generation ───────────────────────────────────────────────────────


@router.post(
    "/generate",
    response_model=GeneratedReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> GeneratedReportResponse:
    """
    Generate a report from a template.

    @param data: Generation request
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Generated report
    """
    service = ReportsService(db)
    try:
        report = await service.generate_report(
            data=data,
            facility_id=current_user.facility_id,
            generated_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return GeneratedReportResponse.model_validate(report)


@router.get("/generated", response_model=GeneratedReportListResponse)
async def list_generated_reports(
    template_id: uuid.UUID | None = Query(None, description="Filter by template"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> GeneratedReportListResponse:
    """
    Get list of generated reports.

    @param template_id: Optional template filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Generated report list
    """
    service = ReportsService(db)
    items = await service.get_generated_reports(
        facility_id=current_user.facility_id,
        template_id=template_id,
    )
    return GeneratedReportListResponse(items=items, total=len(items))


@router.get("/generated/{report_id}", response_model=GeneratedReportResponse)
async def get_generated_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> GeneratedReportResponse:
    """
    Get a single generated report with full data.

    @param report_id: Report UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Generated report with data
    """
    service = ReportsService(db)
    report = await service.get_generated_report(
        report_id=report_id,
        facility_id=current_user.facility_id,
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated report not found",
        )
    return GeneratedReportResponse.model_validate(report)
