"""Pydantic schemas for the HR/Payroll module."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ── Employees ────────────────────────────────────────────────────────────────


class EmployeeCreate(BaseModel):
    """Create a payroll-grade employee record."""

    staff_id: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=200)
    id_number: str | None = Field(None, max_length=20)
    kra_pin: str | None = Field(None, max_length=20)
    nssf_number: str | None = Field(None, max_length=20)
    shif_number: str | None = Field(None, max_length=20)
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(None, max_length=200)
    employment_type: str = Field(
        default="permanent",
        pattern=r"^(permanent|contract|casual|intern)$",
    )
    hire_date: date
    termination_date: date | None = None
    is_active: bool = True
    bank_name: str | None = Field(None, max_length=100)
    bank_branch: str | None = Field(None, max_length=100)
    bank_account: str | None = Field(None, max_length=200)
    disability_exemption: bool = False
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)
    # Opening pay for the employee. Payroll prices every run from
    # employee_salaries, so these become the first salary record on create -
    # without it a newly-registered employee is skipped by every run.
    basic_salary: Decimal | None = Field(None, ge=0)
    house_allowance: Decimal = Field(Decimal("0"), ge=0)
    transport_allowance: Decimal = Field(Decimal("0"), ge=0)
    other_allowances: Decimal = Field(Decimal("0"), ge=0)
    #: Clinical role HR assigns to this employee, from the catalogue HR may
    #: pick from. When set it replaces the role the job title would otherwise
    #: have been guessed from - the access is HR's decision, not a side effect
    #: of how the title happens to be worded.
    role: str | None = Field(None, max_length=64)
    #: Initial sign-in password. Supplying one creates this employee's Aifya
    #: login (AUTH_PROVIDER=internal) at the same time as the record; leaving
    #: it blank registers the person without a login until HR sets one.
    login_password: str | None = Field(None, min_length=8, max_length=128)


class EmployeeUpdate(BaseModel):
    """Patch an employee. All fields optional."""

    full_name: str | None = Field(None, max_length=200)
    id_number: str | None = Field(None, max_length=20)
    kra_pin: str | None = Field(None, max_length=20)
    nssf_number: str | None = Field(None, max_length=20)
    shif_number: str | None = Field(None, max_length=20)
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(None, max_length=200)
    employment_type: str | None = Field(
        None, pattern=r"^(permanent|contract|casual|intern)$"
    )
    termination_date: date | None = None
    is_active: bool | None = None
    bank_name: str | None = Field(None, max_length=100)
    bank_branch: str | None = Field(None, max_length=100)
    bank_account: str | None = Field(None, max_length=200)
    disability_exemption: bool | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)


class EmployeeResponse(BaseModel):
    """Employee API response (full record, returned on detail endpoints).

    Sensitive fields (kra_pin, nssf_number, shif_number, bank_*) are exposed
    here. The list endpoint returns the lighter EmployeeListItem instead.
    bank_account is NEVER exposed in any response (it is encrypted at rest;
    the service layer must decrypt explicitly when needed for payslip rendering).
    """

    id: uuid.UUID
    staff_id: str
    full_name: str
    id_number: str | None
    kra_pin: str | None
    nssf_number: str | None
    shif_number: str | None
    department_id: uuid.UUID | None
    department_name: str | None = None
    job_title: str | None
    employment_type: str
    hire_date: date
    termination_date: date | None
    is_active: bool
    bank_name: str | None
    bank_branch: str | None
    disability_exemption: bool
    phone: str | None
    email: str | None
    notes: str | None
    created_at: datetime
    #: Whether this employee can sign in. Their access is the staff role, which
    #: lives in the staff directory; this only says whether credentials exist.
    has_login: bool = False

    model_config = ConfigDict(from_attributes=True)


class EmployeeListItem(BaseModel):
    """Light-weight employee row for list endpoints — hides PII / statutory IDs."""

    id: uuid.UUID
    staff_id: str
    full_name: str
    department_id: uuid.UUID | None
    department_name: str | None = None
    job_title: str | None
    employment_type: str
    hire_date: date
    is_active: bool
    phone: str | None
    email: str | None

    model_config = ConfigDict(from_attributes=True)


class EmployeeListResponse(BaseModel):
    """Paged employee list."""

    items: list[EmployeeListItem]
    total: int


# ── Salary structure ────────────────────────────────────────────────────────


class SalaryStructureCreate(BaseModel):
    """Create a new salary effective record for an employee."""

    basic_salary: Decimal = Field(..., ge=0)
    house_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    transport_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    other_allowances: dict[str, Decimal] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(None, max_length=500)


class SalaryStructureResponse(BaseModel):
    """Salary structure API response."""

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    basic_salary: Decimal
    house_allowance: Decimal
    transport_allowance: Decimal
    other_allowances: dict
    effective_from: date
    effective_to: date | None
    approved_by: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Payroll runs ────────────────────────────────────────────────────────────


class PayrollRunCreate(BaseModel):
    """Trigger calculation of a draft payroll run."""

    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    notes: str | None = Field(None, max_length=500)


class PayrollRunApprove(BaseModel):
    """Approve a draft payroll run."""

    notes: str | None = Field(None, max_length=500)


class PayrollLineItemResponse(BaseModel):
    """Per-employee payslip line response."""

    id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    basic_salary: Decimal
    house_allowance: Decimal
    transport_allowance: Decimal
    other_allowances: dict
    gross_salary: Decimal
    nssf_employee: Decimal
    shif: Decimal
    housing_levy: Decimal
    taxable_pay: Decimal
    paye_gross: Decimal
    personal_relief: Decimal
    insurance_relief: Decimal
    paye: Decimal
    other_deductions: dict
    total_deductions: Decimal
    net_salary: Decimal
    employer_nssf: Decimal
    employer_housing_levy: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class PayrollRunResponse(BaseModel):
    """Payroll run summary."""

    id: uuid.UUID
    period_id: uuid.UUID | None
    month: int
    year: int
    status: str
    run_date: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    gl_transaction_id: uuid.UUID | None
    gl_posting_error: str | None = None
    gl_attempted_at: datetime | None = None
    skipped_employees: list[dict] = Field(default_factory=list)
    total_gross: Decimal
    total_paye: Decimal
    total_nssf: Decimal
    total_shif: Decimal
    total_hl: Decimal
    total_net: Decimal
    total_employer_nssf: Decimal
    total_employer_hl: Decimal
    notes: str | None
    created_at: datetime
    line_items: list[PayrollLineItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PayrollRunListResponse(BaseModel):
    """Paged payroll run list."""

    items: list[PayrollRunResponse]
    total: int


# ── Statutory rates ─────────────────────────────────────────────────────────


class StatutoryRateCreate(BaseModel):
    """Create a statutory rate."""

    name: str = Field(..., max_length=100)
    category: str = Field(
        ..., pattern=r"^(paye|nssf|shif|housing_levy|relief|insurance)$"
    )
    rate: Decimal | None = None
    fixed_amount: Decimal | None = None
    fixed_cap: Decimal | None = None
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(None, max_length=500)


class StatutoryRateResponse(BaseModel):
    """Statutory rate API response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    name: str
    category: str
    rate: Decimal | None
    fixed_amount: Decimal | None
    fixed_cap: Decimal | None
    effective_from: date
    effective_to: date | None
    approved_by: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeDeductionCreate(BaseModel):
    """Record a recurring or one-time deduction against an employee.

    Insurance premiums are ordinary deductions whose name matches a
    configured ``insurance`` statutory rate, which is what makes them
    eligible for insurance relief.
    """

    employee_id: uuid.UUID
    name: str = Field(..., max_length=100)
    amount: Decimal = Field(..., gt=0)
    frequency: str = Field(default="monthly", pattern=r"^(monthly|one_time)$")
    start_date: date
    end_date: date | None = None
    is_active: bool = True
    notes: str | None = Field(None, max_length=500)


