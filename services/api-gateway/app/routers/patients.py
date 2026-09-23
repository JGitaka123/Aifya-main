import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_patient_read
from app.auth.dependencies import require_roles
from app.auth.license_check import require_module, require_patient_capacity
from app.database import get_db
from app.schemas.event import EventResponse, TimelineResponse
from app.schemas.patient import (
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    DuplicateMatch,
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.services.event_service import EventService
from app.services.patient_service import PatientService

# Roles allowed to create/update patient demographics. Reads default to
# all authenticated facility staff (cashiers, lab, pharmacy all need
# lookup) but a facility can restrict them via PATIENT_READ_ROLES
# (enforced by require_patient_read).
_PATIENT_WRITE_ROLES = (
    "receptionist",
    "records",
    "nurse",
    "midwife",
    "doctor",
    "admin",
    "facility_admin",
)

router = APIRouter(dependencies=[Depends(require_module("patients"))])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_patient_capacity())],
)
async def register_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_PATIENT_WRITE_ROLES)),
    x_idempotency_key: str | None = Header(None),
) -> PatientResponse:
    """
    Register a new patient.

    @param data: Patient registration data (validated by Pydantic)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key for safe retries
    @returns Created patient
    """
    service = PatientService(db)
    patient = await service.register_patient(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    return PatientResponse.model_validate(patient)


@router.post("/check-duplicates", response_model=DuplicateCheckResponse)
async def check_duplicates(
    data: DuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_PATIENT_WRITE_ROLES)),
) -> DuplicateCheckResponse:
    """
    Check for likely-duplicate patients before registering a new one (D7).

    Matches on National ID, passport, phone, or (name + DOB). The frontend
    uses this to surface a "possible duplicate — review / use existing /
    register anyway" prompt before creating a second record.

    @param data: Candidate patient identifiers
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Possible duplicates with the reasons they matched
    """
    service = PatientService(db)
    matches = await service.find_potential_duplicates(
        facility_id=current_user.facility_id,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        phone_number=data.phone_number,
        national_id=data.national_id,
        passport_number=data.passport_number,
    )
    return DuplicateCheckResponse(
        has_duplicates=bool(matches),
        matches=[
            DuplicateMatch(
                patient=PatientResponse.model_validate(patient),
                match_reasons=reasons,
            )
            for patient, reasons in matches
        ],
    )


@router.get("", response_model=PatientListResponse)
async def list_patients(
    q: str | None = Query(None, description="Search by name, ID, phone, or MRN"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> PatientListResponse:
    """
    Search and list patients with pagination.

    @param q: Optional search query
    @param page: Page number (1-based)
    @param page_size: Number of results per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated list of patients
    """
    service = PatientService(db)
    patients, total = await service.search_patients(
        facility_id=current_user.facility_id,
        query=q,
        page=page,
        page_size=page_size,
    )
    return PatientListResponse(
        items=[PatientResponse.model_validate(p) for p in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> PatientResponse:
    """
    Get a single patient by ID.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Patient details
    """
    service = PatientService(db)
    patient = await service.get_patient(patient_id, current_user.facility_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_PATIENT_WRITE_ROLES)),
    x_idempotency_key: str | None = Header(None),
) -> PatientResponse:
    """
    Update patient demographics.

    @param patient_id: Patient UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key
    @returns Updated patient
    """
    service = PatientService(db)
    patient = await service.update_patient(
        patient_id=patient_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}/timeline", response_model=TimelineResponse)
async def get_patient_timeline(
    patient_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> TimelineResponse:
    """
    Get the event timeline for a patient.

    @param patient_id: Patient UUID
    @param limit: Max events to return
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Event timeline
    """
    event_service = EventService(db)
    events, total = await event_service.get_patient_timeline(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        limit=limit,
    )
    return TimelineResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
    )
