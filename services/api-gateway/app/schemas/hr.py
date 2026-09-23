import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

# ── Staff Profile ───────────────────────────────────────────────────────────


class StaffProfileCreate(BaseModel):
    """Schema for creating/updating a staff profile."""

    staff_id: uuid.UUID
    date_of_birth: date | None = None
    gender: str | None = Field(None, pattern=r"^(male|female|other)$")
    national_id: str | None = Field(None, max_length=20)
    kra_pin: str | None = Field(None, max_length=20)
    nhif_number: str | None = Field(None, max_length=20)
    nssf_number: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=500)
    county: str | None = Field(None, max_length=50)
    sub_county: str | None = Field(None, max_length=50)
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_phone: str | None = Field(None, max_length=20)
    emergency_contact_relationship: str | None = Field(None, max_length=50)
    employment_type: str = Field(
        default="permanent",
        pattern=r"^(permanent|contract|casual|intern|locum)$",
    )
    employment_date: date | None = None
    contract_end_date: date | None = None
    probation_end_date: date | None = None
    basic_salary: int | None = Field(None, ge=0)
    allowances: dict | None = None
    qualifications: list[dict] | None = None
    certifications: list[dict] | None = None
    notes: str | None = Field(None, max_length=2000)


class StaffProfileResponse(BaseModel):
    """Schema for staff profile API responses."""

    id: uuid.UUID
    staff_id: uuid.UUID
    date_of_birth: date | None
    gender: str | None
    national_id: str | None
    kra_pin: str | None
    nhif_number: str | None
    nssf_number: str | None
    address: str | None
    county: str | None
    sub_county: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_relationship: str | None
    employment_type: str
    employment_date: date | None
    contract_end_date: date | None
    probation_end_date: date | None
    basic_salary: int | None
    allowances: dict | None
    qualifications: list[dict] | None
    certifications: list[dict] | None
    annual_leave_balance: int
    sick_leave_balance: int
    maternity_leave_balance: int
    paternity_leave_balance: int
    photo_url: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StaffDirectoryItem(BaseModel):
    """Staff member in directory listing with key details."""

    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    title: str | None
    role: str
    specialization: str | None
    department_name: str | None = None
    phone: str | None
    email: str
    is_active: bool
    license_number: str | None

    model_config = {"from_attributes": True}


class StaffDirectoryResponse(BaseModel):
    """Paginated staff directory response."""

    items: list[StaffDirectoryItem]
    total: int


# ── Shifts ──────────────────────────────────────────────────────────────────


class ShiftCreate(BaseModel):
    """Schema for creating a shift definition."""

    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    start_time: time
    end_time: time
    duration_hours: int = Field(..., ge=1, le=24)
    is_night_shift: bool = False
    department_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)


class ShiftResponse(BaseModel):
    """Schema for shift API responses."""

    id: uuid.UUID
    code: str
    name: str
    start_time: time
    end_time: time
    duration_hours: int
    is_night_shift: bool
    department_id: uuid.UUID | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShiftAssignmentCreate(BaseModel):
    """Schema for assigning a staff member to a shift."""

    staff_id: uuid.UUID
    shift_id: uuid.UUID
    department_id: uuid.UUID | None = None
    assignment_date: date
    notes: str | None = Field(None, max_length=500)


class ShiftAssignmentResponse(BaseModel):
    """Schema for shift assignment API responses."""

    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str | None = None
    shift_id: uuid.UUID
    shift_name: str | None = None
    department_id: uuid.UUID | None
    assignment_date: date
    status: str
    swapped_with_id: uuid.UUID | None
    swap_reason: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShiftAssignmentListResponse(BaseModel):
    """Paginated shift assignment list."""

    items: list[ShiftAssignmentResponse]
    total: int


# ── Leave ───────────────────────────────────────────────────────────────────


class LeaveRequestCreate(BaseModel):
    """Schema for creating a leave request."""

    leave_type: str = Field(
        ...,
        pattern=r"^(annual|sick|maternity|paternity|compassionate|study|unpaid)$",
    )
    start_date: date
    end_date: date
    days_requested: int = Field(..., ge=1, le=365)
    reason: str | None = Field(None, max_length=1000)
    handover_to: uuid.UUID | None = None
    handover_notes: str | None = Field(None, max_length=1000)


class LeaveApprovalRequest(BaseModel):
    """Schema for approving or rejecting a leave request."""

    action: str = Field(..., pattern=r"^(approve|reject)$")
    rejection_reason: str | None = Field(None, max_length=500)


class LeaveRequestResponse(BaseModel):
    """Schema for leave request API responses."""

    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str | None = None
    leave_type: str
    start_date: date
    end_date: date
    days_requested: int
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    handover_to: uuid.UUID | None
    handover_notes: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveRequestListResponse(BaseModel):
    """Paginated leave request list."""

    items: list[LeaveRequestResponse]
    total: int


# ── Attendance ──────────────────────────────────────────────────────────────


class AttendanceClockIn(BaseModel):
    """Schema for clocking in."""

    shift_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)


class AttendanceClockOut(BaseModel):
    """Schema for clocking out."""

    notes: str | None = Field(None, max_length=500)


class AttendanceResponse(BaseModel):
    """Schema for attendance API responses."""

    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: str | None = None
    shift_id: uuid.UUID | None
    shift_name: str | None = None
    attendance_date: date
    clock_in: datetime | None
    clock_out: datetime | None
    status: str
    overtime_minutes: int
    notes: str | None

    model_config = {"from_attributes": True}


class AttendanceListResponse(BaseModel):
    """Paginated attendance list."""

    items: list[AttendanceResponse]
    total: int


# ── Summary ─────────────────────────────────────────────────────────────────


class HRSummary(BaseModel):
    """HR module dashboard summary."""

    total_staff: int = 0
    active_staff: int = 0
    doctors: int = 0
    nurses: int = 0
    on_duty_today: int = 0
    on_leave_today: int = 0
    pending_leave_requests: int = 0
    expiring_contracts: int = 0
