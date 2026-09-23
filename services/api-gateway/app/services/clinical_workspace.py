"""What one clinician has to do today.

Reception registers a patient, records the reason for the visit and routes the
patient to a department - and sometimes to a named clinician. This service
answers the only question the clinician then has: *which patients are mine?*

Scope
-----
The signed-in staff record supplies the clinician's profession, speciality and
department. Scope then decides which encounters are visible:

    mine        assigned to me, plus unclaimed patients I could pick up
    department  everyone routed to my department
    facility    everyone at the facility (administrators only)

A clinician without a configured department sees the facility's unclaimed
patients under ``mine``, so a single-doctor clinic works before departments are
set up. A clinician with a department sees unclaimed patients in that
department only.

Profession, speciality and department are data rather than roles: a dental
clinician is a ``doctor`` whose department is Dental, so one role serves every
speciality instead of one Keycloak role per hospital department.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.models.staff import Department, Staff

# Statuses the worklist reports. An admitted patient has left the clinician's
# day and a cancelled visit never happened, so neither belongs on the list.
WORKLIST_STATUSES: tuple[str, ...] = (
    "waiting",
    "in_consultation",
    "completed",
)

SCOPE_MINE = "mine"
SCOPE_DEPARTMENT = "department"
SCOPE_FACILITY = "facility"
WORKLIST_SCOPES: tuple[str, ...] = (SCOPE_MINE, SCOPE_DEPARTMENT, SCOPE_FACILITY)

# Roles allowed to widen the worklist to the whole facility.
FACILITY_WIDE_ROLES: tuple[str, ...] = ("admin", "facility_admin")

# Safety valve: a worklist is a day of work, never a paginated archive.
WORKLIST_LIMIT = 200


@dataclass
class ClinicianProfile:
    """Who the signed-in clinician is, and where they work."""

    staff_id: uuid.UUID | None
    name: str
    profession: str
    specialty: str | None
    department_id: uuid.UUID | None
    department_name: str | None


def is_facility_wide(roles: list[str]) -> bool:
    """
    Whether these roles may ask for the whole facility's work.

    @param roles: Roles from the access token
    @returns True when the caller is an administrator
    """
    return any(role in roles for role in FACILITY_WIDE_ROLES)


def default_scope(roles: list[str]) -> str:
    """
    The scope a clinician lands on when they do not choose one.

    @param roles: Roles from the access token
    @returns One of WORKLIST_SCOPES
    """
    return SCOPE_FACILITY if is_facility_wide(roles) else SCOPE_MINE


def scope_filter(
    scope: str,
    *,
    staff_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
):
    """
    Build the SQL that narrows a worklist to one scope.

    @param scope: mine, department or facility
    @param staff_id: The clinician's staff UUID
    @param department_id: The clinician's department UUID
    @returns A SQLAlchemy filter clause
    """
    if scope == SCOPE_FACILITY:
        return true()

    if scope == SCOPE_DEPARTMENT and department_id is not None:
        return Encounter.department_id == department_id

    # Mine: what is already assigned to me, plus what is unclaimed and within
    # reach. Nothing is reachable without a staff record to assign work to.
    if staff_id is None:
        return false()

    unclaimed = Encounter.attending_doctor_id.is_(None)
    if department_id is not None:
        unclaimed = and_(unclaimed, Encounter.department_id == department_id)

    return or_(Encounter.attending_doctor_id == staff_id, unclaimed)


class ClinicalWorkspaceService:
    """Read-only view of the encounters routed to one clinician."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_clinician(
        self, facility_id: uuid.UUID, staff_id: uuid.UUID
    ) -> ClinicianProfile:
        """
        Resolve the signed-in staff member's profession, speciality and unit.

        A token can belong to an account with no staff record (an integration
        or a platform operator). The workspace still renders, it just has no
        department to widen to.

        @param facility_id: Facility UUID
        @param staff_id: Staff UUID from the access token subject
        @returns The clinician's profile
        """
        staff = (
            await self.db.execute(
                select(Staff).where(
                    Staff.id == staff_id,
                    Staff.facility_id == facility_id,
                    Staff.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()

        if staff is None:
            return ClinicianProfile(
                staff_id=None,
                name="",
                profession="",
                specialty=None,
                department_id=None,
                department_name=None,
            )

        department_id = staff.department_id or staff.primary_department_id
        department_name: str | None = None
        if department_id is not None:
            department_name = (
                await self.db.execute(
                    select(Department.name).where(Department.id == department_id)
                )
            ).scalar_one_or_none()

        return ClinicianProfile(
            staff_id=staff.id,
            name=f"{staff.first_name} {staff.last_name}".strip(),
            profession=staff.role,
            specialty=staff.specialization,
            department_id=department_id,
            department_name=department_name,
        )

    async def get_worklist(
        self,
        facility_id: uuid.UUID,
        *,
        staff_id: uuid.UUID | None,
        department_id: uuid.UUID | None,
        scope: str,
        status: str | None = None,
    ) -> tuple[dict[str, int], list[Encounter]]:
        """
        Today's encounters in scope, with a count per status.

        The counts always describe the whole scoped day, so a clinician who
        filters down to `waiting` still sees how much work sits behind them.

        @param facility_id: Facility UUID
        @param staff_id: The clinician's staff UUID
        @param department_id: The clinician's department UUID
        @param scope: mine, department or facility
        @param status: Optional single status to filter the list by
        @returns Tuple of (counts by status, encounters for the list)
        """
        filters = [
            Encounter.facility_id == facility_id,
            Encounter.is_deleted == False,  # noqa: E712
            Encounter.status.in_(list(WORKLIST_STATUSES)),
            func.date(Encounter.encounter_date) == func.current_date(),
            scope_filter(scope, staff_id=staff_id, department_id=department_id),
        ]

        counted = (
            await self.db.execute(
                select(Encounter.status, func.count(Encounter.id))
                .where(*filters)
                .group_by(Encounter.status)
            )
        ).all()
        counts = {status_name: 0 for status_name in WORKLIST_STATUSES}
        for status_name, total in counted:
            counts[str(status_name)] = int(total)

        stmt = select(Encounter).where(*filters)
        if status:
            stmt = stmt.where(Encounter.status == status)
        stmt = stmt.order_by(
            Encounter.priority.desc(),
            Encounter.encounter_date.asc(),
        ).limit(WORKLIST_LIMIT)

        encounters = list((await self.db.execute(stmt)).scalars().all())
        return counts, encounters

    async def labels_for(
        self, encounters: list[Encounter]
    ) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
        """
        Resolve department and clinician names for a page of encounters.

        @param encounters: Encounters being displayed
        @returns Tuple of (department names by id, staff names by id)
        """
        department_ids = {
            encounter.department_id
            for encounter in encounters
            if encounter.department_id is not None
        }
        staff_ids = {
            encounter.attending_doctor_id
            for encounter in encounters
            if encounter.attending_doctor_id is not None
        }

        departments: dict[uuid.UUID, str] = {}
        if department_ids:
            rows = (
                await self.db.execute(
                    select(Department.id, Department.name).where(
                        Department.id.in_(department_ids)
                    )
                )
            ).all()
            departments = {row[0]: row[1] for row in rows}

        staff: dict[uuid.UUID, str] = {}
        if staff_ids:
            rows = (
                await self.db.execute(
                    select(Staff.id, Staff.first_name, Staff.last_name).where(
                        Staff.id.in_(staff_ids)
                    )
                )
            ).all()
            staff = {row[0]: f"{row[1]} {row[2]}".strip() for row in rows}

        return departments, staff