"""HR/Payroll module REST router.

All endpoints are tenant-scoped via `current_user.facility_id`. The
service layer handles all business logic — no business logic in this
router.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.models.payroll import (
    Employee,
    EmployeeSalary,
    NSSFTier,
    PAYEBand,
    PayrollLineItem,
    PayrollRun,
    StatutoryRate,
)
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest
from app.models.staff import Department
from app.schemas.payroll import (
    CostTrendResponse,
    DepartmentCreate,
    DepartmentResponse,
    EmployeeCreate,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
    HeadcountResponse,
    LeaveApprovalRequest,
    LeaveRequestCreate,
    LeaveRequestListItem,
    LeaveRequestListResponse,
    LeaveRequestResponse,
    LeaveTypeCreate,
    LeaveTypeResponse,
    NSSFScheduleResponse,
    NSSFTierResponse,
    P9Response,
    P9Row,
    PAYEBandResponse,
    PAYEScheduleResponse,
    PayrollLineItemResponse,
    PayrollRunCreate,
    PayrollRunListResponse,
    PayrollRunResponse,
    SalaryStructureCreate,
    SalaryStructureResponse,
    SHIFScheduleResponse,
    StatutoryRateCreate,
    StatutoryRateResponse,
    TurnoverResponse,
)
from app.services.payroll.employee_staff_sync import sync_employee_to_staff
from app.services.payroll.engine import run_monthly_payroll
from app.services.payroll.gl_integration import post_payroll_to_gl
from app.services.payroll.leave import (
    approve_leave_request,
    reject_leave_request,
    resolve_payroll_employee,
    submit_leave_request,
)
from app.services.payroll.payslip import (
    PayslipNotAvailableError,
    generate_payslip,
)
from app.services.payroll.reports import (
    generate_p9,
    get_employee_turnover,
    get_headcount_report,
    get_leave_utilisation,
    get_monthly_payroll_summary,
    get_nssf_schedule,
    get_paye_schedule,
    get_payroll_cost_trend,
    get_shif_schedule,
)

router = APIRouter(dependencies=[Depends(require_module("hr"))])


# ── Employees ──────────────────────────────────────────────────────────────


# ── Departments ────────────────────────────────────────────────────────────


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DepartmentResponse]:
    """List the facility's departments.

    Departments are the cost centres the payroll reports group by, so this is
    what the employee form picks from.

    @param include_inactive: Include deactivated departments
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Departments ordered by name
    """
    stmt = select(Department).where(
        Department.facility_id == current_user.facility_id,
        Department.is_deleted.is_(False),
    )
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    rows = (
        await db.execute(stmt.order_by(Department.name.asc()))
    ).scalars().all()
    return [DepartmentResponse.model_validate(row) for row in rows]


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin")
    ),
) -> DepartmentResponse:
    """Create a department.

    The (facility_id, code) index is unique across soft-deleted rows too, so a
    previously deleted department with the same code is revived instead of
    colliding.

    @param data: Department details
    @param db: Database session
    @param current_user: Authenticated HR administrator
    @returns The created or revived department
    """
    code = data.code.strip().upper()
    existing = (
        await db.execute(
            select(Department).where(
                Department.facility_id == current_user.facility_id,
                func.upper(Department.code) == code,
            )
        )
    ).scalars().first()
    if existing is not None and not existing.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A department with code {code} already exists",
        )

    if existing is not None:
        existing.is_deleted = False
        existing.deleted_at = None
        existing.is_active = data.is_active
        existing.name = data.name.strip()
        existing.code = code
        existing.description = data.description
        existing.department_type = data.department_type
        existing.parent_id = data.parent_id
        existing.head_of_department_id = data.head_of_department_id
        existing.updated_by = current_user.user_id
        department = existing
    else:
        department = Department(
            facility_id=current_user.facility_id,
            code=code,
            name=data.name.strip(),
            description=data.description,
            department_type=data.department_type,
            parent_id=data.parent_id,
            head_of_department_id=data.head_of_department_id,
            is_active=data.is_active,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        db.add(department)

    await db.flush()
    await db.refresh(department)
    return DepartmentResponse.model_validate(department)


# ── Employees ──────────────────────────────────────────────────────────────


async def _department_name(
    db: AsyncSession, facility_id: uuid.UUID, department_id: uuid.UUID | None
) -> str | None:
    """Resolve a department name, or None when there is no department.

    @param db: Database session
    @param facility_id: Facility UUID
    @param department_id: Department UUID, or None
    @returns Department name or None
    """
    if department_id is None:
        return None
    return (
        await db.execute(
            select(Department.name).where(
                Department.id == department_id,
                Department.facility_id == facility_id,
                Department.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()


@router.get("/employees", response_model=EmployeeListResponse)
async def list_employees(
    department_id: uuid.UUID | None = Query(None),
    employment_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    active_only: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmployeeListResponse:
    """List employees in the current facility.

    `is_active` is the filter the UI sends. `active_only` is kept for callers
    still sending the older flag. When neither is supplied every employee in
    the facility is returned, so the "All" filter is a true "all".

    @param department_id: Optional department filter
    @param employment_type: Optional employment type filter
    @param is_active: Filter on the active flag
    @param active_only: Legacy alias for is_active
    @param search: Match against full_name / staff_id (ILIKE)
    @param page: 1-based page number
    @param page_size: Page size, or None to return the whole list
    @returns Matching employees with their department name
    """
    stmt = (
        select(Employee, Department.name.label("department_name"))
        .outerjoin(
            Department,
            and_(
                Department.id == Employee.department_id,
                Department.is_deleted.is_(False),
            ),
        )
        .where(
            Employee.facility_id == current_user.facility_id,
            Employee.is_deleted.is_(False),
        )
    )
    active_filter = is_active if is_active is not None else active_only
    if active_filter is not None:
        stmt = stmt.where(Employee.is_active.is_(active_filter))
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if employment_type:
        stmt = stmt.where(Employee.employment_type == employment_type)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.staff_id.ilike(pattern),
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0

    stmt = stmt.order_by(Employee.full_name.asc())
    if page_size is not None:
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(stmt)).all()
    items = [
        EmployeeListItem.model_validate(employee).model_copy(
            update={"department_name": department_name}
        )
        for employee, department_name in rows
    ]
    return EmployeeListResponse(items=items, total=int(total))


@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin")
    ),
) -> EmployeeResponse:
    """Create a payroll-grade employee record."""
    emp = Employee(
        facility_id=current_user.facility_id,
        **data.model_dump(),
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(emp)
    await db.flush()
    await sync_employee_to_staff(
        db,
        facility_id=current_user.facility_id,
        employee=emp,
        actor_id=current_user.user_id,
    )
    await db.refresh(emp)
    response = EmployeeResponse.model_validate(emp)
    return response.model_copy(
        update={
            "department_name": await _department_name(
                db, current_user.facility_id, emp.department_id
            )
        }
    )


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmployeeResponse:
    """Fetch a single employee."""
    emp = (
        await db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.facility_id == current_user.facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )
    response = EmployeeResponse.model_validate(emp)
    return response.model_copy(
        update={
            "department_name": await _department_name(
                db, current_user.facility_id, emp.department_id
            )
        }
    )


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin")
    ),
) -> EmployeeResponse:
    """Patch an employee record."""
    emp = (
        await db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.facility_id == current_user.facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    emp.updated_by = current_user.user_id
    await db.flush()
    await sync_employee_to_staff(
        db,
        facility_id=current_user.facility_id,
        employee=emp,
        actor_id=current_user.user_id,
    )
    await db.refresh(emp)
    response = EmployeeResponse.model_validate(emp)
    return response.model_copy(
        update={
            "department_name": await _department_name(
                db, current_user.facility_id, emp.department_id
            )
        }
    )


@router.post(
    "/employees/{employee_id}/salaries",
    response_model=SalaryStructureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_salary(
    employee_id: uuid.UUID,
    data: SalaryStructureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin")
    ),
) -> SalaryStructureResponse:
    """Add a salary effective record (HR admin only). Closes the previous
    open record by setting its `effective_to` to (effective_from - 1)."""
    emp = (
        await db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.facility_id == current_user.facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )

    # Close any currently-open record
    open_records = (
        await db.execute(
            select(EmployeeSalary).where(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.facility_id == current_user.facility_id,
                EmployeeSalary.is_deleted.is_(False),
                EmployeeSalary.effective_to.is_(None),
            )
        )
    ).scalars().all()
    for sal in open_records:
        sal.effective_to = date.fromordinal(data.effective_from.toordinal() - 1)

    salary = EmployeeSalary(
        facility_id=current_user.facility_id,
        employee_id=employee_id,
        basic_salary=data.basic_salary,
        house_allowance=data.house_allowance,
        transport_allowance=data.transport_allowance,
        other_allowances={k: str(v) for k, v in data.other_allowances.items()},
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        approved_by=current_user.user_id,
        notes=data.notes,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(salary)
    await db.flush()
    await db.refresh(salary)
    return SalaryStructureResponse.model_validate(salary)


@router.get(
    "/employees/{employee_id}/salaries",
    response_model=list[SalaryStructureResponse],
)
async def list_employee_salaries(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SalaryStructureResponse]:
    """List an employee's salary records, most recent effective date first."""
    records = (
        await db.execute(
            select(EmployeeSalary)
            .where(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.facility_id == current_user.facility_id,
                EmployeeSalary.is_deleted.is_(False),
            )
            .order_by(EmployeeSalary.effective_from.desc())
        )
    ).scalars().all()
    return [SalaryStructureResponse.model_validate(rec) for rec in records]


