import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.mch import (
    ANCProfileCreate,
    ANCProfileDetail,
    ANCProfileListResponse,
    ANCProfileResponse,
    ANCVisitCreate,
    ANCVisitResponse,
    ChildRecordCreate,
    ChildRecordListResponse,
    ChildRecordResponse,
    DeliveryRecordCreate,
    DeliveryRecordResponse,
    ImmunizationCreate,
    ImmunizationResponse,
    ImmunizationScheduleItem,
    ImmunizationUpdate,
    MCHSummary,
)
from app.services.mch_service import MCHService

router = APIRouter(dependencies=[Depends(require_module("mch"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=MCHSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MCHSummary:
    """
    Get MCH department dashboard summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns MCH summary with ANC, delivery, and child stats
    """
    service = MCHService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Immunization schedule ──────────────────────────────────────────────────


@router.get(
    "/immunization-schedule",
    response_model=list[ImmunizationScheduleItem],
)
async def get_immunization_schedule(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ImmunizationScheduleItem]:
    """
    Get the national EPI routine immunization schedule.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Routine doses in due order
    """
    service = MCHService(db)
    return service.get_immunization_schedule()


# ── ANC Profiles ─────────────────────────────────────────────────────────


@router.get("/anc", response_model=ANCProfileListResponse)
async def list_anc_profiles(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by ANC status"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ANCProfileListResponse:
    """
    Get ANC profiles with patient info and visit counts.

    @param status_filter: Optional status filter (active|delivered|postnatal|closed)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated ANC profile list
    """
    service = MCHService(db)
    items = await service.get_anc_profiles(
        facility_id=current_user.facility_id,
        status=status_filter,
    )
    return ANCProfileListResponse(items=items, total=len(items))


@router.post("/anc", response_model=ANCProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_anc_profile(
    data: ANCProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> ANCProfileResponse:
    """
    Register a new pregnancy / ANC profile.

    @param data: ANC profile data
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Created ANC profile
    """
    service = MCHService(db)
    try:
        profile = await service.create_anc_profile(
            data=data,
            facility_id=current_user.facility_id,
            created_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return ANCProfileResponse.model_validate(profile)


@router.get("/anc/{profile_id}", response_model=ANCProfileDetail)
async def get_anc_profile_detail(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ANCProfileDetail:
    """
    Get full ANC profile with visits, delivery, and patient info.

    @param profile_id: ANC profile UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Full ANC profile detail
    """
    service = MCHService(db)
    detail = await service.get_anc_profile_detail(
        profile_id=profile_id,
        facility_id=current_user.facility_id,
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ANC profile not found",
        )
    return detail


# ── ANC Visits ───────────────────────────────────────────────────────────────


@router.post("/anc/visits", response_model=ANCVisitResponse, status_code=status.HTTP_201_CREATED)
async def add_anc_visit(
    data: ANCVisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> ANCVisitResponse:
    """
    Record an ANC visit with vitals, obstetric exam, and interventions.

    @param data: ANC visit data
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Created ANC visit
    """
    service = MCHService(db)
    try:
        visit = await service.add_anc_visit(
            data=data,
            facility_id=current_user.facility_id,
            provider_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return ANCVisitResponse.model_validate(visit)


# ── Delivery ─────────────────────────────────────────────────────────────────


@router.post("/delivery", response_model=DeliveryRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_delivery(
    data: DeliveryRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> DeliveryRecordResponse:
    """
    Record a delivery. Updates ANC profile status and pregnancy outcome.

    @param data: Delivery record data
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Created delivery record
    """
    service = MCHService(db)
    try:
        delivery = await service.record_delivery(
            data=data,
            facility_id=current_user.facility_id,
            delivered_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return DeliveryRecordResponse.model_validate(delivery)


# ── Child Records ────────────────────────────────────────────────────────────


@router.get("/children", response_model=ChildRecordListResponse)
async def list_child_records(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChildRecordListResponse:
    """
    Get child health records with immunization counts.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Child record list
    """
    service = MCHService(db)
    items = await service.get_child_records(facility_id=current_user.facility_id)
    return ChildRecordListResponse(items=items, total=len(items))


@router.post("/children", response_model=ChildRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_child_record(
    data: ChildRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> ChildRecordResponse:
    """
    Create a child health record.

    @param data: Child record data
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Created child record
    """
    service = MCHService(db)
    try:
        child = await service.create_child_record(
            data=data,
            facility_id=current_user.facility_id,
            created_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return ChildRecordResponse.model_validate(child)


# ── Immunizations ────────────────────────────────────────────────────────────


@router.get("/children/{child_id}/immunizations", response_model=list[ImmunizationResponse])
async def list_immunizations(
    child_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ImmunizationResponse]:
    """
    Get all immunizations for a child.

    @param child_id: Child record UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of immunization records
    """
    service = MCHService(db)
    immunizations = await service.get_immunizations(
        child_record_id=child_id,
        facility_id=current_user.facility_id,
    )
    return [ImmunizationResponse.model_validate(i) for i in immunizations]


@router.post("/children/{child_id}/immunizations", response_model=ImmunizationResponse, status_code=status.HTTP_201_CREATED)
async def record_immunization(
    child_id: uuid.UUID,
    data: ImmunizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> ImmunizationResponse:
    """
    Record an immunization dose for a child.

    @param child_id: Child record UUID
    @param data: Immunization data
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Created immunization record
    """
    service = MCHService(db)
    try:
        immunization = await service.record_immunization(
            data=data,
            facility_id=current_user.facility_id,
            administered_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return ImmunizationResponse.model_validate(immunization)


@router.patch("/immunizations/{immunization_id}", response_model=ImmunizationResponse)
async def update_immunization(
    immunization_id: uuid.UUID,
    data: ImmunizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> ImmunizationResponse:
    """
    Correct a recorded immunization dose.

    @param immunization_id: Immunization UUID
    @param data: Fields to correct
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Updated immunization record
    """
    service = MCHService(db)
    try:
        immunization = await service.update_immunization(
            immunization_id=immunization_id,
            data=data,
            facility_id=current_user.facility_id,
            updated_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return ImmunizationResponse.model_validate(immunization)


@router.delete(
    "/immunizations/{immunization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_immunization(
    immunization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "midwife", "admin", "facility_admin")
    ),
) -> None:
    """
    Remove a dose that was recorded in error (soft delete).

    @param immunization_id: Immunization UUID
    @param db: Database session
    @param current_user: Authenticated clinician
    """
    service = MCHService(db)
    try:
        await service.delete_immunization(
            immunization_id=immunization_id,
            facility_id=current_user.facility_id,
            deleted_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
