"""
Federated Analytics router.
County-level anonymized aggregation, disease surveillance, and outbreak detection.
All data is anonymized — NO patient-identifiable information exposed.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.services.federated.models import (
    AnonymizedFacilityReport,
    DiseaseSurveillanceEntry,
    OutbreakAlert,
)
from app.services.federated.service import FederatedAnalyticsService

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("analytics"))])


@router.get("/facility-report", response_model=AnonymizedFacilityReport)
async def get_facility_report(
    date_from: date = Query(..., description="Period start (YYYY-MM-DD)"),
    date_to: date = Query(..., description="Period end (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AnonymizedFacilityReport:
    """
    Generate anonymized facility report for county aggregation.
    Contains aggregate counts only — NO patient-identifiable information.

    @param date_from: Report period start
    @param date_to: Report period end
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Anonymized facility report
    """
    service = FederatedAnalyticsService(db)
    report = await service.generate_facility_report(
        facility_id=current_user.facility_id,
        date_from=date_from,
        date_to=date_to,
    )

    logger.info(
        "federated_facility_report",
        facility_id=str(current_user.facility_id),
        period=f"{date_from}/{date_to}",
    )
    return report


@router.get("/surveillance", response_model=list[DiseaseSurveillanceEntry])
async def get_disease_surveillance(
    date_from: date = Query(default=None, description="Period start"),
    date_to: date = Query(default=None, description="Period end"),
    limit: int = Query(default=20, le=50, description="Max conditions"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DiseaseSurveillanceEntry]:
    """
    Get disease surveillance data with trend comparison.
    Shows top conditions, case counts, and alert levels.

    @param date_from: Period start (defaults to last 30 days)
    @param date_to: Period end (defaults to today)
    @param limit: Max conditions to return
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Surveillance entries with trend data
    """
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)

    service = FederatedAnalyticsService(db)
    return await service.get_disease_surveillance(
        facility_id=current_user.facility_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/outbreaks", response_model=list[OutbreakAlert])
async def get_outbreak_alerts(
    window_days: int = Query(default=7, le=30, description="Surveillance window in days"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[OutbreakAlert]:
    """
    Detect potential disease outbreaks by comparing current case counts
    against historical baseline. Uses WHO-recommended threshold analysis.

    @param window_days: Current surveillance window
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of outbreak alerts sorted by severity
    """
    service = FederatedAnalyticsService(db)
    alerts = await service.detect_outbreaks(
        facility_id=current_user.facility_id,
        current_period_days=window_days,
    )

    if alerts:
        logger.warning(
            "outbreak_alerts_detected",
            count=len(alerts),
            conditions=[a.condition for a in alerts],
            facility_id=str(current_user.facility_id),
        )

    return alerts