# ── Payroll runs ───────────────────────────────────────────────────────────


@router.post(
    "/runs",
    response_model=PayrollRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payroll_run(
    data: PayrollRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_officer", "hr_admin")
    ),
    x_idempotency_key: str | None = Header(None),
) -> PayrollRunResponse:
    """Calculate a draft payroll run (HR officer).

    @param x_idempotency_key: Optional idempotency key header (logged for audit;
        engine rejects duplicate active runs by month/year naturally).
    """
    _ = x_idempotency_key  # informational; dedup enforced by month/year uniqueness
    try:
        run = await run_monthly_payroll(
            db=db,
            facility_id=current_user.facility_id,
            month=data.month,
            year=data.year,
            user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return await _build_run_response(db, current_user.facility_id, run)


@router.get("/runs", response_model=PayrollRunListResponse)
async def list_payroll_runs(
    year: int | None = Query(None),
    run_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PayrollRunListResponse:
    """List payroll runs."""
    stmt = select(PayrollRun).where(
        PayrollRun.facility_id == current_user.facility_id,
        PayrollRun.is_deleted.is_(False),
    )
    if year is not None:
        stmt = stmt.where(PayrollRun.year == year)
    if run_status is not None:
        stmt = stmt.where(PayrollRun.status == run_status)
    stmt = stmt.order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    rows = (await db.execute(stmt)).scalars().all()
    items = [PayrollRunResponse.model_validate(r) for r in rows]
    return PayrollRunListResponse(items=items, total=len(items))


@router.get("/runs/{run_id}", response_model=PayrollRunResponse)
async def get_payroll_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PayrollRunResponse:
    """Get a payroll run with all line items."""
    run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.id == run_id,
                PayrollRun.facility_id == current_user.facility_id,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        )
    return await _build_run_response(db, current_user.facility_id, run)


@router.post("/runs/{run_id}/approve", response_model=PayrollRunResponse)
async def approve_payroll_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin")
    ),
) -> PayrollRunResponse:
    """Approve a draft run; triggers GL posting (gracefully degrades)."""
    run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.id == run_id,
                PayrollRun.facility_id == current_user.facility_id,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        )
    if run.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve run in status '{run.status}'",
        )

    run.status = "approved"
    run.approved_by = current_user.user_id
    run.approved_at = datetime.now(UTC)
    run.updated_by = current_user.user_id
    await db.flush()

    # Post to GL (best-effort)
    txn_id = await post_payroll_to_gl(
        db=db, run=run, user_id=current_user.user_id
    )
    if txn_id is not None:
        run.gl_transaction_id = txn_id
        run.status = "posted"
        await db.flush()

    await db.refresh(run)
    return await _build_run_response(db, current_user.facility_id, run)


