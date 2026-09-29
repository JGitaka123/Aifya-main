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

A clinician with a department sees the unclaimed patients routed to that
department plus the patients nobody has routed anywhere: reception registers
and takes the fee without choosing a unit, so an unrouted patient is the front
door's work until a doctor takes them and decides where they go next. A
clinician without a configured department sees only the unrouted patients, so a
single-doctor clinic still works before departments are set up. A patient routed
to another unit is never handed over - Dental's queue stays Dental's.

Profession, speciality and department are data rather than roles: a dental
clinician is a ``doctor`` whose department is Dental, so one role serves every
speciality instead of one Keycloak role per hospital department.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.models.emergency import EmergencyVisit
from app.models.patient import Patient
from app.models.referral import Referral
from app.models.staff import Department, Staff

_logger = logging.getLogger(__name__)

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

# Encounter statuses that are still work in front of the clinician.
ACTIVE_STATUSES: tuple[str, ...] = ("waiting", "in_consultation")

# Emergency visit statuses that mean the episode is over. The ED record is the
# authority on that, so a patient discharged, admitted, transferred, deceased or
# gone against advice in Emergency has left the clinician's day even when the
# shared encounter still reads as waiting.
CLOSED_EMERGENCY_STATUSES: tuple[str, ...] = (
    "discharged",
    "admitted",
    "transferred",
    "deceased",
    "left_against_advice",
)

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


def _search_filter(facility_id: uuid.UUID, term: str):
    """
    Build the SQL that matches one patient by name, MRN or queue number.

    The front desk and the clinician both know a patient by one of those three,
    rarely by UUID, so the box accepts any of them. Name matching is a plain
    substring so "wanjiku" finds "Mary Wanjiku", and a digit-only term also
    matches the queue number the patient is holding.

    @param facility_id: Facility UUID, so the subquery stays tenant-scoped
    @param term: Raw search text from the clinician
    @returns A SQLAlchemy filter clause
    """
    like = f"%{term}%"
    matches = [
        Encounter.patient_id.in_(
            select(Patient.id).where(
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.mrn.ilike(like),
                ),
            )
        )
    ]
    if term.isdigit():
        matches.append(Encounter.queue_number == int(term))
    return or_(*matches)


# The unit that holds the front door. Reception registers every walk-in
# without choosing a unit, so an un-routed encounter carries no department at
# all; that work is the outpatient unit's until a clinician routes it onward.
FRONT_DOOR_CODES = frozenset({"OPD", "OP", "OUTPATIENT", "OUT-PATIENT"})
FRONT_DOOR_NAME_HINTS = ("outpatient", "out-patient", "opd")


def is_front_door_department(code: str | None, name: str | None) -> bool:
    """
    Whether a department is the facility's front door (the OPD).

    @param code: Department code, e.g. OPD
    @param name: Department name, e.g. Outpatient Department
    @returns True when the un-routed front-door queue belongs to this unit
    """
    if code and code.strip().upper() in FRONT_DOOR_CODES:
        return True
    lowered = (name or "").lower()
    return any(hint in lowered for hint in FRONT_DOOR_NAME_HINTS)


