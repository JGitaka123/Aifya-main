"""Who can take this patient, in this unit, right now.

The consultation room assigns a patient to a person, not to a department.
That decision has three parts - the unit, the specialty and whether the
clinician is actually free - and this service answers all three from the
staff record plus the live facts the record alone cannot carry: whether
approved leave covers today, whether the clinician is already holding a
consultation, and whether their weekly schedule puts them on duty at all.

Availability is therefore *effective*, never merely declared. An active
account (``staff.is_active``) that is on leave, mid-consultation, or simply
not scheduled today is not available, and the picker must not pretend
otherwise.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import ROLE_PERMISSIONS, Permission
from app.config import settings
from app.models.appointment import DoctorSchedule
from app.models.encounter import Encounter
from app.models.facility import Facility
from app.models.staff import Department, Staff
from app.schemas.provider import WORK_STATUSES, ProviderItem
from app.services.leave_overlap import staff_ids_on_approved_leave

#: Roles that may receive a patient. Taken from the permission matrix rather
#: than a hand-written list, so a role added there (a dentist, a midwife) is a
#: provider here without a second edit. A records clerk or cashier holds no
#: clinical permission and is never offered.
_PROVIDER_PERMISSIONS: frozenset[str] = frozenset(
    {Permission.CLINICAL_VIEW.value, Permission.CLINICAL_CONSULT.value}
)
PROVIDER_ROLES: frozenset[str] = frozenset(
    role
    for role, permissions in ROLE_PERMISSIONS.items()
    if permissions & _PROVIDER_PERMISSIONS
)

#: Sort order for the picker: whoever can take the patient leads.
_STATUS_RANK: dict[str, int] = {
    "available": 0,
    "busy": 1,
    "on_leave": 2,
    "off_duty": 3,
    "unavailable": 4,
}

#: Used when a facility's own timezone is missing or invalid, so the weekday
#: is never computed against the wrong calendar.
_FALLBACK_TIMEZONE = "Africa/Nairobi"


def _effective_work_status(
    declared: str | None,
    is_on_leave: bool,
    is_occupied: bool,
    *,
    has_schedule: bool = False,
    scheduled_today: bool = False,
) -> str:
    """
    Resolve declared availability against the live state.

    Precedence, most authoritative first:

    1. approved leave today -> ``on_leave``
    2. already in a consultation -> ``busy``
    3. a weekly schedule in force that omits today -> ``off_duty``
    4. otherwise the status the record declares

    A clinician with no schedule in force is deliberately *not* forced off
    duty. An unset schedule must never hide someone from the picker, so their
    declared status stands - that is what keeps a newly added colleague
    routable before anyone has drawn up their week.

    @param declared: The stored ``staff.work_status``
    @param is_on_leave: Whether approved leave covers today
    @param is_occupied: Whether the clinician holds a consultation now
    @param has_schedule: Whether a weekly schedule is in force today
    @param scheduled_today: Whether that schedule marks today as a working day
    @returns One of ``WORK_STATUSES``
    """
    if is_on_leave:
        return "on_leave"
    if is_occupied:
        return "busy"
    if has_schedule and not scheduled_today:
        return "off_duty"
    if declared in WORK_STATUSES:
        return declared
    return "unavailable"


class ProviderDirectoryService:
    """The assignment picker's query surface."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_providers(
        self,
        facility_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        role: str | None = None,
        specialty: str | None = None,
        work_status: str | None = None,
        available_only: bool = False,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[ProviderItem], list[str]]:
        """
        Providers matching the picker's filters, and the specialties offered.

        @param facility_id: Facility UUID; the picker never crosses tenants
        @param department_id: Restrict to one unit, matching either the posted
            or the primary department
        @param role: Optional single role filter (defaults to every clinical
            role)
        @param specialty: Optional exact specialty filter
        @param work_status: Optional effective-availability filter
        @param available_only: Keep only clinicians who can be assigned now
        @param search: Optional name substring
        @param include_inactive: Include deactivated accounts
        @returns Tuple of (matching providers, distinct specialties offered)
        """
        department_ref = func.coalesce(
            Staff.department_id, Staff.primary_department_id
        )
        query = (
            select(Staff, Department.name.label("dept_name"))
            .outerjoin(Department, Department.id == department_ref)
            .where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        if not include_inactive:
            query = query.where(Staff.is_active == True)  # noqa: E712
        if role:
            query = query.where(Staff.role == role)
        else:
            query = query.where(Staff.role.in_(PROVIDER_ROLES))
        if department_id is not None:
            query = query.where(
                or_(
                    Staff.department_id == department_id,
                    Staff.primary_department_id == department_id,
                )
            )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                Staff.first_name.ilike(pattern) | Staff.last_name.ilike(pattern)
            )
        result = await self.db.execute(
            query.order_by(Staff.last_name.asc(), Staff.first_name.asc())
        )
        rows = result.all()

        # One "today", read in the facility's own timezone, answers all three
        # live questions - approved leave, an open consultation and the weekly
        # roster - so they can never disagree about which day is being judged.
        today = await self._facility_today(facility_id)
        on_leave = await staff_ids_on_approved_leave(self.db, facility_id, today)
        occupied = await self._occupied_ids(facility_id, today)
        scheduled_today, has_schedule = await self._schedule_state(
            facility_id, today
        )

        # The specialty dropdown is built from every candidate in the unit, so
        # narrowing by availability never empties the list of options.
        specialties = sorted(
            {
                staff.specialization
                for staff, _ in rows
                if staff.specialization
            },
            key=str.lower,
        )

        items: list[ProviderItem] = []
        wanted_specialty = specialty.lower() if specialty else None
        for staff, dept_name in rows:
            declared_specialty = staff.specialization
            if (
                wanted_specialty
                and (declared_specialty or "").lower() != wanted_specialty
            ):
                continue
            status = _effective_work_status(
                staff.work_status,
                staff.id in on_leave,
                staff.id in occupied,
                has_schedule=staff.id in has_schedule,
                scheduled_today=staff.id in scheduled_today,
            )
            if available_only and status != "available":
                continue
            if work_status and status != work_status:
                continue
            items.append(
                ProviderItem(
                    id=staff.id,
                    first_name=staff.first_name,
                    last_name=staff.last_name,
                    full_name=f"{staff.first_name} {staff.last_name}".strip(),
                    title=staff.title,
                    role=staff.role,
                    specialty=declared_specialty,
                    department_id=(
                        staff.department_id or staff.primary_department_id
                    ),
                    department_name=dept_name,
                    work_status=status,
                    is_active=staff.is_active,
                    is_on_leave=staff.id in on_leave,
                    is_occupied=staff.id in occupied,
                )
            )

        items.sort(
            key=lambda p: (
                _STATUS_RANK.get(p.work_status, 9),
                p.last_name.lower(),
                p.first_name.lower(),
            )
        )
        return items, specialties

    async def is_eligible_receiver(
        self,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> bool:
        """
        Whether this clinician may be handed a patient in this unit.

        Guards the route endpoint: a named receiver must be active, a clinical
        provider, and posted to (or primarily in) the destination unit, so a
        hand-off can never be addressed to someone who cannot take it.

        @param facility_id: Facility UUID
        @param staff_id: Chosen clinician's staff UUID
        @param department_id: Destination department UUID
        @returns True when the clinician qualifies
        """
        row = (
            await self.db.execute(
                select(Staff.id).where(
                    Staff.id == staff_id,
                    Staff.facility_id == facility_id,
                    Staff.is_deleted == False,  # noqa: E712
                    Staff.is_active == True,  # noqa: E712
                    Staff.role.in_(PROVIDER_ROLES),
                    or_(
                        Staff.department_id == department_id,
                        Staff.primary_department_id == department_id,
                    ),
                )
            )
        ).scalar_one_or_none()
        return row is not None

    async def status_for_staff(
        self,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
        declared: str | None,
    ) -> tuple[str, bool, bool]:
        """
        One clinician's effective availability, and the roster behind it.

        The picker resolves a whole unit at once; the schedule screens ask the
        same question about a single person. Both go through
        ``_effective_work_status`` here, so a badge on a profile and the
        clinician's place in the picker can never disagree.

        @param facility_id: Facility UUID
        @param staff_id: Staff UUID whose status is wanted
        @param declared: The stored ``staff.work_status``
        @returns Tuple of (effective status, has schedule, scheduled today)
        """
        today = await self._facility_today(facility_id)
        on_leave = await staff_ids_on_approved_leave(
            self.db, facility_id, today
        )
        occupied = await self._occupied_ids(facility_id, today)
        scheduled_today, has_schedule = await self._schedule_state(
            facility_id, today
        )
        status = _effective_work_status(
            declared,
            staff_id in on_leave,
            staff_id in occupied,
            has_schedule=staff_id in has_schedule,
            scheduled_today=staff_id in scheduled_today,
        )
        return status, staff_id in has_schedule, staff_id in scheduled_today
    async def _facility_today(self, facility_id: uuid.UUID) -> date:
        """
        Today's date as the hospital experiences it.

        The weekday that decides who is on duty has to be read in the
        facility's own timezone, or a late-night hand-off in Nairobi would be
        judged against the wrong day's roster.

        @param facility_id: Facility UUID
        @returns The current calendar date at the facility
        """
        facility_tz = (
            await self.db.execute(
                select(Facility.timezone).where(Facility.id == facility_id)
            )
        ).scalar_one_or_none()
        try:
            zone = ZoneInfo(facility_tz or settings.facility_timezone)
        except Exception:
            zone = ZoneInfo(_FALLBACK_TIMEZONE)
        return datetime.now(zone).date()

    async def _schedule_state(
        self, facility_id: uuid.UUID, today: date
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        """
        Who has a weekly schedule in force, and who it puts on duty today.

        Only rows whose effective window covers today count, so a roster that
        was switched off or has expired stops restricting anybody. The two
        sets answer different questions: a clinician in neither is left to
        their declared status, while one in ``has_schedule`` but not in
        ``scheduled_today`` is off duty for the day.

        @param facility_id: Facility UUID
        @param today: Today's date in the facility's own timezone
        @returns Tuple of (staff scheduled today, staff with any schedule in force)
        """
        weekday = today.weekday()
        rows = await self.db.execute(
            select(DoctorSchedule.doctor_id, DoctorSchedule.day_of_week)
            .where(
                DoctorSchedule.facility_id == facility_id,
                DoctorSchedule.is_deleted == False,  # noqa: E712
                DoctorSchedule.is_active == True,  # noqa: E712
                or_(
                    DoctorSchedule.effective_from.is_(None),
                    DoctorSchedule.effective_from <= today,
                ),
                or_(
                    DoctorSchedule.effective_until.is_(None),
                    DoctorSchedule.effective_until >= today,
                ),
            )
            .distinct()
        )
        has_schedule: set[uuid.UUID] = set()
        scheduled_today: set[uuid.UUID] = set()
        for doctor_id, day_of_week in rows.all():
            has_schedule.add(doctor_id)
            if day_of_week == weekday:
                scheduled_today.add(doctor_id)
        return scheduled_today, has_schedule

    async def _occupied_ids(
        self, facility_id: uuid.UUID, today: date
    ) -> set[uuid.UUID]:
        """
        Clinicians holding a consultation today.

        A visit left ``in_consultation`` on a previous day is stale, not a
        reason to hide someone from today's picker, so the search is bounded
        to the current day.

        @param facility_id: Facility UUID
        @param today: Today's date in the facility's own timezone
        @returns Set of staff UUIDs currently occupied
        """
        start_of_day = datetime.combine(today, time.min, tzinfo=timezone.utc)
        rows = await self.db.execute(
            select(Encounter.attending_doctor_id)
            .where(
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
                Encounter.status == "in_consultation",
                Encounter.attending_doctor_id.is_not(None),
                Encounter.encounter_date >= start_of_day,
            )
            .distinct()
        )
        return {row for row in rows.scalars().all() if row is not None}
