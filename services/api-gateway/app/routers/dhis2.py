"""
DHIS2 / MOH Reporting router.
Provides endpoints for generating MOH forms and managing DHIS2 integration.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.services.dhis2.sync import DHIS2SyncService

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("dhis2_sync"))])


class MOHReportRequest(BaseModel):
    """
    Request to generate a specific MOH form.

    @param form_code: MOH form code (MOH_705A, MOH_705B, MOH_710, MOH_711, MOH_713, MOH_718)
    @param date_from: Report period start date
    @param date_to: Report period end date
    """
    form_code: str
    date_from: date
    date_to: date


class DHIS2SyncRequest(BaseModel):
    """
    Request to generate and submit a MOH form to DHIS2.

    @param form_code: MOH form code
    @param date_from: Report period start date
    @param date_to: Report period end date
    @param dhis2_dataset_id: Optional DHIS2 dataset UID override
    """
    form_code: str
    date_from: date
    date_to: date
    dhis2_dataset_id: str | None = None


class DHIS2ConnectionTest(BaseModel):
    """
    DHIS2 connection test result.

    @param connected: Whether connection succeeded
    @param message: Status message
    """
    connected: bool
    message: str


# ── Generate MOH Report ─────────────────────────────────────────────────────


@router.post("/moh/generate")
async def generate_moh_report(
    request: MOHReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Generate a specific MOH form (local only, no DHIS2 submission).

    @param request: MOH report request with form code and date range
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Generated MOH report data
    """
    service = DHIS2SyncService(db)
    report = await service._generate_report(
        form_code=request.form_code.upper(),
        facility_id=current_user.facility_id,
        date_from=request.date_from,
        date_to=request.date_to,
    )

    if not report:
        return {"error": f"Unknown form code: {request.form_code}"}

    logger.info(
        "moh_report_generated",
        form=request.form_code,
        facility_id=str(current_user.facility_id),
    )
    return report


# ── Generate All MOH Reports ────────────────────────────────────────────────


@router.get("/moh/generate-all")
async def generate_all_moh_reports(
    date_from: date = Query(..., description="Report period start (YYYY-MM-DD)"),
    date_to: date = Query(..., description="Report period end (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Generate all MOH forms (705A, 705B, 710, 711, 713, 718) for the facility.

    @param date_from: Report period start
    @param date_to: Report period end
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Dict mapping form codes to generated reports
    """
    service = DHIS2SyncService(db)
    reports = await service.generate_all_reports(
        facility_id=current_user.facility_id,
        date_from=date_from,
        date_to=date_to,
    )

    logger.info(
        "moh_all_reports_generated",
        facility_id=str(current_user.facility_id),
        forms=list(reports.keys()),
    )
    return {"reports": reports, "period": {"from": str(date_from), "to": str(date_to)}}


# ── Available MOH Forms ─────────────────────────────────────────────────────


@router.get("/moh/forms")
async def list_moh_forms(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """
    List available MOH form types with descriptions.

    @param current_user: Authenticated user from JWT
    @returns List of available MOH forms
    """
    return [
        {"code": "MOH_705A", "name": "MOH 705A", "title": "Outpatient Morbidity Summary", "period": "monthly"},
        {"code": "MOH_705B", "name": "MOH 705B", "title": "Inpatient Morbidity Summary", "period": "monthly"},
        {"code": "MOH_710", "name": "MOH 710", "title": "Immunization Report", "period": "monthly"},
        {"code": "MOH_711", "name": "MOH 711", "title": "Integrated RH/HIV/TB/Malaria Summary", "period": "monthly"},
        {"code": "MOH_713", "name": "MOH 713", "title": "Laboratory Summary", "period": "monthly"},
        {"code": "MOH_718", "name": "MOH 718", "title": "Maternity Register Summary", "period": "monthly"},
    ]


# ── DHIS2 Connection Test ───────────────────────────────────────────────────


@router.get("/dhis2/status")
async def dhis2_connection_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> DHIS2ConnectionTest:
    """
    Test DHIS2 connectivity for this facility.
    Credentials sourced from environment / Vault.

    @param current_user: Authenticated user from JWT
    @returns Connection test result
    """
    import os

    from app.services.dhis2.client import DHIS2Client, DHIS2Config

    base_url = os.getenv("DHIS2_BASE_URL")
    username = os.getenv("DHIS2_USERNAME")
    password = os.getenv("DHIS2_PASSWORD")

    if not all([base_url, username, password]):
        return DHIS2ConnectionTest(
            connected=False,
            message="DHIS2 credentials not configured. Set DHIS2_BASE_URL, DHIS2_USERNAME, DHIS2_PASSWORD.",
        )

    config = DHIS2Config(
        base_url=base_url,
        username=username,
        password=password,
        org_unit_id="",
    )
    client = DHIS2Client(config)
    connected = await client.check_connection()

    return DHIS2ConnectionTest(
        connected=connected,
        message="Connected to DHIS2" if connected else "Failed to connect to DHIS2",
    )
