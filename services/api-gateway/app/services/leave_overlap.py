"""Shared lookup of staff on approved leave for a given date.

The HR module records leave on leave_requests.staff_id while the
payroll Leave tab used by the UI writes
payroll_leave_requests.employee_id. Availability features (duty
roster, emergency, appointments) must treat both as "on leave" so a
leave approved in the Leave tab immediately hides that staff member
from shift duty and doctor availability on those dates.
"""

import uuid
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import LeaveRequest
from app.models.payroll import Employee
from app.models.payroll_extra import PayrollLeaveRequest
from app.models.staff import Staff


async def staff_ids_on_approved_leave(
    db: AsyncSession,
    facility_id: uuid.UUID,
    target_date: date,
) -> "set[uuid.UUID]":
    """Return staff ids on approved leave overlapping target_date.

    Considers both the HR leave_requests table (staff_id) and the
    payroll payroll_leave_requests table (employee_id), mapping
    payroll employees to their mirrored staff rows through the shared
    staff number (employees.staff_id = staff.employee_number).
    """
    on_leave: "set[uuid.UUID]" = set()

    hr_rows = await db.execute(
        select(LeaveRequest.staff_id).where(
            LeaveRequest.facility_id == facility_id,
            LeaveRequest.is_deleted.is_(False),
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= target_date,
            LeaveRequest.end_date >= target_date,
        )
    )
    on_leave.update(hr_rows.scalars().all())

    payroll_rows = await db.execute(
        select(Staff.id)
        .join(
            Employee,
            and_(
                Employee.facility_id == Staff.facility_id,
                Employee.staff_id == Staff.employee_number,
            ),
        )
        .join(
            PayrollLeaveRequest,
            PayrollLeaveRequest.employee_id == Employee.id,
        )
        .where(
            Staff.facility_id == facility_id,
            Staff.is_deleted.is_(False),
            Employee.is_deleted.is_(False),
            PayrollLeaveRequest.is_deleted.is_(False),
            PayrollLeaveRequest.status == "approved",
            PayrollLeaveRequest.start_date <= target_date,
            PayrollLeaveRequest.end_date >= target_date,
        )
    )
    on_leave.update(payroll_rows.scalars().all())
    return on_leave
