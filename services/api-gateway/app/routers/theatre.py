import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.theatre import (
    OperativeNotesRequest,
    SurgicalCaseCreate,
    SurgicalCaseListResponse,
    SurgicalCaseResponse,
    TheatreCreate,
    TheatreResponse,
    TheatreSummary,
)
from app.services.theatre_service import TheatreService

router = APIRouter(dependencies=[Depends(require_module("theatre"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=TheatreSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TheatreSummary:
    """
    Get theatre department summary.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Theatre summary
    """
    service = TheatreService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Theatres ─────────────────────────────────────────────────────────────────


@router.get("/theatres", response_model=list[TheatreResponse])
async def list_theatres(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TheatreResponse]:
    """
    Get all active operating theatres.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of theatres
    """
    service = TheatreService(db)
    theatres = await service.get_theatres(facility_id=current_user.facility_id)
    return [TheatreResponse.model_validate(t) for t in theatres]


@router.post("/theatres", response_model=TheatreResponse, status_code=status.HTTP_201_CREATED)
async def create_theatre(
    data: TheatreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> TheatreResponse:
    """
    Create an operating theatre.

    @param data: Theatre data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created theatre
    """
    service = TheatreService(db)
    theatre = await service.create_theatre(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return TheatreResponse.model_validate(theatre)


# ── Surgical Cases ───────────────────────────────────────────────────────────


@router.get("/cases", response_model=SurgicalCaseListResponse)
async def list_cases(
    target_date: date | None = Query(None, alias="date", description="Filter by date"),
    case_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SurgicalCaseListResponse:
    """
    Get surgical case list.

    @param target_date: Optional date filter
    @param case_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Case list
    """
    service = TheatreService(db)
    items = await service.get_case_list(
        facility_id=current_user.facility_id,
        target_date=target_date,
        status=case_status,
    )
    return SurgicalCaseListResponse(items=items, total=len(items))


@router.post("/cases", response_model=SurgicalCaseResponse, status_code=status.HTTP_201_CREATED)
async def schedule_case(
    data: SurgicalCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> SurgicalCaseResponse:
    """
    Schedule a surgical case.

    @param data: Case data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Created case
    """
    service = TheatreService(db)
    case = await service.schedule_case(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return SurgicalCaseResponse.model_validate(case)


@router.get("/cases/{case_id}", response_model=SurgicalCaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SurgicalCaseResponse:
    """
    Get a surgical case detail.

    @param case_id: Case UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Case details
    """
    service = TheatreService(db)
    case = await service.get_case(case_id, current_user.facility_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgical case not found")
    return SurgicalCaseResponse.model_validate(case)


@router.patch("/cases/{case_id}/status", response_model=SurgicalCaseResponse)
async def update_case_status(
    case_id: uuid.UUID,
    new_status: str = Query(..., alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "nurse")
    ),
) -> SurgicalCaseResponse:
    """
    Update surgical case status.

    @param case_id: Case UUID
    @param new_status: New status value
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Updated case
    """
    service = TheatreService(db)
    case = await service.update_status(
        case_id=case_id,
        new_status=new_status,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgical case not found")
    return SurgicalCaseResponse.model_validate(case)


@router.post("/cases/{case_id}/operative-notes", response_model=SurgicalCaseResponse)
async def record_operative_notes(
    case_id: uuid.UUID,
    data: OperativeNotesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> SurgicalCaseResponse:
    """
    Record operative notes for a surgical case.

    @param case_id: Case UUID
    @param data: Operative notes
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Updated case
    """
    service = TheatreService(db)
    case = await service.record_operative_notes(
        case_id=case_id,
        data=data,
        facility_id=current_user.facility_id,
        recorded_by=current_user.user_id,
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surgical case not found")
    return SurgicalCaseResponse.model_validate(case)
