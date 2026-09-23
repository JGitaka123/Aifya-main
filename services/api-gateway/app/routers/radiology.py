import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.radiology import (
    CriticalImagingNotifyRequest,
    ImagingOrderCreate,
    ImagingOrderDetail,
    ImagingOrderResponse,
    ImagingPerformRequest,
    ImagingResultCreate,
    ImagingResultResponse,
    ImagingResultVerify,
    ImagingScheduleRequest,
    ImagingWorklistResponse,
    RadiologySummary,
)
from app.services.radiology_service import RadiologyService

router = APIRouter(dependencies=[Depends(require_module("radiology"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=RadiologySummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RadiologySummary:
    """
    Get radiology department dashboard summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Radiology summary with order/report counts
    """
    service = RadiologyService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Worklist ─────────────────────────────────────────────────────────────────


@router.get("/worklist", response_model=ImagingWorklistResponse)
async def get_worklist(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by order status"
    ),
    modality: str | None = Query(
        None, description="Filter by imaging modality"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ImagingWorklistResponse:
    """
    Get the radiology worklist — imaging orders with patient info.
    Ordered by priority (stat > urgent > routine) then creation time.

    @param status_filter: Optional status filter
    @param modality: Optional modality filter (xray|ultrasound|ct|mri|...)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Imaging worklist with items and total count
    """
    service = RadiologyService(db)
    items = await service.get_worklist(
        facility_id=current_user.facility_id,
        status=status_filter,
        modality=modality,
    )
    return ImagingWorklistResponse(items=items, total=len(items))


# ── Create Order ─────────────────────────────────────────────────────────────


@router.post("/orders", response_model=ImagingOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: ImagingOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "admin", "facility_admin")
    ),
) -> ImagingOrderResponse:
    """
    Create a new imaging order.

    @param data: Imaging order data
    @param db: Database session
    @param current_user: Authenticated doctor or nurse
    @returns Created imaging order
    """
    service = RadiologyService(db)
    order = await service.create_order(
        data=data,
        facility_id=current_user.facility_id,
        ordered_by=current_user.user_id,
    )
    return ImagingOrderResponse.model_validate(order)


# ── Order Detail ─────────────────────────────────────────────────────────────


@router.get("/orders/{order_id}", response_model=ImagingOrderDetail)
async def get_order_detail(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ImagingOrderDetail:
    """
    Get an imaging order with result and patient info.

    @param order_id: ImagingOrder UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Full imaging order detail with report
    """
    service = RadiologyService(db)
    detail = await service.get_order_detail(
        order_id=order_id,
        facility_id=current_user.facility_id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging order not found",
        )
    return detail


# ── Schedule ─────────────────────────────────────────────────────────────────


@router.post("/orders/{order_id}/schedule", response_model=ImagingOrderResponse)
async def schedule_order(
    order_id: uuid.UUID,
    data: ImagingScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("radiologist", "rad_tech", "nurse", "admin", "facility_admin")
    ),
) -> ImagingOrderResponse:
    """
    Schedule an imaging study for a date/time and room.

    @param order_id: ImagingOrder UUID
    @param data: Scheduling data (datetime, room)
    @param db: Database session
    @param current_user: Authenticated radiology staff
    @returns Updated imaging order
    """
    service = RadiologyService(db)
    order = await service.schedule_order(
        order_id=order_id,
        data=data,
        facility_id=current_user.facility_id,
        staff_id=current_user.user_id,
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging order not found",
        )
    return ImagingOrderResponse.model_validate(order)


# ── Perform Study ────────────────────────────────────────────────────────────


@router.post("/orders/{order_id}/perform", response_model=ImagingOrderResponse)
async def perform_study(
    order_id: uuid.UUID,
    data: ImagingPerformRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("radiologist", "rad_tech", "admin", "facility_admin")
    ),
) -> ImagingOrderResponse:
    """
    Mark an imaging study as performed. Creates a blank result for reporting.

    @param order_id: ImagingOrder UUID
    @param data: Accession number and notes
    @param db: Database session
    @param current_user: Authenticated radiology technologist
    @returns Updated imaging order
    """
    service = RadiologyService(db)
    try:
        order = await service.perform_study(
            order_id=order_id,
            data=data,
            facility_id=current_user.facility_id,
            staff_id=current_user.user_id,
        )
    except ValueError as exc:
        # The study is not paid at the cashier yet.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging order not found",
        )
    return ImagingOrderResponse.model_validate(order)


# ── Enter Report ─────────────────────────────────────────────────────────────


@router.post("/results/{result_id}/report", response_model=ImagingResultResponse)
async def enter_report(
    result_id: uuid.UUID,
    data: ImagingResultCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("radiologist", "admin", "facility_admin")
    ),
) -> ImagingResultResponse:
    """
    Enter or update a radiology report (findings, impression, recommendations).
    Sets status to preliminary.

    @param result_id: ImagingResult UUID
    @param data: Report data
    @param db: Database session
    @param current_user: Authenticated radiologist
    @returns Updated imaging result
    """
    service = RadiologyService(db)
    result = await service.enter_report(
        result_id=result_id,
        data=data,
        facility_id=current_user.facility_id,
        reported_by=current_user.user_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging result not found",
        )
    return ImagingResultResponse.model_validate(result)


# ── Verify Report ────────────────────────────────────────────────────────────


@router.post("/results/{result_id}/verify", response_model=ImagingResultResponse)
async def verify_report(
    result_id: uuid.UUID,
    data: ImagingResultVerify,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("radiologist", "admin", "facility_admin")
    ),
) -> ImagingResultResponse:
    """
    Verify (finalise) a radiology report. Marks order as completed.

    @param result_id: ImagingResult UUID
    @param data: Optional verification notes
    @param db: Database session
    @param current_user: Authenticated senior radiologist
    @returns Verified imaging result
    """
    service = RadiologyService(db)
    result = await service.verify_report(
        result_id=result_id,
        data=data,
        facility_id=current_user.facility_id,
        verified_by=current_user.user_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging result not found",
        )
    return ImagingResultResponse.model_validate(result)


# ── Critical Finding Notification ────────────────────────────────────────────


@router.post("/results/{result_id}/notify-critical", response_model=ImagingResultResponse)
async def notify_critical(
    result_id: uuid.UUID,
    data: CriticalImagingNotifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("radiologist", "rad_tech", "admin", "facility_admin")
    ),
) -> ImagingResultResponse:
    """
    Record that a critical imaging finding was communicated to a clinician.
    Critical findings MUST trigger immediate alert (CLAUDE.md: Clinical Safety).

    @param result_id: ImagingResult UUID
    @param data: Clinician who was notified
    @param db: Database session
    @param current_user: Authenticated radiology staff
    @returns Updated imaging result with notification recorded
    """
    service = RadiologyService(db)
    result = await service.record_critical_notification(
        result_id=result_id,
        notified_to=data.notified_to,
        facility_id=current_user.facility_id,
        notified_by=current_user.user_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imaging result not found",
        )
    return ImagingResultResponse.model_validate(result)
