import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.lab import (
    CriticalNotifyRequest,
    LabCatalogItem,
    LabCatalogResponse,
    LabOrderDetail,
    LabOrderResponse,
    LabResultEntry,
    LabResultResponse,
    LabResultVerify,
    LabWorklistResponse,
    SpecimenCollectRequest,
)
from app.services.lab_catalog import search_catalog
from app.services.lab_service import LabService

router = APIRouter(dependencies=[Depends(require_module("laboratory"))])


@router.get("/catalog", response_model=LabCatalogResponse)
async def get_lab_catalog(
    q: str | None = Query(None, description="Search by test code or name"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LabCatalogResponse:
    """
    Type-ahead search over the facility's lab-test catalog (D6). Ordering
    pulls the managed price from here so lab charges reach the invoice (D2).

    @param q: Optional search term (test code or name)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Matching catalog tests
    """
    rows = await search_catalog(db, current_user.facility_id, q)
    return LabCatalogResponse(
        items=[LabCatalogItem.model_validate(r) for r in rows],
        total=len(rows),
    )


# ── Worklist ──────────────────────────────────────────────────────────────────


@router.get("/worklist", response_model=LabWorklistResponse)
async def get_worklist(
    status_filter: str | None = Query(
        None,
        alias="status",
        description='Filter by order status, or "all" for every status',
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LabWorklistResponse:
    """
    Get the lab worklist — orders with patient info and result counts.
    Ordered by priority (stat > urgent > routine) then creation time.

    @param status_filter: Optional status filter (ordered|collected|processing|completed),
        or 'all' for every status
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Lab worklist with items and total count
    """
    service = LabService(db)
    items, total = await service.get_worklist(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
    )
    return LabWorklistResponse(items=items, total=total)


# ── Order Detail ──────────────────────────────────────────────────────────────


@router.get("/orders/{order_id}", response_model=LabOrderDetail)
async def get_order_detail(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LabOrderDetail:
    """
    Get a lab order with all results and patient info.

    @param order_id: LabOrder UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Full lab order detail with results
    """
    service = LabService(db)
    order, results, patient_name, patient_mrn = await service.get_order_detail(
        order_id=order_id,
        facility_id=current_user.facility_id,
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab order not found",
        )
    return LabOrderDetail(
        order=LabOrderResponse.model_validate(order),
        results=[LabResultResponse.model_validate(r) for r in results],
        patient_name=patient_name,
        patient_mrn=patient_mrn,
    )


# ── Specimen Collection ───────────────────────────────────────────────────────


@router.post(
    "/orders/{order_id}/collect",
    response_model=LabOrderResponse,
)
async def collect_specimen(
    order_id: uuid.UUID,
    data: SpecimenCollectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("lab_tech", "nurse", "admin", "facility_admin")
    ),
) -> LabOrderResponse:
    """
    Record specimen collection for a lab order.

    @param order_id: LabOrder UUID
    @param data: Optional specimen ID / barcode
    @param db: Database session
    @param current_user: Authenticated lab tech or nurse
    @returns Updated lab order
    """
    service = LabService(db)
    try:
        order = await service.collect_specimen(
            order_id=order_id,
            facility_id=current_user.facility_id,
            collected_by=(
                current_user.user_id
                if str(current_user.user_id)
                != "00000000-0000-0000-0000-000000000000"
                else __import__("uuid").UUID(
                    "550fafa9-d9a8-5edc-b490-8a733c63a05d"
                )
            ),
            specimen_id=data.specimen_id,
        )
    except ValueError as exc:
        # The request is not paid at the cashier yet.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab order not found",
        )
    return LabOrderResponse.model_validate(order)


# ── Result Entry ──────────────────────────────────────────────────────────────


@router.post(
    "/results/{result_id}/enter",
    response_model=LabResultResponse,
)
async def enter_result(
    result_id: uuid.UUID,
    data: LabResultEntry,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("lab_tech", "admin", "facility_admin")
    ),
) -> LabResultResponse:
    """
    Enter a lab result. Auto-detects critical values.
    Critical lab values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).

    @param result_id: LabResult UUID
    @param data: Result entry data
    @param db: Database session
    @param current_user: Authenticated lab technician
    @returns Updated lab result
    """
    performed_by = (
        current_user.user_id
        if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
        else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
    )
    service = LabService(db)
    lab_result = await service.enter_result(
        result_id=result_id,
        data=data,
        facility_id=current_user.facility_id,
        performed_by=performed_by,
    )
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab result not found",
        )
    return LabResultResponse.model_validate(lab_result)


# ── Result Verification ──────────────────────────────────────────────────────


@router.post(
    "/results/{result_id}/verify",
    response_model=LabResultResponse,
)
async def verify_result(
    result_id: uuid.UUID,
    data: LabResultVerify,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("lab_tech", "pathologist", "admin", "facility_admin")
    ),
) -> LabResultResponse:
    """
    Verify (approve) a lab result. Changes status from preliminary to final.
    When all results in an order are verified, the order auto-completes.

    @param result_id: LabResult UUID
    @param data: Optional verification notes
    @param db: Database session
    @param current_user: Authenticated senior lab tech or pathologist
    @returns Verified lab result
    """
    service = LabService(db)
    try:
        lab_result = await service.verify_result(
            result_id=result_id,
            facility_id=current_user.facility_id,
            verified_by=(
        current_user.user_id
        if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
        else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
    ),
            notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab result not found",
        )
    return LabResultResponse.model_validate(lab_result)


# ── Critical Value Notification ───────────────────────────────────────────────


@router.post(
    "/results/{result_id}/notify-critical",
    response_model=LabResultResponse,
)
async def notify_critical(
    result_id: uuid.UUID,
    data: CriticalNotifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("lab_tech", "admin", "facility_admin")
    ),
) -> LabResultResponse:
    """
    Record that a critical lab value was communicated to a clinician.
    Critical lab values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).

    @param result_id: LabResult UUID
    @param data: Clinician who was notified
    @param db: Database session
    @param current_user: Authenticated lab technician
    @returns Updated lab result with notification recorded
    """
    service = LabService(db)
    lab_result = await service.record_critical_notification(
        result_id=result_id,
        facility_id=current_user.facility_id,
        notified_by=(
        current_user.user_id
        if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
        else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
    ),
        notified_to=data.notified_to,
    )
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab result not found",
        )
    return LabResultResponse.model_validate(lab_result)
