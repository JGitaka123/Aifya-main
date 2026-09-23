import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.appointment import (
    AppointmentCheckIn,
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentSummary,
    AppointmentUpdate,
    AvailableSlot,
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
    DoctorScheduleWithName,
)
from app.services.appointment_service import AppointmentService

# The prefix lives on the router (not on include_router) so the collection
# root can be declared as "", which registers the bare "/api/v1/appointments".
# Declaring it as "/" instead makes FastAPI 307-redirect the bare path while
# Next.js 308-redirects the slashed one, which loops the browser. Both paths
# are registered below; neither redirects.
router = APIRouter(
    prefix="/api/v1/appointments",
    dependencies=[Depends(require_module("appointments"))],
)


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=AppointmentSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentSummary:
    """
    Get appointment dashboard summary for today.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Appointment summary stats
    """
    service = AppointmentService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Doctor Schedules ─────────────────────────────────────────────────────────


@router.get("/schedules", response_model=list[DoctorScheduleWithName])
async def list_schedules(
    doctor_id: uuid.UUID | None = Query(None, description="Filter by doctor"),
    consultation_type: str | None = Query(
        None,
        description=(
            "Filter by clinic type "
            "(general|specialist|follow_up|procedure|anc|dental)"
        ),
    ),
    include_inactive: bool = Query(
        False, description="Include schedules that are switched off"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DoctorScheduleWithName]:
    """
    Get doctor schedules with doctor names.

    @param doctor_id: Optional doctor filter
    @param consultation_type: Optional clinic type filter
    @param include_inactive: Include switched-off schedules
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of doctor schedules
    """
    service = AppointmentService(db)
    return await service.get_schedules(
        facility_id=current_user.facility_id,
        doctor_id=doctor_id,
        consultation_type=consultation_type,
        active_only=not include_inactive,
    )


@router.post("/schedules", response_model=DoctorScheduleWithName, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: DoctorScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> DoctorScheduleWithName:
    """
    Create a doctor availability schedule.

    @param data: Schedule data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created schedule
    """
    service = AppointmentService(db)
    schedule = await service.create_schedule(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return DoctorScheduleWithName.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=DoctorScheduleWithName)
async def update_schedule(
    schedule_id: uuid.UUID,
    data: DoctorScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> DoctorScheduleWithName:
    """
    Update a doctor schedule, e.g. switch a clinic session off.

    @param schedule_id: Schedule UUID
    @param data: Fields to change
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Updated schedule
    """
    service = AppointmentService(db)
    schedule = await service.update_schedule(
        schedule_id=schedule_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor schedule not found",
        )
    return schedule


# ── Available Slots ──────────────────────────────────────────────────────────


@router.get("/slots", response_model=list[AvailableSlot])
async def get_available_slots(
    target_date: date = Query(..., alias="date", description="Date to check availability"),
    doctor_id: uuid.UUID | None = Query(None, description="Filter by doctor"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AvailableSlot]:
    """
    Get available appointment slots for a given date.

    @param target_date: Date to check
    @param doctor_id: Optional doctor filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of available time slots
    """
    service = AppointmentService(db)
    return await service.get_available_slots(
        facility_id=current_user.facility_id,
        target_date=target_date,
        doctor_id=doctor_id,
    )


# ── Appointments ─────────────────────────────────────────────────────────────


@router.get("", response_model=AppointmentListResponse, include_in_schema=False)
@router.get("/", response_model=AppointmentListResponse)
async def list_appointments(
    target_date: date | None = Query(None, alias="date", description="Filter by date"),
    doctor_id: uuid.UUID | None = Query(None, description="Filter by doctor"),
    patient_id: uuid.UUID | None = Query(None, description="Filter by patient"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    appointment_type: str | None = Query(
        None,
        alias="appointment_type",
        description=(
            "Filter by appointment type "
            "(consultation|follow_up|procedure|lab|radiology|anc|dental|vaccination)"
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentListResponse:
    """
    Get appointments with patient and doctor names.

    @param target_date: Optional date filter
    @param doctor_id: Optional doctor filter
    @param patient_id: Optional patient filter
    @param status_filter: Optional status filter
    @param appointment_type: Optional appointment type filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Appointment list with total count
    """
    service = AppointmentService(db)
    items = await service.get_appointments(
        facility_id=current_user.facility_id,
        target_date=target_date,
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status_filter,
        appointment_type=appointment_type,
    )
    return AppointmentListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "receptionist", "admin", "facility_admin")
    ),
) -> AppointmentResponse:
    """
    Book a new appointment.

    @param data: Appointment data
    @param db: Database session
    @param current_user: Authenticated staff
    @returns Created appointment
    """
    service = AppointmentService(db)
    appointment = await service.create_appointment(
        data=data,
        facility_id=current_user.facility_id,
        booked_by=current_user.user_id,
    )
    return AppointmentResponse.model_validate(appointment)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentResponse:
    """
    Get a single appointment by ID.

    @param appointment_id: Appointment UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Appointment detail
    """
    service = AppointmentService(db)
    appt = await service.get_appointment(
        appointment_id=appointment_id,
        facility_id=current_user.facility_id,
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return AppointmentResponse.model_validate(appt)


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "nurse", "receptionist", "admin", "facility_admin")
    ),
) -> AppointmentResponse:
    """
    Update an appointment (reschedule, change status, cancel).

    @param appointment_id: Appointment UUID
    @param data: Update data
    @param db: Database session
    @param current_user: Authenticated staff
    @returns Updated appointment
    """
    service = AppointmentService(db)
    appt = await service.update_appointment(
        appointment_id=appointment_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appointment_id}/check-in", response_model=AppointmentResponse)
async def check_in_appointment(
    appointment_id: uuid.UUID,
    data: AppointmentCheckIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("nurse", "receptionist", "admin", "facility_admin")
    ),
) -> AppointmentResponse:
    """
    Check in a patient for their appointment.

    @param appointment_id: Appointment UUID
    @param data: Optional check-in notes
    @param db: Database session
    @param current_user: Authenticated receptionist or nurse
    @returns Updated appointment
    """
    service = AppointmentService(db)
    appt = await service.check_in(
        appointment_id=appointment_id,
        facility_id=current_user.facility_id,
        checked_in_by=current_user.user_id,
    )
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return AppointmentResponse.model_validate(appt)