class EmployeeDeductionResponse(BaseModel):
    """Employee deduction API response."""

    id: uuid.UUID
    employee_id: uuid.UUID
    name: str
    amount: Decimal
    frequency: str
    start_date: date
    end_date: date | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsuranceProductResponse(BaseModel):
    """An insurance product that can be deducted from staff pay."""

    id: uuid.UUID
    name: str
    rate: Decimal | None
    fixed_amount: Decimal | None
    effective_from: date
    effective_to: date | None


class InsuranceCoverageItem(BaseModel):
    """One employee's current insurance coverage."""

    employee_id: uuid.UUID
    employee_name: str
    products: list[str]
    monthly_premium: Decimal


class InsuranceUsagePoint(BaseModel):
    """Premium and relief the payroll produced for one period."""

    month: int
    year: int
    label: str
    run_status: str | None = None
    covered_employees: int
    premium: Decimal
    relief: Decimal


class InsuranceUtilisationResponse(BaseModel):
    """Insurance configuration plus how it has been used in payroll."""

    year: int
    relief_rate: Decimal
    relief_cap: Decimal
    products: list[InsuranceProductResponse]
    coverage: list[InsuranceCoverageItem]
    covered_employees: int
    monthly_premium: Decimal
    periods: list[InsuranceUsagePoint]
    total_premium: Decimal
    total_relief: Decimal


