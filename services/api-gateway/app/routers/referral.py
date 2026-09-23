import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.referral import (
    FacilityLookupItem,
    FacilityLookupResponse,
    ReferralCreate,
    ReferralListResponse,
    ReferralResponse,
    ReferralSummary,
    ReferralUpdateStatus,
)
from app.services.referral.note_generator import generate_referral_note_pdf
from app.services.referral_service import ReferralService

router = APIRouter(dependencies=[Depends(require_module("referrals"))])


@router.get("/summary", response_model=ReferralSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralSummary:
    """
    Get referral summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral summary
    """
    service = ReferralService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


@router.get("", response_model=ReferralListResponse)
async def list_referrals(
    direction: str | None = Query(None, description="Filter by direction"),
    ref_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralListResponse:
    """
    Get referrals.

    @param direction: Optional direction filter
    @param ref_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral list
    """
    service = ReferralService(db)
    items = await service.get_referrals(
        facility_id=current_user.facility_id,
        direction=direction,
        status=ref_status,
    )
    return ReferralListResponse(items=items, total=len(items))


@router.post("", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def create_referral(
    data: ReferralCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> ReferralResponse:
    """
    Create a referral.

    @param data: Referral data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Created referral
    """
    service = ReferralService(db)
    referral = await service.create_referral(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        initial_status=data.initial_status,
    )
    return ReferralResponse.model_validate(referral)


@router.get("/facility-lookup", response_model=FacilityLookupResponse)
async def lookup_facilities(
    q: str = Query(
        ..., min_length=2, description="Facility name, MFL code or facility code"
    ),
    limit: int = Query(10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FacilityLookupResponse:
    """
    Search the facility register for a referral destination.

    A clinician must be able to tell whether the hospital being referred to
    exists in the register, and which MFL code belongs to it, before the
    referral is dispatched - the same check the pharmacy makes on stock before
    a medicine is prescribed.

    @param q: Facility name, MFL code or facility code
    @param limit: Maximum number of matches
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Matching facilities, shortest name first
    """
    service = ReferralService(db)
    facilities = await service.search_facilities(q, limit=limit)
    return FacilityLookupResponse(
        items=[FacilityLookupItem.model_validate(f) for f in facilities],
        total=len(facilities),
    )


@router.get("/{referral_id}", response_model=ReferralResponse)
async def get_referral(
    referral_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralResponse:
    """
    Get a single referral.

    @param referral_id: Referral UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral details
    """
    service = ReferralService(db)
    referral = await service.get_referral(referral_id, current_user.facility_id)
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return ReferralResponse.model_validate(referral)


@router.get("/{referral_id}/pdf-note")
async def get_referral_pdf(
    referral_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Generate a standardized referral note PDF.

    @param referral_id: Referral UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns PDF binary response
    @raises HTTPException 404: If referral is not found
    """
    try:
        pdf_bytes = await generate_referral_note_pdf(
            db,
            referral_id=referral_id,
            facility_id=current_user.facility_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="referral-{referral_id}.pdf"'
            ),
        },
    )


@router.post("/{referral_id}/status", response_model=ReferralResponse)
async def update_referral_status(
    referral_id: uuid.UUID,
    data: ReferralUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> ReferralResponse:
    """
    Update referral status.

    @param referral_id: Referral UUID
    @param data: Status update data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Updated referral
    """
    service = ReferralService(db)
    referral = await service.update_status(
        referral_id=referral_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return ReferralResponse.model_validate(referral)