def scope_filter(
    scope: str,
    *,
    staff_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    front_door: bool = False,
):
    """
    Build the SQL that narrows a worklist to one scope.

    @param scope: mine, department or facility
    @param staff_id: The clinician's staff UUID
    @param department_id: The clinician's department UUID
    @param front_door: True when this unit owns the un-routed front-door queue
    @returns A SQLAlchemy filter clause
    """
    if scope == SCOPE_FACILITY:
        return true()

    if scope == SCOPE_DEPARTMENT and department_id is not None:
        if front_door:
            # The outpatient unit also owns the patients nobody has routed yet
            # - they carry no department, so matching only on department_id
            # would hide the front door's own queue from the front door.
            return or_(
                Encounter.department_id == department_id,
                Encounter.department_id.is_(None),
            )
        return Encounter.department_id == department_id

    # Mine: what is already assigned to me, plus what is unclaimed and within
    # reach. Nothing is reachable without a staff record to assign work to.
    if staff_id is None:
        return false()

    unclaimed = Encounter.attending_doctor_id.is_(None)
    if department_id is not None:
        # A clinician with a unit picks up the unclaimed patients routed to it,
        # and the ones still at the front door: nobody has routed them, so they
        # are not another unit's queue yet. The doctor who takes the patient
        # decides where they go next.
        unclaimed = and_(
            unclaimed,
            or_(
                Encounter.department_id.is_(None),
                Encounter.department_id == department_id,
            ),
        )
    else:
        # A clinician with no unit of their own may only pick up the patients
        # nobody routed anywhere. Patients reception sent to another department
        # belong to that department's clinicians, not to every doctor in the
        # facility.
        unclaimed = and_(unclaimed, Encounter.department_id.is_(None))

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

    async def _is_front_door(
        self, facility_id: uuid.UUID, department_id: uuid.UUID | None
    ) -> bool:
        """
        Whether the clinician's unit is the facility's front door.

        @param facility_id: Facility UUID, so the lookup stays tenant-scoped
        @param department_id: The clinician's department UUID
        @returns True when un-routed patients belong to this unit
        """
        if department_id is None:
            return False
        row = (
            await self.db.execute(
                select(Department.code, Department.name).where(
                    Department.id == department_id,
                    Department.facility_id == facility_id,
                )
            )
        ).first()
        if row is None:
            # A staff record pointing at a unit that no longer exists behaves
            # like "no department configured": the clinician can work what
            # nobody has routed yet. Returning False here would leave them
            # with a permanently empty queue, because no encounter can ever
            # carry a dangling department id.
            _logger.warning(
                "worklist.department_unknown facility=%s department=%s",
                facility_id,
                department_id,
            )
            return True
        return is_front_door_department(row[0], row[1])

    async def get_worklist(
        self,
        facility_id: uuid.UUID,
        *,
        staff_id: uuid.UUID | None,
        department_id: uuid.UUID | None,
        scope: str,
        status: str | None = None,
        triaged: bool | None = None,
        search: str | None = None,
        only_department_id: uuid.UUID | None = None,
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
        @param triaged: True for patients the nurse has finished assessing, False
            for those still with OPD, None for both
        @param search: Optional patient name, MRN or queue number to narrow by
        @param only_department_id: Optional single unit to narrow the list to
        @returns Tuple of (counts by status, encounters for the list)
        """
        front_door = (
            await self._is_front_door(facility_id, department_id)
            if scope == SCOPE_DEPARTMENT and department_id is not None
            else False
        )
        filters = [
            Encounter.facility_id == facility_id,
            Encounter.is_deleted == False,  # noqa: E712
            Encounter.status.in_(list(WORKLIST_STATUSES)),
            func.date(Encounter.encounter_date) == func.current_date(),
            scope_filter(
                scope,
                staff_id=staff_id,
                department_id=department_id,
                front_door=front_door,
            ),
            ~and_(
                Encounter.status.in_(list(ACTIVE_STATUSES)),
                exists().where(
                    EmergencyVisit.encounter_id == Encounter.id,
                    EmergencyVisit.is_deleted == False,  # noqa: E712
                    EmergencyVisit.status.in_(list(CLOSED_EMERGENCY_STATUSES)),
                ),
            ),
        ]

        if triaged is not None:
            filters.append(
                Encounter.triaged_at.is_not(None)
                if triaged
                else Encounter.triaged_at.is_(None)
            )

        if only_department_id is not None:
            # An administrator narrowing the whole-facility view to one unit.
            filters.append(Encounter.department_id == only_department_id)

        if search and search.strip():
            filters.append(_search_filter(facility_id, search.strip()))

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

    async def referral_sources(
        self, encounters: list[Encounter]
    ) -> dict[uuid.UUID, tuple[str | None, datetime | None]]:
        """
        Where each encounter was routed from.

        A department's queue is mostly patients handed over by another unit, so
        the row has to say who sent them. Without it a dentist cannot tell a
        referral from a walk-in, and the routing trail is only discoverable by
        opening the record. The newest internal routing wins.

        @param encounters: Encounters being displayed
        @returns Map of encounter id to (source unit name, routed at)
        """
        encounter_ids = [encounter.id for encounter in encounters]
        if not encounter_ids:
            return {}

        rows = (
            await self.db.execute(
                select(
                    Referral.encounter_id,
                    Referral.referring_department_id,
                    Referral.referral_date,
                )
                .where(
                    Referral.encounter_id.in_(encounter_ids),
                    Referral.is_deleted == False,  # noqa: E712
                    Referral.referral_type == "internal",
                )
                .order_by(Referral.referral_date.desc())
            )
        ).all()

        department_ids = {
            row[1] for row in rows if row[1] is not None
        }
        names: dict[uuid.UUID, str] = {}
        if department_ids:
            named = (
                await self.db.execute(
                    select(Department.id, Department.name).where(
                        Department.id.in_(department_ids)
                    )
                )
            ).all()
            names = {row[0]: row[1] for row in named}

        sources: dict[uuid.UUID, tuple[str | None, datetime | None]] = {}
        for encounter_id, department_id, referral_date in rows:
            # Rows are newest first, so the first seen is the one in force.
            if encounter_id in sources:
                continue
            sources[encounter_id] = (names.get(department_id), referral_date)
        return sources

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
        # The nurse who triaged is shown beside the triage time, so the same
        # lookup has to carry them or the board would print a UUID.
        staff_ids.update(
            encounter.nurse_id
            for encounter in encounters
            if encounter.nurse_id is not None
        )

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

    async def emergency_links(
        self, encounters: list[Encounter]
    ) -> dict[uuid.UUID, tuple[uuid.UUID, str, str, str]]:
        """
        Link emergency visits to their shared encounters, in one query.

        An emergency visit and its encounter are one episode in two places. The
        clinician sees the encounter, so the emergency record it belongs to has
        to travel with it or the patient looks like an ordinary walk-in.

        @param encounters: Encounters on the page
        @returns Map of encounter UUID -> (visit id, visit number, status, colour)
        """
        encounter_ids = {encounter.id for encounter in encounters}
        if not encounter_ids:
            return {}
        rows = (
            await self.db.execute(
                select(
                    EmergencyVisit.encounter_id,
                    EmergencyVisit.id,
                    EmergencyVisit.visit_number,
                    EmergencyVisit.status,
                    EmergencyVisit.triage_color,
                ).where(
                    EmergencyVisit.encounter_id.in_(encounter_ids),
                    EmergencyVisit.is_deleted == False,  # noqa: E712
                )
            )
        ).all()
        return {
            encounter_id: (visit_id, visit_number, status, colour)
            for encounter_id, visit_id, visit_number, status, colour in rows
        }

    async def department_load(
        self,
        facility_id: uuid.UUID,
        *,
        department_id: uuid.UUID | None,
        facility_wide: bool,
    ) -> list[dict]:
        """
        Today's patient load for each department.

        The workspace is built on departments: reception routes a patient to a
        unit, and a clinician's unit is what decides which patients reach them.
        A clinician therefore sees the total for their own unit, and an
        administrator sees every unit side by side. A department that took no
        patients today is still returned, at zero, so a quiet unit reads as
        quiet rather than missing.

        @param facility_id: Facility UUID
        @param department_id: The signed-in clinician's own unit, if any
        @param facility_wide: Whether the caller may see the whole facility
        @returns One dict per department, with a count per status
        """
        departments = (
            await self.db.execute(
                select(Department.id, Department.code, Department.name)
                .where(
                    Department.facility_id == facility_id,
                    Department.is_deleted == False,  # noqa: E712
                    Department.is_active == True,  # noqa: E712
                )
                .order_by(Department.name)
            )
        ).all()

        counts: dict[uuid.UUID, dict[str, int]] = {}
        rows = (
            await self.db.execute(
                select(
                    Encounter.department_id,
                    Encounter.status,
                    func.count(Encounter.id),
                )
                .where(
                    Encounter.facility_id == facility_id,
                    Encounter.is_deleted == False,  # noqa: E712
                    Encounter.status.in_(list(WORKLIST_STATUSES)),
                    func.date(Encounter.encounter_date) == func.current_date(),
                    Encounter.department_id.is_not(None),
                )
                .group_by(Encounter.department_id, Encounter.status)
            )
        ).all()
        for encounter_department_id, status_name, total in rows:
            counts.setdefault(encounter_department_id, {})[str(status_name)] = int(
                total
            )

        load: list[dict] = []
        for unit_id, code, name in departments:
            if not facility_wide and unit_id != department_id:
                continue
            per_status = counts.get(unit_id, {})
            load.append(
                {
                    "department_id": unit_id,
                    "code": code,
                    "name": name,
                    "waiting": per_status.get("waiting", 0),
                    "in_consultation": per_status.get("in_consultation", 0),
                    "completed": per_status.get("completed", 0),
                    "total": sum(per_status.values()),
                }
            )
        return load