class PAYEBandResponse(BaseModel):
    """PAYE band response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    lower_limit: Decimal
    upper_limit: Decimal | None
    rate: Decimal
    effective_from: date
    effective_to: date | None

    model_config = ConfigDict(from_attributes=True)


class NSSFTierResponse(BaseModel):
    """NSSF tier response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    tier: str
    lower_limit: Decimal
    upper_limit: Decimal
    employee_rate: Decimal
    employer_rate: Decimal
    effective_from: date
    effective_to: date | None

    model_config = ConfigDict(from_attributes=True)


# ── Leave ───────────────────────────────────────────────────────────────────


class LeaveTypeCreate(BaseModel):
    """Create a facility leave type (e.g. typed on the fly from the Leave tab)."""

    name: str = Field(..., min_length=1, max_length=50)
    days_entitlement: int = Field(21, ge=0, le=365)
    paid: bool = True
    partial_pay: bool = False
    carries_over: bool = False
    max_carryover: int | None = Field(None, ge=0, le=365)
    notes: str | None = Field(None, max_length=500)


class LeaveTypeResponse(BaseModel):
    """Leave type response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    name: str
    days_entitlement: int
    paid: bool
    partial_pay: bool
    carries_over: bool
    max_carryover: int | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestCreate(BaseModel):
    """Submit a payroll-aware leave request."""

    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days_requested: int = Field(..., ge=1, le=365)
    reason: str | None = Field(None, max_length=1000)


class LeaveRequestResponse(BaseModel):
    """Payroll leave request response."""

    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days_requested: int
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    payroll_deduction: Decimal
    payroll_period_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestListItem(BaseModel):
    """Leave request list row with joined employee and leave type names."""

    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    leave_type_id: uuid.UUID
    leave_type_name: str | None = None
    start_date: date
    end_date: date
    days_requested: int
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime


class LeaveRequestListResponse(BaseModel):
    """Paginated-style leave request listing."""

    items: list[LeaveRequestListItem]
    total: int


class LeaveApprovalRequest(BaseModel):
    """Approve/reject a leave request."""

    action: str = Field(..., pattern=r"^(approve|reject)$")
    rejection_reason: str | None = Field(None, max_length=500)


class LeaveBalanceBucket(BaseModel):
    """One leave bucket: entitlement, days already approved, and the rest."""

    key: str
    entitled_days: int
    taken_days: int
    remaining_days: int


class LeaveBalanceResponse(BaseModel):
    """A staff member's own leave balance for the self-service My Leave panel."""

    employee_id: uuid.UUID
    employee_name: str
    buckets: list[LeaveBalanceBucket]


# ── Reports ─────────────────────────────────────────────────────────────────


class PayslipResponse(BaseModel):
    """Computed payslip view (line item + employee + facility)."""

    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    staff_id: str
    kra_pin: str | None
    nssf_number: str | None
    shif_number: str | None
    bank_name: str | None
    bank_branch: str | None
    month: int
    year: int
    line: PayrollLineItemResponse


class DepartmentCreate(BaseModel):
    """Create a hospital department (payroll cost centre)."""

    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    department_type: str = Field(
        default="clinical", pattern=r"^(clinical|support|admin)$"
    )
    parent_id: uuid.UUID | None = None
    head_of_department_id: uuid.UUID | None = None
    is_active: bool = True