@router.post("/runs/{run_id}/recalculate", response_model=PayrollRunResponse)
async def recalculate_payroll_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_officer", "hr_admin")
    ),
) -> PayrollRunResponse:
    """Re-run the payroll engine for a draft run's period.

    The previous draft run and its line items are soft-deleted, then the engine
    recalculates the period from the current salary and statutory data. Only
    draft runs can be recalculated; approved/posted runs are immutable.
    """
    run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.id == run_id,
                PayrollRun.facility_id == current_user.facility_id,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        )
    if run.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot recalculate run in status '{run.status}'",
        )

    month, year = run.month, run.year

    # Retire the previous draft (soft-delete) so the replaced line items are
    # never double-counted and the period is free for a fresh calculation.
    previous_items = (
        await db.execute(
            select(PayrollLineItem).where(
                PayrollLineItem.payroll_run_id == run_id,
                PayrollLineItem.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    for item in previous_items:
        item.is_deleted = True
        item.updated_by = current_user.user_id
    run.is_deleted = True
    run.updated_by = current_user.user_id
    await db.flush()

    try:
        recalculated = await run_monthly_payroll(
            db=db,
            facility_id=current_user.facility_id,
            month=month,
            year=year,
            user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return await _build_run_response(
        db, current_user.facility_id, recalculated
    )


@router.get("/runs/{run_id}/payslip/{employee_id}")
async def get_run_payslip(
    run_id: uuid.UUID,
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Render and download an individual payslip PDF.

    Access control: HR/finance admins can download any payslip; otherwise the
    requester may only download their own payslip (matched via the employee
    record's email == JWT email). Other users get 403.
    """
    privileged_roles = {"admin", "facility_admin", "hr_admin", "finance_admin"}
    is_privileged = bool(privileged_roles.intersection(current_user.roles))

    if not is_privileged:
        emp_row = (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == current_user.facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        ).scalars().first()
        owns_record = (
            emp_row is not None
            and bool(current_user.email)
            and (emp_row.email or "").lower() == (current_user.email or "").lower()
        )
        if not owns_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this payslip",
            )

    try:
        pdf_bytes = await generate_payslip(
            db=db,
            facility_id=current_user.facility_id,
            payroll_run_id=run_id,
            employee_id=employee_id,
        )
    except PayslipNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    media = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/plain"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type=media,
        headers={
            "Content-Disposition": (
                f'attachment; filename="payslip-{run_id}-{employee_id}.pdf"'
            )
        },
    )


@router.get("/employees/{employee_id}/payslips")
async def list_employee_payslips(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Self-service: list approved payslips for one employee.

    Access control: HR/finance admins can list any employee's payslips;
    otherwise the requester may only list their own.
    """
    privileged_roles = {"admin", "facility_admin", "hr_admin", "finance_admin"}
    is_privileged = bool(privileged_roles.intersection(current_user.roles))
    if not is_privileged:
        emp_row = (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == current_user.facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        ).scalars().first()
        owns_record = (
            emp_row is not None
            and bool(current_user.email)
            and (emp_row.email or "").lower() == (current_user.email or "").lower()
        )
        if not owns_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to list these payslips",
            )

    rows = (
        await db.execute(
            select(
                PayrollRun.id,
                PayrollRun.month,
                PayrollRun.year,
                PayrollRun.status,
                PayrollLineItem.gross_salary,
                PayrollLineItem.net_salary,
            )
            .join(PayrollRun, PayrollRun.id == PayrollLineItem.payroll_run_id)
            .where(
                PayrollLineItem.employee_id == employee_id,
                PayrollLineItem.facility_id == current_user.facility_id,
                PayrollLineItem.is_deleted.is_(False),
                PayrollRun.is_deleted.is_(False),
                PayrollRun.status.in_(["approved", "posted", "locked"]),
            )
            .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        )
    ).all()
    return [
        {
            "payroll_run_id": rid,
            "month": int(m),
            "year": int(y),
            "status": st,
            "gross_salary": str(Decimal(g or 0)),
            "net_salary": str(Decimal(n or 0)),
        }
        for (rid, m, y, st, g, n) in rows
    ]


# ── Reports ────────────────────────────────────────────────────────────────


@router.get("/reports/p9/{employee_id}", response_model=P9Response)
async def get_p9(
    employee_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> P9Response:
    """Annual P9 PAYE return for one employee."""
    try:
        data = await generate_p9(
            db=db,
            facility_id=current_user.facility_id,
            employee_id=employee_id,
            year=year,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return P9Response(
        employee_id=data["employee_id"],
        employee_name=data["employee_name"],
        kra_pin=data["kra_pin"],
        year=data["year"],
        rows=[P9Row(**row) for row in data["rows"]],
        totals=P9Row(**data["totals"]),
    )


@router.get("/reports/paye-schedule", response_model=PAYEScheduleResponse)
async def paye_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PAYEScheduleResponse:
    """KRA P10 PAYE schedule per employee."""
    return PAYEScheduleResponse(
        **await get_paye_schedule(db, current_user.facility_id, month, year)
    )


@router.get("/reports/nssf-schedule", response_model=NSSFScheduleResponse)
async def nssf_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NSSFScheduleResponse:
    """NSSF schedule per employee."""
    return NSSFScheduleResponse(
        **await get_nssf_schedule(db, current_user.facility_id, month, year)
    )


@router.get("/reports/shif-schedule", response_model=SHIFScheduleResponse)
async def shif_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SHIFScheduleResponse:
    """SHIF schedule per employee."""
    return SHIFScheduleResponse(
        **await get_shif_schedule(db, current_user.facility_id, month, year)
    )


@router.get("/reports/headcount", response_model=HeadcountResponse)
async def headcount_report(
    as_of: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> HeadcountResponse:
    """Headcount report by department + employment type."""
    return HeadcountResponse(
        **await get_headcount_report(
            db=db,
            facility_id=current_user.facility_id,
            as_of=as_of or date.today(),
        )
    )


@router.get("/reports/leave-utilisation")
async def leave_utilisation(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Leave utilisation for the year."""
    return await get_leave_utilisation(
        db=db, facility_id=current_user.facility_id, year=year
    )


@router.get("/reports/cost-trend", response_model=CostTrendResponse)
async def cost_trend(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CostTrendResponse:
    """Per-month payroll cost trend."""
    return CostTrendResponse(
        **await get_payroll_cost_trend(
            db=db, facility_id=current_user.facility_id, year=year
        )
    )


@router.get("/reports/turnover", response_model=TurnoverResponse)
async def turnover(
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    year: int | None = Query(None, ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TurnoverResponse:
    """Hires, terminations and ending headcount.

    Defaults to the current calendar year when no period is supplied, so the
    turnover trend chart works without the caller picking a range.
    """
    today = date.today()
    if year is not None:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    else:
        start = period_start or date(today.year, 1, 1)
        end = period_end or today
    return TurnoverResponse(
        **await get_employee_turnover(
            db=db,
            facility_id=current_user.facility_id,
            period_start=start,
            period_end=end,
        )
    )


# ── Statutory rate config ──────────────────────────────────────────────────


@router.get("/statutory-rates", response_model=list[StatutoryRateResponse])
async def list_statutory_rates(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[StatutoryRateResponse]:
    """List rates available to this facility (its own + globals)."""
    stmt = select(StatutoryRate).where(
        StatutoryRate.is_deleted.is_(False),
        or_(
            StatutoryRate.facility_id == current_user.facility_id,
            StatutoryRate.facility_id.is_(None),
        ),
    )
    if category is not None:
        stmt = stmt.where(StatutoryRate.category == category)
    rows = (await db.execute(stmt.order_by(StatutoryRate.effective_from.desc()))).scalars().all()
    return [StatutoryRateResponse.model_validate(r) for r in rows]


@router.post(
    "/statutory-rates",
    response_model=StatutoryRateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_statutory_rate(
    data: StatutoryRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin")
    ),
) -> StatutoryRateResponse:
    """Create a facility-scoped statutory rate override."""
    rate = StatutoryRate(
        facility_id=current_user.facility_id,
        name=data.name,
        category=data.category,
        rate=data.rate,
        fixed_amount=data.fixed_amount,
        fixed_cap=data.fixed_cap,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        notes=data.notes,
        approved_by=current_user.user_id,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return StatutoryRateResponse.model_validate(rate)


@router.get("/paye-bands", response_model=list[PAYEBandResponse])
async def list_paye_bands(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PAYEBandResponse]:
    """List currently-effective PAYE bands."""
    today = date.today()
    rows = (
        await db.execute(
            select(PAYEBand).where(
                PAYEBand.is_deleted.is_(False),
                PAYEBand.effective_from <= today,
                or_(PAYEBand.effective_to.is_(None), PAYEBand.effective_to >= today),
                or_(
                    PAYEBand.facility_id == current_user.facility_id,
                    PAYEBand.facility_id.is_(None),
                ),
            ).order_by(PAYEBand.lower_limit.asc())
        )
    ).scalars().all()
    return [PAYEBandResponse.model_validate(b) for b in rows]


@router.get("/nssf-tiers", response_model=list[NSSFTierResponse])
async def list_nssf_tiers(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[NSSFTierResponse]:
    """List currently-effective NSSF tiers."""
    today = date.today()
    rows = (
        await db.execute(
            select(NSSFTier).where(
                NSSFTier.is_deleted.is_(False),
                NSSFTier.effective_from <= today,
                or_(NSSFTier.effective_to.is_(None), NSSFTier.effective_to >= today),
                or_(
                    NSSFTier.facility_id == current_user.facility_id,
                    NSSFTier.facility_id.is_(None),
                ),
            ).order_by(NSSFTier.lower_limit.asc())
        )
    ).scalars().all()
    return [NSSFTierResponse.model_validate(t) for t in rows]


# ── Leave ──────────────────────────────────────────────────────────────────


@router.get("/leave-types", response_model=list[LeaveTypeResponse])
async def list_leave_types(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[LeaveTypeResponse]:
    """List leave types (facility-specific + globals)."""
    rows = (
        await db.execute(
            select(LeaveType).where(
                LeaveType.is_deleted.is_(False),
                or_(
                    LeaveType.facility_id == current_user.facility_id,
                    LeaveType.facility_id.is_(None),
                ),
            ).order_by(LeaveType.name.asc())
        )
    ).scalars().all()
    return [LeaveTypeResponse.model_validate(lt) for lt in rows]


@router.post(
    "/leave-types",
    response_model=LeaveTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_type(
    data: LeaveTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin")
    ),
) -> LeaveTypeResponse:
    """Create a facility leave type, reusing an existing one with the same name."""
    name = data.name.strip()
    existing = (
        await db.execute(
            select(LeaveType).where(
                LeaveType.is_deleted.is_(False),
                LeaveType.facility_id == current_user.facility_id,
                func.lower(LeaveType.name) == name.lower(),
            )
        )
    ).scalars().first()
    if existing is not None:
        return LeaveTypeResponse.model_validate(existing)

    leave_type = LeaveType(
        facility_id=current_user.facility_id,
        name=name,
        days_entitlement=data.days_entitlement,
        paid=data.paid,
        partial_pay=data.partial_pay,
        carries_over=data.carries_over,
        max_carryover=data.max_carryover,
        notes=data.notes,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(leave_type)
    await db.flush()
    await db.refresh(leave_type)
    return LeaveTypeResponse.model_validate(leave_type)


@router.get("/leave-requests", response_model=LeaveRequestListResponse)
async def list_leave_requests(
    employee_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeaveRequestListResponse:
    """List payroll leave requests for the facility.

    HR/managers see every request; other employees are scoped to their
    own payroll employee record (the auth staff id is resolved to the
    mirrored payroll employee row when present).
    """
    manager_roles = {
        "admin",
        "facility_admin",
        "hr_admin",
        "hr_officer",
        "manager",
        "super_admin",
    }
    if current_user.roles and any(r in manager_roles for r in current_user.roles):
        scope_employee_id = employee_id
    else:
        # Non-managers are scoped to their own payroll employee row. Their
        # auth id is a staff id, not the payroll employee id.
        scope_employee_id = None
        resolved = await resolve_payroll_employee(
            db, current_user.facility_id, current_user.user_id
        )
        if resolved is not None:
            scope_employee_id = resolved.id

    # Managers filtering by "my requests" pass their own staff id; resolve it.
    if (
        scope_employee_id is not None
        and scope_employee_id == current_user.user_id
    ):
        resolved = await resolve_payroll_employee(
            db, current_user.facility_id, current_user.user_id
        )
        scope_employee_id = resolved.id if resolved is not None else None

    stmt = (
        select(PayrollLeaveRequest, Employee.full_name, LeaveType.name)
        .join(Employee, Employee.id == PayrollLeaveRequest.employee_id)
        .join(LeaveType, LeaveType.id == PayrollLeaveRequest.leave_type_id)
        .where(
            PayrollLeaveRequest.facility_id == current_user.facility_id,
            PayrollLeaveRequest.is_deleted.is_(False),
            Employee.facility_id == current_user.facility_id,
        )
    )
    if scope_employee_id is not None:
        stmt = stmt.where(PayrollLeaveRequest.employee_id == scope_employee_id)
    if status:
        stmt = stmt.where(PayrollLeaveRequest.status == status)
    stmt = stmt.order_by(PayrollLeaveRequest.created_at.desc())

    rows = (await db.execute(stmt)).all()
    items = [
        LeaveRequestListItem(
            id=req.id,
            employee_id=req.employee_id,
            employee_name=emp_name,
            leave_type_id=req.leave_type_id,
            leave_type_name=lt_name,
            start_date=req.start_date,
            end_date=req.end_date,
            days_requested=req.days_requested,
            reason=req.reason,
            status=req.status,
            approved_by=req.approved_by,
            approved_at=req.approved_at,
            created_at=req.created_at,
        )
        for req, emp_name, lt_name in rows
    ]
    return LeaveRequestListResponse(items=items, total=len(items))


@router.post(
    "/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    data: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeaveRequestResponse:
    """Submit a payroll-aware leave request."""
    try:
        employee_id = data.employee_id
        # The Leave tab sends the signed-in user's staff id by default.
        # Translate that to the matching payroll employee record.
        if employee_id == current_user.user_id:
            resolved = await resolve_payroll_employee(
                db, current_user.facility_id, current_user.user_id
            )
            if resolved is None:
                raise ValueError(
                    "No payroll employee is linked to this account. "
                    "Ask an HR admin to register you as an employee first."
                )
            employee_id = resolved.id
        req = await submit_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            employee_id=employee_id,
            leave_type_id=data.leave_type_id,
            start_date=data.start_date,
            end_date=data.end_date,
            days_requested=data.days_requested,
            reason=data.reason,
            user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return LeaveRequestResponse.model_validate(req)


@router.post(
    "/leave-requests/{leave_id}/approve",
    response_model=LeaveRequestResponse,
)
async def process_leave_request(
    leave_id: uuid.UUID,
    data: LeaveApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "hr_admin", "hr_officer")
    ),
) -> LeaveRequestResponse:
    """Approve or reject a leave request."""
    if data.action == "approve":
        req = await approve_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            leave_id=leave_id,
            approver_id=current_user.user_id,
        )
    else:
        req = await reject_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            leave_id=leave_id,
            approver_id=current_user.user_id,
            reason=data.rejection_reason,
        )
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found"
        )
    return LeaveRequestResponse.model_validate(req)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _build_run_response(
    db: AsyncSession,
    facility_id: uuid.UUID,
    run: PayrollRun,
) -> PayrollRunResponse:
    """Hydrate a PayrollRun with its line items as a response model."""
    lines = (
        await db.execute(
            select(PayrollLineItem).where(
                PayrollLineItem.payroll_run_id == run.id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    emp_ids = [li.employee_id for li in lines]
    emp_rows = (
        await db.execute(
            select(Employee.id, Employee.full_name).where(Employee.id.in_(emp_ids))
        )
    ).all()
    emp_names = {row.id: row.full_name for row in emp_rows}
    resp = PayrollRunResponse.model_validate(run)
    line_responses = []
    for li in lines:
        data = {**li.__dict__}
        data.pop("_sa_instance_state", None)
        data["employee_name"] = emp_names.get(li.employee_id, "-")
        lr = PayrollLineItemResponse.model_validate(data)
        line_responses.append(lr)
    resp.line_items = line_responses
    return resp


# Monthly summary endpoint (placed at end so route order is intuitive)
@router.get("/reports/summary")
async def monthly_summary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Per-department monthly summary."""
    data = await get_monthly_payroll_summary(
        db=db, facility_id=current_user.facility_id, month=month, year=year
    )
    # Convert Decimals to strings for JSON safety
    for d in data["departments"]:
        d["total_gross"] = str(d["total_gross"])
        d["total_net"] = str(d["total_net"])
        d["total_paye"] = str(d["total_paye"])
    for k in (
        "grand_total_gross",
        "grand_total_net",
        "grand_total_paye",
        "grand_total_nssf",
        "grand_total_shif",
        "grand_total_hl",
    ):
        data[k] = str(data[k])
    return data