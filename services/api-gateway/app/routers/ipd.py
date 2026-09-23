import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.emergency import EmergencyVisitResponse
from app.schemas.ipd import (
    AdmissionCreate,
    AdmissionListResponse,
    AdmissionResponse,
    BedCreate,
    BedResponse,
    DischargeRequest,
    NursingNoteCreate,
    NursingNoteResponse,
    TransferToEmergencyRequest,
    WardBoardSummary,
    WardCreate,
    WardResponse,
)
from app.services.emergency_service import EmergencyService
from app.services.ipd_service import IPDService

router = APIRouter(dependencies=[Depends(require_module("ipd"))])


# ── Ward Board Summary ────────────────────────────────────────────────────────


@router.get("/summary", response_model=WardBoardSummary)
async def get_ward_board_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WardBoardSummary:
    """
    Get IPD ward board summary: bed occupancy, active admissions.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Ward board summary stats
    """
    service = IPDService(db)
    return await service.get_ward_board_summary(current_user.facility_id)


# ── Ward Management ───────────────────────────────────────────────────────────


@router.get("/wards", response_model=list[WardResponse])
async def list_wards(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[WardResponse]:
    """
    List all active wards with bed occupancy counts.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of wards
    """
    service = IPDService(db)
    return await service.get_wards(current_user.facility_id)


@router.post(
    "/wards",
    response_model=WardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ward(
    data: WardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> WardResponse:
    """
    Create a new ward.

    @param data: Ward creation data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created ward
    """
    service = IPDService(db)
    ward = await service.create_ward(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return WardResponse.model_validate(ward)


# ── Bed Management ──────────────────────────────────────────────��─────────────


@router.get("/beds", response_model=list[BedResponse])
async def list_beds(
    ward_id: uuid.UUID | None = Query(None),
    bed_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[BedResponse]:
    """
    List beds with optional ward and status filters.

    @param ward_id: Optional ward filter
    @param bed_status: Optional bed status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of beds
    """
    service = IPDService(db)
    return await service.get_beds(
        facility_id=current_user.facility_id,
        ward_id=ward_id,
        status_filter=bed_status,
    )


@router.post(
    "/beds",
    response_model=BedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bed(
    data: BedCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> BedResponse:
    """
    Create a new bed in a ward.

    @param data: Bed creation data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created bed
    """
    service = IPDService(db)
    bed = await service.create_bed(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return BedResponse.model_validate(bed)


# ── Admissions ────────────────────────────────────────────────────────────────


@router.get("/admissions", response_model=AdmissionListResponse)
async def list_admissions(
    status_filter: str | None = Query(None, alias="status"),
    ward_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdmissionListResponse:
    """
    List active admissions with patient and ward info.

    @param status_filter: Optional status filter
    @param ward_id: Optional ward filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Admission list
    """
    service = IPDService(db)
    items, total = await service.get_admissions(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
        ward_id=ward_id,
    )
    return AdmissionListResponse(items=items, total=total)


@router.post(
    "/admissions",
    response_model=AdmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admit_patient(
    data: AdmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "admin", "facility_admin")
    ),
    x_idempotency_key: str | None = Header(None),
) -> AdmissionResponse:
    """
    Admit a patient — assigns bed, creates admission record.

    @param data: Admission data
    @param db: Database session
    @param current_user: Authenticated doctor or nurse
    @param x_idempotency_key: Optional idempotency key
    @returns Created admission
    """
    service = IPDService(db)
    try:
        admission = await service.admit_patient(
            data=data,
            facility_id=current_user.facility_id,
            admitted_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return AdmissionResponse.model_validate(admission)


@router.post(
    '/admissions/{admission_id}/transfer-to-emergency',
    response_model=EmergencyVisitResponse,
)
async def transfer_inpatient_to_emergency(
    admission_id: uuid.UUID,
    data: TransferToEmergencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles('doctor', 'nurse', 'admin', 'facility_admin')
    ),
) -> EmergencyVisitResponse:
    '''
    Transfer an inpatient whose condition has worsened to the Emergency Room.

    Registers an emergency visit for the patient and closes the IPD
    admission as transferred, freeing the ward bed.

    @param admission_id: Admission UUID
    @param data: Transfer reason and notes
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Created emergency visit
    '''
    service = EmergencyService(db)
    try:
        visit = await service.transfer_inpatient_to_emergency(
            admission_id=admission_id,
            data=data,
            facility_id=current_user.facility_id,
            transferred_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Admission not found',
        )
    return EmergencyVisitResponse.model_validate(visit)


@router.get("/admissions/{admission_id}", response_model=AdmissionResponse)
async def get_admission_detail(
    admission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdmissionResponse:
    """
    Get a single admission detail.

    @param admission_id: Admission UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Admission detail
    """
    service = IPDService(db)
    admission = await service.get_admission_detail(
        admission_id=admission_id,
        facility_id=current_user.facility_id,
    )
    if not admission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admission not found",
        )
    return AdmissionResponse.model_validate(admission)


# ── Discharge ─────────────────────────────────────────────────────────────────


@router.post(
    "/admissions/{admission_id}/discharge",
    response_model=AdmissionResponse,
)
async def discharge_patient(
    admission_id: uuid.UUID,
    data: DischargeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> AdmissionResponse:
    """
    Discharge an inpatient — frees bed, updates encounter status.

    @param admission_id: Admission UUID
    @param data: Discharge details
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Updated admission with discharge info
    """
    service = IPDService(db)
    try:
        admission = await service.discharge_patient(
            admission_id=admission_id,
            data=data,
            facility_id=current_user.facility_id,
            discharged_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    if not admission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admission not found",
        )
    return AdmissionResponse.model_validate(admission)


# ── Nursing Notes ─────────────────────────────────────────────────────────────


@router.get(
    "/admissions/{admission_id}/notes",
    response_model=list[NursingNoteResponse],
)
async def list_nursing_notes(
    admission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[NursingNoteResponse]:
    """
    Get all nursing notes for an admission.

    @param admission_id: Admission UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of nursing notes
    """
    service = IPDService(db)
    notes = await service.get_nursing_notes(
        admission_id=admission_id,
        facility_id=current_user.facility_id,
    )
    return [NursingNoteResponse.model_validate(n) for n in notes]


@router.post(
    "/admissions/{admission_id}/notes",
    response_model=NursingNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_nursing_note(
    admission_id: uuid.UUID,
    data: NursingNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("nurse", "doctor", "admin", "facility_admin")
    ),
) -> NursingNoteResponse:
    """
    Add a nursing note to an admission.

    @param admission_id: Admission UUID
    @param data: Note data
    @param db: Database session
    @param current_user: Authenticated nurse or doctor
    @returns Created nursing note
    """
    service = IPDService(db)
    try:
        note = await service.add_nursing_note(
            admission_id=admission_id,
            data=data,
            facility_id=current_user.facility_id,
            author_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return NursingNoteResponse.model_validate(note)
