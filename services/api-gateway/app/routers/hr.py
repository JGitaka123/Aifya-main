import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.hr import (
    AttendanceClockIn,
    AttendanceClockOut,
    AttendanceListResponse,
    AttendanceResponse,
    HRSummary,
    LeaveApprovalRequest,
    LeaveRequestCreate,
    LeaveRequestListResponse,
    LeaveRequestResponse,
    ShiftAssignmentCreate,
    ShiftAssignmentListResponse,
    ShiftAssignmentResponse,
    ShiftCreate,
    ShiftResponse,
    StaffDirectoryResponse,
    StaffProfileCreate,
    StaffProfileResponse,
)
from app.services.hr_service import HRService

router = APIRouter(dependencies=[Depends(require_module("hr"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=HRSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> HRSummary:
    """
    Get HR dashboard summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns HR summary
    """
    service = HRService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Staff Directory ──────────────────────────────────────────────────────────


@router.get("/staff", response_model=StaffDirectoryResponse)
async def get_staff_directory(
    role: str | None = Query(None, description="Filter by role"),
    department_id: uuid.UUID | None = Query(None, description="Filter by department"),
    search: str | None = Query(None, description="Search by name or employee number"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StaffDirectoryResponse:
    """
    Get staff directory with department names.

    @param role: Optional role filter
    @param department_id: Optional department filter
    @param search: Optional search query
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Staff directory
    """
    service = HRService(db)
    items = await service.get_staff_directory(
        facility_id=current_user.facility_id,
        role=role,
        department_id=department_id,
        search=search,
    )
    return StaffDirectoryResponse(items=items, total=len(items))


# ── Staff Profiles ───────────────────────────────────────────────────────────


@router.get("/staff/{staff_id}/profile", response_model=StaffProfileResponse)
async def get_staff_profile(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> StaffProfileResponse:
    """
    Get extended staff profile.

    @param staff_id: Staff UUID
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Staff profile
    """
    service = HRService(db)
    profile = await service.get_profile(
        staff_id=staff_id,
        facility_id=current_user.facility_id,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found",
        )
    return StaffProfileResponse.model_validate(profile)


@router.put("/staff/{staff_id}/profile", response_model=StaffProfileResponse)
async def upsert_staff_profile(
    staff_id: uuid.UUID,
    data: StaffProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> StaffProfileResponse:
    """
    Create or update a staff profile.

    @param staff_id: Staff UUID
    @param data: Profile data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created/updated profile
    """
    data.staff_id = staff_id
    service = HRService(db)
    profile = await service.upsert_profile(
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    return StaffProfileResponse.model_validate(profile)


# ── Shifts ───────────────────────────────────────────────────────────────────


@router.get("/shifts", response_model=list[ShiftResponse])
async def list_shifts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ShiftResponse]:
    """
    Get all active shift definitions.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of shifts
    """
    service = HRService(db)
    shifts = await service.get_shifts(facility_id=current_user.facility_id)
    return [ShiftResponse.model_validate(s) for s in shifts]


@router.post("/shifts", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(
    data: ShiftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> ShiftResponse:
    """
    Create a shift definition.

    @param data: Shift data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created shift
    """
    service = HRService(db)
    shift = await service.create_shift(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return ShiftResponse.model_validate(shift)


# ── Shift Assignments ────────────────────────────────────────────────────────


@router.get("/shift-assignments", response_model=ShiftAssignmentListResponse)
async def list_shift_assignments(
    target_date: date | None = Query(None, alias="date", description="Filter by date"),
    staff_id: uuid.UUID | None = Query(None, description="Filter by staff"),
    department_id: uuid.UUID | None = Query(None, description="Filter by department"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ShiftAssignmentListResponse:
    """
    Get shift assignments with staff and shift names.

    @param target_date: Optional date filter
    @param staff_id: Optional staff filter
    @param department_id: Optional department filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Shift assignment list
    """
    service = HRService(db)
    items = await service.get_shift_assignments(
        facility_id=current_user.facility_id,
        target_date=target_date,
        staff_id=staff_id,
        department_id=department_id,
    )
    return ShiftAssignmentListResponse(items=items, total=len(items))


@router.post(
    "/shift-assignments",
    response_model=ShiftAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_shift_assignment(
    data: ShiftAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "nurse")
    ),
) -> ShiftAssignmentResponse:
    """
    Assign a staff member to a shift.

    @param data: Assignment data
    @param db: Database session
    @param current_user: Authenticated admin or charge nurse
    @returns Created assignment
    """
    service = HRService(db)
    try:
        assignment = await service.assign_shift(
            data=data,
            facility_id=current_user.facility_id,
            created_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return ShiftAssignmentResponse.model_validate(assignment)


# ── Leave Requests ───────────────────────────────────────────────────────────


@router.get("/leave", response_model=LeaveRequestListResponse)
async def list_leave_requests(
    staff_id: uuid.UUID | None = Query(None, description="Filter by staff"),
    leave_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeaveRequestListResponse:
    """
    Get leave requests with staff names.

    @param staff_id: Optional staff filter
    @param leave_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Leave request list
    """
    service = HRService(db)
    items = await service.get_leave_requests(
        facility_id=current_user.facility_id,
        staff_id=staff_id,
        status=leave_status,
    )
    return LeaveRequestListResponse(items=items, total=len(items))


@router.post(
    "/leave",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    data: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeaveRequestResponse:
    """
    Submit a leave request.

    @param data: Leave request data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Created leave request
    """
    service = HRService(db)
    try:
        staff_id = await service.resolve_staff_id(
            current_user.user_id, current_user.facility_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    leave = await service.create_leave_request(
        data=data,
        staff_id=staff_id,
        facility_id=current_user.facility_id,
    )
    return LeaveRequestResponse.model_validate(leave)


@router.post("/leave/{leave_id}/process", response_model=LeaveRequestResponse)
async def process_leave_request(
    leave_id: uuid.UUID,
    data: LeaveApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> LeaveRequestResponse:
    """
    Approve or reject a leave request.

    @param leave_id: Leave request UUID
    @param data: Approval/rejection data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Updated leave request
    """
    service = HRService(db)
    leave = await service.process_leave(
        leave_id=leave_id,
        data=data,
        facility_id=current_user.facility_id,
        processed_by=current_user.user_id,
    )
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )
    return LeaveRequestResponse.model_validate(leave)


# ── Attendance ───────────────────────────────────────────────────────────────


@router.get("/attendance", response_model=AttendanceListResponse)
async def list_attendance(
    target_date: date | None = Query(None, alias="date", description="Filter by date"),
    staff_id: uuid.UUID | None = Query(None, description="Filter by staff"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AttendanceListResponse:
    """
    Get attendance records.

    @param target_date: Optional date filter
    @param staff_id: Optional staff filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Attendance list
    """
    service = HRService(db)
    items = await service.get_attendance(
        facility_id=current_user.facility_id,
        target_date=target_date,
        staff_id=staff_id,
    )
    return AttendanceListResponse(items=items, total=len(items))


@router.post(
    "/attendance/clock-in",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clock_in(
    data: AttendanceClockIn,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AttendanceResponse:
    """
    Record clock-in for current user.

    @param data: Clock-in data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Attendance record
    """
    service = HRService(db)
    try:
        staff_id = await service.resolve_staff_id(
            current_user.user_id, current_user.facility_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    attendance = await service.clock_in(
        data=data,
        staff_id=staff_id,
        facility_id=current_user.facility_id,
    )
    return AttendanceResponse.model_validate(attendance)


@router.post("/attendance/{attendance_id}/clock-out", response_model=AttendanceResponse)
async def clock_out(
    attendance_id: uuid.UUID,
    data: AttendanceClockOut,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AttendanceResponse:
    """
    Record clock-out.

    @param attendance_id: Attendance UUID
    @param data: Clock-out data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated attendance record
    """
    service = HRService(db)
    try:
        staff_id = await service.resolve_staff_id(
            current_user.user_id, current_user.facility_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    attendance = await service.clock_out(
        attendance_id=attendance_id,
        data=data,
        facility_id=current_user.facility_id,
        staff_id=staff_id,
    )
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found",
        )
    return AttendanceResponse.model_validate(attendance)
