import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.auth.permissions import assignable_roles, is_assignable_role
from app.database import get_db
from app.models.hr import StaffProfile
from app.schemas.hr import (
    AssignableRoleListResponse,
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
    StaffAccessResponse,
    StaffActiveUpdate,
    StaffDirectoryItem,
    StaffDirectoryResponse,
    StaffPasswordUpdate,
    StaffProfileCreate,
    StaffProfileResponse,
    StaffRoleUpdate,
)
from app.services.hr_service import HRService
from app.services.staff_access import StaffAccessError

router = APIRouter(dependencies=[Depends(require_module("hr"))])

#: The HR desk, as one authority. ``hr``, ``hr_admin`` and ``hr_officer`` are
#: the same rank wearing different job titles, so every gate names all three.
_HR_ROLES = ("hr", "hr_admin", "hr_officer")

async def _profile_with_live_balances(
    service: HRService,
    profile: StaffProfile,
    staff_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> StaffProfileResponse:
    """Staff profile with Leave-tab leave reflected in the balance cards.

    @param service: HR service bound to the request session
    @param profile: Persisted staff profile
    @param staff_id: Staff UUID
    @param facility_id: Facility UUID
    @returns Profile response with payroll-approved days deducted
    """
    response = StaffProfileResponse.model_validate(profile)
    taken = await service.payroll_leave_days_by_type(staff_id, facility_id)
    response.annual_leave_balance = max(
        0, profile.annual_leave_balance - taken.get("annual", 0)
    )
    response.sick_leave_balance = max(
        0, profile.sick_leave_balance - taken.get("sick", 0)
    )
    response.maternity_leave_balance = max(
        0, profile.maternity_leave_balance - taken.get("maternity", 0)
    )
    response.paternity_leave_balance = max(
        0, profile.paternity_leave_balance - taken.get("paternity", 0)
    )
    return response


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=HRSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
    include_inactive: bool = Query(
        False, description="Include deactivated staff (admin screens)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
        active_only=not include_inactive,
    )
    return StaffDirectoryResponse(items=items, total=len(items))


@router.patch("/staff/{staff_id}/active", response_model=StaffDirectoryItem)
async def set_staff_active(
    staff_id: uuid.UUID,
    data: StaffActiveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
    ),
) -> StaffDirectoryItem:
    """
    Activate or deactivate a staff member.

    The role says what someone may open; this says whether they may sign in at
    all. Deactivating takes the login away with it, so an employee who leaves
    cannot keep using a session they already had.

    @param staff_id: Staff UUID
    @param data: Desired active state
    @param db: Database session
    @param current_user: Authenticated administrator
    @returns The updated directory entry
    """
    service = HRService(db)
    item = await service.set_staff_active(
        facility_id=current_user.facility_id,
        staff_id=staff_id,
        is_active=data.is_active,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )
    return item


@router.get("/roles", response_model=AssignableRoleListResponse)
async def list_assignable_roles(
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
    ),
) -> AssignableRoleListResponse:
    """
    List the roles HR may assign when adding or editing a staff member.

    This is the picker's source of truth. Because it is served from the same
    catalogue the write endpoints validate against, the interface cannot offer
    a role the API would then refuse, and no screen can invent one.

    @param current_user: Authenticated administrator
    @returns Assignable roles with the access each one carries
    """
    items = assignable_roles()
    return AssignableRoleListResponse(items=items, total=len(items))


@router.patch("/staff/{staff_id}/role", response_model=StaffDirectoryItem)
async def set_staff_role(
    staff_id: uuid.UUID,
    data: StaffRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
    ),
) -> StaffDirectoryItem:
    """
    Change which role a staff member holds.

    The new role takes effect on the employee's next request: /auth/me resolves
    permissions from the staff record rather than from the token, so their tabs
    change at the next page load instead of when the token expires.

    @param staff_id: Staff UUID
    @param data: The role to assign
    @param db: Database session
    @param current_user: Authenticated administrator
    @returns The updated directory entry
    @raises HTTPException 422: When the role is not one HR may assign
    """
    if not is_assignable_role(data.role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "That is not a role HR can assign. Choose one from "
                "GET /hr/roles."
            ),
        )
    service = HRService(db)
    item = await service.set_staff_role(
        facility_id=current_user.facility_id,
        staff_id=staff_id,
        role=data.role,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )
    return item


@router.post("/staff/{staff_id}/password", response_model=StaffAccessResponse)
async def set_staff_password(
    staff_id: uuid.UUID,
    data: StaffPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
    ),
) -> StaffAccessResponse:
    """
    Set or reset a staff member's sign-in password.

    With no email delivery in internal-auth mode, HR hands the password over
    in person; this is how a new employee gets their first one and how a
    forgotten one is replaced.

    @param staff_id: Staff UUID
    @param data: The new password
    @param db: Database session
    @param current_user: Authenticated administrator
    @returns Confirmation naming the staff member
    @raises HTTPException 404: When the staff member is not at this facility
    @raises HTTPException 422: When the password is rejected
    """
    service = HRService(db)
    try:
        staff = await service.set_staff_password(
            facility_id=current_user.facility_id,
            staff_id=staff_id,
            password=data.password,
        )
    except StaffAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )
    return StaffAccessResponse(
        staff_id=staff.id,
        role=staff.role,
        has_login=True,
        message=(
            f"Password updated for {staff.first_name} {staff.last_name}."
        ),
    )


# ── Staff Profiles ───────────────────────────────────────────────────────────


@router.get("/staff/{staff_id}/profile", response_model=StaffProfileResponse)
async def get_staff_profile(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
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
    return await _profile_with_live_balances(
        service, profile, staff_id, current_user.facility_id
    )


@router.put("/staff/{staff_id}/profile", response_model=StaffProfileResponse)
async def upsert_staff_profile(
    staff_id: uuid.UUID,
    data: StaffProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*_HR_ROLES)
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
    return await _profile_with_live_balances(
        service, profile, staff_id, current_user.facility_id
    )


# ── Shifts ───────────────────────────────────────────────────────────────────


@router.get("/shifts", response_model=list[ShiftResponse])
async def list_shifts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
        require_roles(*_HR_ROLES)
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
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
        require_roles(*_HR_ROLES)
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
    current_user: CurrentUser = Depends(require_roles(*_HR_ROLES)),
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