class DepartmentResponse(BaseModel):
    """Department API response."""

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    department_type: str
    parent_id: uuid.UUID | None
    head_of_department_id: uuid.UUID | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class P9Row(BaseModel):
    """One month of a P9 annual return, in KRA P9 column order."""

    month: int
    basic_salary: Decimal
    benefits: Decimal
    gross_pay: Decimal
    defined_contribution_retirement: Decimal
    affordable_housing_levy: Decimal
    shif_contribution: Decimal
    taxable_pay: Decimal
    paye: Decimal
    personal_relief: Decimal
    insurance_relief: Decimal
    paye_payable: Decimal


class P9Response(BaseModel):
    """Annual P9 PAYE return for a single employee."""

    employee_id: uuid.UUID
    employee_name: str
    kra_pin: str | None
    year: int
    rows: list[P9Row]
    totals: P9Row


class PAYEScheduleRow(BaseModel):
    """One employee line on the monthly P10 PAYE schedule."""

    employee_id: uuid.UUID
    employee_name: str
    kra_pin: str | None
    taxable_pay: Decimal
    paye: Decimal


class PAYEScheduleResponse(BaseModel):
    """Monthly KRA P10 PAYE schedule."""

    month: int
    year: int
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    rows: list[PAYEScheduleRow]
    total_taxable: Decimal
    total_paye: Decimal


class NSSFScheduleRow(BaseModel):
    """One employee line on the monthly NSSF schedule."""

    employee_id: uuid.UUID
    employee_name: str
    nssf_number: str | None
    pensionable_pay: Decimal
    employee_contribution: Decimal
    employer_contribution: Decimal
    total: Decimal


class NSSFScheduleResponse(BaseModel):
    """Monthly NSSF schedule."""

    month: int
    year: int
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    rows: list[NSSFScheduleRow]
    total_employee: Decimal
    total_employer: Decimal
    total: Decimal


class SHIFScheduleRow(BaseModel):
    """One employee line on the monthly SHIF schedule."""

    employee_id: uuid.UUID
    employee_name: str
    shif_number: str | None
    gross_salary: Decimal
    contribution: Decimal


class SHIFScheduleResponse(BaseModel):
    """Monthly SHIF schedule."""

    month: int
    year: int
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    rows: list[SHIFScheduleRow]
    total: Decimal


class HousingLevyScheduleRow(BaseModel):
    """One employee line on the monthly Affordable Housing Levy schedule."""

    employee_id: uuid.UUID
    employee_name: str
    kra_pin: str | None
    gross_salary: Decimal
    employee_contribution: Decimal
    employer_contribution: Decimal
    total: Decimal


class HousingLevyScheduleResponse(BaseModel):
    """Monthly Affordable Housing Levy schedule (1.5% employee + employer)."""

    month: int
    year: int
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    rows: list[HousingLevyScheduleRow]
    total_employee: Decimal
    total_employer: Decimal
    total: Decimal


class HeadcountBucket(BaseModel):
    """One bucket of the headcount report."""

    label: str
    count: int


class HeadcountResponse(BaseModel):
    """Headcount as of a date, by department and employment type."""

    as_of: date
    total: int
    by_department: list[HeadcountBucket]
    by_employment_type: list[HeadcountBucket]


class CostTrendPoint(BaseModel):
    """One month of the payroll cost trend."""

    month: int
    year: int
    label: str
    gross: Decimal
    net: Decimal
    paye: Decimal
    statutory: Decimal


class CostTrendResponse(BaseModel):
    """Payroll cost trend for a year."""

    year: int
    points: list[CostTrendPoint]


class TurnoverPoint(BaseModel):
    """Joiners and leavers for one month."""

    period: str
    joiners: int
    leavers: int


class TurnoverResponse(BaseModel):
    """Hires, terminations and ending headcount for a period."""

    period_start: date
    period_end: date
    hires: int
    terminations: int
    ending_headcount: int
    points: list[TurnoverPoint]


class DepartmentTotals(BaseModel):
    """Per-department payroll totals."""

    department_id: uuid.UUID | None
    department_name: str | None
    headcount: int
    total_gross: Decimal
    total_net: Decimal
    total_paye: Decimal


class PayrollSummaryResponse(BaseModel):
    """Monthly payroll summary, totals per department."""

    month: int
    year: int
    departments: list[DepartmentTotals]
    grand_total_gross: Decimal
    grand_total_net: Decimal
    grand_total_paye: Decimal
    grand_total_nssf: Decimal
    grand_total_shif: Decimal
    grand_total_hl: Decimal
    headcount: int
