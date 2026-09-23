import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import Attendance, LeaveRequest, Shift, ShiftAssignment, StaffProfile
from app.models.staff import Department, Staff
from app.schemas.hr import (

    AttendanceClockIn,
    AttendanceClockOut,
    AttendanceResponse,
    HRSummary,
    LeaveApprovalRequest,
    LeaveRequestCreate,
    LeaveRequestResponse,
    ShiftAssignmentCreate,
    ShiftAssignmentResponse,
    ShiftCreate,
    StaffDirectoryItem,
    StaffProfileCreate,
)
from app.services.leave_overlap import staff_ids_on_approved_leave


class HRService:
    """
    Service for HR management: staff directory, profiles, shifts,
    shift assignments, leave requests, attendance, and analytics.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_staff_id(
        self, keycloak_user_id: uuid.UUID, facility_id: uuid.UUID
    ) -> uuid.UUID:
        """
        Resolve the Staff row ID for an authenticated Keycloak user.

        Attendance/leave/shift rows reference staff.id; the JWT carries the
        Keycloak user ID, so it must be mapped before writing those rows.

        @param keycloak_user_id: Keycloak user UUID from the JWT
        @param facility_id: Facility UUID
        @returns Staff UUID
        @raises ValueError: If no active staff profile is linked to the user
        """
        result = await self.db.execute(
            select(Staff.id).where(
                Staff.keycloak_user_id == keycloak_user_id,
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        staff_id = result.scalar_one_or_none()
        if staff_id is None:
            raise ValueError("No staff profile is linked to this user")
        return staff_id

    # ── Staff Directory ──────────────────────────────────────────────────

    async def get_staff_directory(
        self,
        facility_id: uuid.UUID,
        role: str | None = None,
        department_id: uuid.UUID | None = None,
        search: str | None = None,
        active_only: bool = True,
    ) -> list[StaffDirectoryItem]:
        """
        Get staff directory with department names.

        @param facility_id: Facility UUID
        @param role: Optional role filter
        @param department_id: Optional department filter
        @param search: Optional name search
        @param active_only: Only active staff
        @returns List of staff directory items
        """
        query = (
            select(Staff, Department.name.label("dept_name"))
            .outerjoin(Department, Staff.department_id == Department.id)
            .where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        if active_only:
            query = query.where(Staff.is_active == True)  # noqa: E712
        if role:
            query = query.where(Staff.role == role)
        if department_id:
            query = query.where(Staff.department_id == department_id)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Staff.first_name.ilike(pattern))
                | (Staff.last_name.ilike(pattern))
                | (Staff.employee_number.ilike(pattern))
            )

        query = query.order_by(Staff.last_name.asc(), Staff.first_name.asc())
        result = await self.db.execute(query)
        rows = result.all()

        items: list[StaffDirectoryItem] = []
        for staff, dept_name in rows:
            item = StaffDirectoryItem.model_validate(staff)
            item.department_name = dept_name
            items.append(item)

        return items

    # ── Staff Profiles ───────────────────────────────────────────────────

    async def get_profile(
        self,
        staff_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> StaffProfile | None:
        """
        Get extended staff profile.

        @param staff_id: Staff UUID
        @param facility_id: Facility UUID
        @returns Staff profile or None
        """
        result = await self.db.execute(
            select(StaffProfile).where(
                StaffProfile.staff_id == staff_id,
                StaffProfile.facility_id == facility_id,
                StaffProfile.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def upsert_profile(
        self,
        data: StaffProfileCreate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> StaffProfile:
        """
        Create or update a staff profile.

        @param data: Profile data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Created/updated profile
        """
        existing = await self.get_profile(data.staff_id, facility_id)

        if existing:
            for field, value in data.model_dump(exclude_unset=True, exclude={"staff_id"}).items():
                setattr(existing, field, value)
            existing.updated_by = updated_by
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        profile = StaffProfile(
            facility_id=facility_id,
            staff_id=data.staff_id,
            **data.model_dump(exclude={"staff_id"}),
            created_by=updated_by,
            updated_by=updated_by,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    # ── Shifts ───────────────────────────────────────────────────────────

    async def create_shift(
        self,
        data: ShiftCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> Shift:
        """
        Create a shift definition.

        @param data: Shift data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created shift
        """
        shift = Shift(
            facility_id=facility_id,
            code=data.code,
            name=data.name,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_hours=data.duration_hours,
            is_night_shift=data.is_night_shift,
            department_id=data.department_id,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(shift)
        await self.db.flush()
        await self.db.refresh(shift)
        return shift

    async def get_shifts(
        self, facility_id: uuid.UUID
    ) -> list[Shift]:
        """
        Get all active shift definitions.

        @param facility_id: Facility UUID
        @returns List of shifts
        """
        result = await self.db.execute(
            select(Shift)
            .where(
                Shift.facility_id == facility_id,
                Shift.is_deleted == False,  # noqa: E712
                Shift.is_active == True,  # noqa: E712
            )
            .order_by(Shift.start_time.asc())
        )
        return list(result.scalars().all())

    # ── Shift Assignments ────────────────────────────────────────────────

    async def assign_shift(
        self,
        data: ShiftAssignmentCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> ShiftAssignment:
        """
        Assign a staff member to a shift on a date.

        @param data: Assignment data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created assignment
        @raises ValueError: If the staff member or shift does not exist
        """
        staff_exists = await self.db.execute(
            select(Staff.id).where(
                Staff.id == data.staff_id,
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        if staff_exists.scalar_one_or_none() is None:
            raise ValueError("Staff member not found")

        shift_exists = await self.db.execute(
            select(Shift.id).where(
                Shift.id == data.shift_id,
                Shift.facility_id == facility_id,
                Shift.is_deleted == False,  # noqa: E712
            )
        )
        if shift_exists.scalar_one_or_none() is None:
            raise ValueError("Shift not found")

        # Staff on approved leave (HR or payroll Leave tab) cannot be assigned.
        on_leave_ids = await staff_ids_on_approved_leave(
            self.db, facility_id, data.assignment_date
        )
        if data.staff_id in on_leave_ids:
            raise ValueError(
                "Staff member is on approved leave for this date"
            )

        assignment = ShiftAssignment(
            facility_id=facility_id,
            staff_id=data.staff_id,
            shift_id=data.shift_id,
            department_id=data.department_id,
            assignment_date=data.assignment_date,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def get_shift_assignments(
        self,
        facility_id: uuid.UUID,
        target_date: date | None = None,
        staff_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
    ) -> list[ShiftAssignmentResponse]:
        """
        Get shift assignments with staff and shift names.

        @param facility_id: Facility UUID
        @param target_date: Optional date filter
        @param staff_id: Optional staff filter
        @param department_id: Optional department filter
        @returns List of shift assignments
        """
        query = (
            select(ShiftAssignment, Staff.first_name, Staff.last_name, Shift.name.label("shift_name"))
            .join(Staff, ShiftAssignment.staff_id == Staff.id)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .where(
                ShiftAssignment.facility_id == facility_id,
                ShiftAssignment.is_deleted == False,  # noqa: E712
            )
        )
        if target_date:
            query = query.where(ShiftAssignment.assignment_date == target_date)
        if staff_id:
            query = query.where(ShiftAssignment.staff_id == staff_id)
        if department_id:
            query = query.where(ShiftAssignment.department_id == department_id)

        query = query.order_by(
            ShiftAssignment.assignment_date.asc(), Shift.start_time.asc()
        )
        result = await self.db.execute(query)
        rows = result.all()

        items: list[ShiftAssignmentResponse] = []
        for sa, first_name, last_name, shift_name in rows:
            item = ShiftAssignmentResponse.model_validate(sa)
            item.staff_name = f"{first_name or ''} {last_name or ''}".strip() or None
            item.shift_name = shift_name
            items.append(item)

        return items

    # ── Leave Requests ───────────────────────────────────────────────────

    async def create_leave_request(
        self,
        data: LeaveRequestCreate,
        staff_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> LeaveRequest:
        """
        Create a leave request.

        @param data: Leave request data
        @param staff_id: Requesting staff UUID
        @param facility_id: Facility UUID
        @returns Created leave request
        """
        leave = LeaveRequest(
            facility_id=facility_id,
            staff_id=staff_id,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            days_requested=data.days_requested,
            reason=data.reason,
            handover_to=data.handover_to,
            handover_notes=data.handover_notes,
            status="pending",
            created_by=staff_id,
            updated_by=staff_id,
        )
        self.db.add(leave)
        await self.db.flush()
        await self.db.refresh(leave)
        return leave

    async def get_leave_requests(
        self,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[LeaveRequestResponse]:
        """
        Get leave requests with staff names.

        @param facility_id: Facility UUID
        @param staff_id: Optional staff filter
        @param status: Optional status filter
        @returns List of leave requests
        """
        query = (
            select(LeaveRequest, Staff.first_name, Staff.last_name)
            .join(Staff, LeaveRequest.staff_id == Staff.id)
            .where(
                LeaveRequest.facility_id == facility_id,
                LeaveRequest.is_deleted == False,  # noqa: E712
            )
        )
        if staff_id:
            query = query.where(LeaveRequest.staff_id == staff_id)
        if status:
            query = query.where(LeaveRequest.status == status)

        query = query.order_by(LeaveRequest.created_at.desc())
        result = await self.db.execute(query)
        rows = result.all()

        items: list[LeaveRequestResponse] = []
        for leave, first_name, last_name in rows:
            item = LeaveRequestResponse.model_validate(leave)
            item.staff_name = f"{first_name or ''} {last_name or ''}".strip() or None
            items.append(item)

        return items

    async def process_leave(
        self,
        leave_id: uuid.UUID,
        data: LeaveApprovalRequest,
        facility_id: uuid.UUID,
        processed_by: uuid.UUID,
    ) -> LeaveRequest | None:
        """
        Approve or reject a leave request. Deducts from balance on approval.

        @param leave_id: Leave request UUID
        @param data: Approval/rejection data
        @param facility_id: Facility UUID
        @param processed_by: Approver staff UUID
        @returns Updated leave request or None
        """
        result = await self.db.execute(
            select(LeaveRequest).where(
                LeaveRequest.id == leave_id,
                LeaveRequest.facility_id == facility_id,
                LeaveRequest.is_deleted == False,  # noqa: E712
            )
        )
        leave = result.scalar_one_or_none()
        if not leave:
            return None

        now = datetime.now(UTC)

        if data.action == "approve":
            leave.status = "approved"
            leave.approved_by = processed_by
            leave.approved_at = now

            # Deduct from leave balance
            profile = await self.get_profile(leave.staff_id, facility_id)
            if profile:
                balance_field = f"{leave.leave_type}_leave_balance"
                if hasattr(profile, balance_field):
                    current = getattr(profile, balance_field)
                    setattr(profile, balance_field, max(0, current - leave.days_requested))
        else:
            leave.status = "rejected"
            leave.rejection_reason = data.rejection_reason

        leave.updated_by = processed_by
        await self.db.flush()
        await self.db.refresh(leave)
        return leave

    # ── Attendance ────────────────────────────────────────────────────────

    async def clock_in(
        self,
        data: AttendanceClockIn,
        staff_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> Attendance:
        """
        Record staff clock-in.

        @param data: Clock-in data
        @param staff_id: Staff UUID
        @param facility_id: Facility UUID
        @returns Attendance record
        """
        now = datetime.now(UTC)
        today = date.today()

        attendance = Attendance(
            facility_id=facility_id,
            staff_id=staff_id,
            shift_id=data.shift_id,
            attendance_date=today,
            clock_in=now,
            status="present",
            notes=data.notes,
            created_by=staff_id,
            updated_by=staff_id,
        )
        self.db.add(attendance)
        await self.db.flush()
        await self.db.refresh(attendance)
        return attendance

    async def clock_out(
        self,
        attendance_id: uuid.UUID,
        data: AttendanceClockOut,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> Attendance | None:
        """
        Record staff clock-out and calculate overtime.

        @param attendance_id: Attendance UUID
        @param data: Clock-out data
        @param facility_id: Facility UUID
        @param staff_id: Staff UUID
        @returns Updated attendance record
        """
        result = await self.db.execute(
            select(Attendance).where(
                Attendance.id == attendance_id,
                Attendance.facility_id == facility_id,
                Attendance.is_deleted == False,  # noqa: E712
            )
        )
        attendance = result.scalar_one_or_none()
        if not attendance:
            return None

        now = datetime.now(UTC)
        attendance.clock_out = now
        if data.notes:
            attendance.notes = data.notes

        # Calculate overtime if shift is assigned
        if attendance.shift_id and attendance.clock_in:
            shift_result = await self.db.execute(
                select(Shift).where(Shift.id == attendance.shift_id)
            )
            shift = shift_result.scalar_one_or_none()
            if shift:
                worked_minutes = int((now - attendance.clock_in).total_seconds() / 60)
                expected_minutes = shift.duration_hours * 60
                if worked_minutes > expected_minutes:
                    attendance.overtime_minutes = worked_minutes - expected_minutes

        attendance.updated_by = staff_id
        await self.db.flush()
        await self.db.refresh(attendance)
        return attendance

    async def get_attendance(
        self,
        facility_id: uuid.UUID,
        target_date: date | None = None,
        staff_id: uuid.UUID | None = None,
    ) -> list[AttendanceResponse]:
        """
        Get attendance records with staff and shift names.

        @param facility_id: Facility UUID
        @param target_date: Optional date filter
        @param staff_id: Optional staff filter
        @returns List of attendance records
        """
        query = (
            select(Attendance, Staff.first_name, Staff.last_name, Shift.name.label("shift_name"))
            .join(Staff, Attendance.staff_id == Staff.id)
            .outerjoin(Shift, Attendance.shift_id == Shift.id)
            .where(
                Attendance.facility_id == facility_id,
                Attendance.is_deleted == False,  # noqa: E712
            )
        )
        if target_date:
            query = query.where(Attendance.attendance_date == target_date)
        if staff_id:
            query = query.where(Attendance.staff_id == staff_id)

        query = query.order_by(Attendance.attendance_date.desc(), Attendance.clock_in.asc())
        result = await self.db.execute(query)
        rows = result.all()

        items: list[AttendanceResponse] = []
        for att, first_name, last_name, shift_name in rows:
            item = AttendanceResponse.model_validate(att)
            item.staff_name = f"{first_name or ''} {last_name or ''}".strip() or None
            item.shift_name = shift_name
            items.append(item)

        return items

    # ── Summary ──────────────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> HRSummary:
        """
        Get HR dashboard summary.

        @param facility_id: Facility UUID
        @returns HR summary stats
        """
        today = date.today()

        total = await self.db.execute(
            select(func.count(Staff.id)).where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        active = await self.db.execute(
            select(func.count(Staff.id)).where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
                Staff.is_active == True,  # noqa: E712
            )
        )
        doctors = await self.db.execute(
            select(func.count(Staff.id)).where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
                Staff.is_active == True,  # noqa: E712
                Staff.role == "doctor",
            )
        )
        nurses = await self.db.execute(
            select(func.count(Staff.id)).where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
                Staff.is_active == True,  # noqa: E712
                Staff.role == "nurse",
            )
        )
        on_duty = await self.db.execute(
            select(func.count(ShiftAssignment.id)).where(
                ShiftAssignment.facility_id == facility_id,
                ShiftAssignment.is_deleted == False,  # noqa: E712
                ShiftAssignment.assignment_date == today,
                ShiftAssignment.status.in_(["assigned", "confirmed"]),
            )
        )
        on_leave = await self.db.execute(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.facility_id == facility_id,
                LeaveRequest.is_deleted == False,  # noqa: E712
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
        )
        pending_leave = await self.db.execute(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.facility_id == facility_id,
                LeaveRequest.is_deleted == False,  # noqa: E712
                LeaveRequest.status == "pending",
            )
        )
        # Contracts expiring within 30 days
        expiring = await self.db.execute(
            select(func.count(StaffProfile.id)).where(
                StaffProfile.facility_id == facility_id,
                StaffProfile.is_deleted == False,  # noqa: E712
                StaffProfile.contract_end_date.isnot(None),
                StaffProfile.contract_end_date <= today + timedelta(days=30),
                StaffProfile.contract_end_date >= today,
            )
        )

        return HRSummary(
            total_staff=total.scalar() or 0,
            active_staff=active.scalar() or 0,
            doctors=doctors.scalar() or 0,
            nurses=nurses.scalar() or 0,
            on_duty_today=on_duty.scalar() or 0,
            on_leave_today=on_leave.scalar() or 0,
            pending_leave_requests=pending_leave.scalar() or 0,
            expiring_contracts=expiring.scalar() or 0,
        )
