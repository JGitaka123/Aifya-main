"""Keeping a clinician's week truthful without letting them redraw their job.

A weekly roster is the difference between "on duty today" and "off duty
today" in the assignment picker, so it is employment information. HR owns it
outright. A clinician may still keep their own week honest - a locum week, a
changed theatre list - but the only fields either of them may touch are the
working day and the hours; the role, unit, specialty and facility stay where
HR recorded them.

Replacing a week reconciles rather than deletes. A session that survives an
edit keeps its row, so an appointment already booked against it is not
orphaned; a session that is dropped is switched off, which stops it counting
for today's availability without destroying the record.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import DoctorSchedule
from app.models.staff import Staff
from app.schemas.appointment import DoctorScheduleResponse
from app.schemas.availability import AvailabilitySlot, WeeklyScheduleResponse
from app.services.hr_service import HRService
from app.services.provider_directory import ProviderDirectoryService


class AvailabilityService:
    """Read and rewrite a clinician's weekly working hours."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_own_staff_id(
        self, keycloak_user_id: uuid.UUID, facility_id: uuid.UUID
    ) -> uuid.UUID | None:
        """
        Map the signed-in token to the staff row it belongs to.

        Self-service never accepts a staff id from the caller: who you are is
        read from the token, so one clinician cannot edit another's week by
        passing a different id.

        @param keycloak_user_id: User UUID from the JWT
        @param facility_id: Facility UUID
        @returns Staff UUID, or None when the user has no staff record here
        """
        try:
            return await HRService(self.db).resolve_staff_id(
                keycloak_user_id, facility_id
            )
        except ValueError:
            return None

    async def get_week(
        self, facility_id: uuid.UUID, staff_id: uuid.UUID
    ) -> WeeklyScheduleResponse | None:
        """
        A clinician's stored week, or None when they are not in this facility.

        @param facility_id: Facility UUID
        @param staff_id: Staff UUID
        @returns The week and its live status, or None when not found
        """
        staff = await self._staff(facility_id, staff_id)
        if staff is None:
            return None
        return await self._snapshot(facility_id, staff)

    async def replace_week(
        self,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
        slots: list[AvailabilitySlot],
        actor_id: uuid.UUID,
    ) -> WeeklyScheduleResponse | None:
        """
        Replace a clinician's whole week with the slots given.

        @param facility_id: Facility UUID
        @param staff_id: Staff UUID whose week is being rewritten
        @param slots: The complete set of sessions the week should contain
        @param actor_id: User making the change, for the audit trail
        @returns The saved week and its live status, or None when not found
        """
        staff = await self._staff(facility_id, staff_id)
        if staff is None:
            return None
        await self._reconcile(facility_id, staff, slots, actor_id)
        await self.db.flush()
        return await self._snapshot(facility_id, staff)

    async def _staff(
        self, facility_id: uuid.UUID, staff_id: uuid.UUID
    ) -> Staff | None:
        """
        Load a non-deleted staff row scoped to the caller's facility.

        @param facility_id: Facility UUID
        @param staff_id: Staff UUID
        @returns The staff row, or None when it is not in this facility
        """
        return (
            await self.db.execute(
                select(Staff).where(
                    Staff.id == staff_id,
                    Staff.facility_id == facility_id,
                    Staff.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()

    async def _reconcile(
        self,
        facility_id: uuid.UUID,
        staff: Staff,
        slots: list[AvailabilitySlot],
        actor_id: uuid.UUID,
    ) -> None:
        """
        Make the stored week match ``slots``, reusing rows where possible.

        Two sessions are the same session when they share a day and both
        times, so ordinary edits keep their row identity and any appointment
        booked against it. A saved session that is no longer in the payload is
        switched off, never deleted.

        @param facility_id: Facility UUID
        @param staff: Staff row whose week is being rewritten
        @param slots: The complete set of sessions the week should contain
        @param actor_id: User making the change
        """
        existing = (
            await self.db.execute(
                select(DoctorSchedule).where(
                    DoctorSchedule.doctor_id == staff.id,
                    DoctorSchedule.facility_id == facility_id,
                    DoctorSchedule.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        by_key = {
            (row.day_of_week, row.start_time, row.end_time): row
            for row in existing
        }
        kept: set[uuid.UUID] = set()
        department_id = staff.department_id or staff.primary_department_id
        for slot in slots:
            key = (slot.day_of_week, slot.start_time, slot.end_time)
            row = by_key.get(key)
            if row is not None and row.id not in kept:
                row.is_active = True
                row.updated_by = actor_id
                kept.add(row.id)
                continue
            created = DoctorSchedule(
                facility_id=facility_id,
                doctor_id=staff.id,
                department_id=department_id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                slot_duration_minutes=15,
                consultation_type="general",
                is_active=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.db.add(created)
            kept.add(created.id)
        for row in existing:
            if row.id not in kept:
                row.is_active = False
                row.updated_by = actor_id

    async def _snapshot(
        self, facility_id: uuid.UUID, staff: Staff
    ) -> WeeklyScheduleResponse:
        """
        Read the stored week back together with the status it resolves to.

        @param facility_id: Facility UUID
        @param staff: Staff row the week belongs to
        @returns The week, its sessions, and today's effective status
        """
        rows = (
            await self.db.execute(
                select(DoctorSchedule)
                .where(
                    DoctorSchedule.doctor_id == staff.id,
                    DoctorSchedule.facility_id == facility_id,
                    DoctorSchedule.is_deleted == False,  # noqa: E712
                    DoctorSchedule.is_active == True,  # noqa: E712
                )
                .order_by(
                    DoctorSchedule.day_of_week.asc(),
                    DoctorSchedule.start_time.asc(),
                )
            )
        ).scalars().all()
        status, has_schedule, scheduled_today = (
            await ProviderDirectoryService(self.db).status_for_staff(
                facility_id, staff.id, staff.work_status
            )
        )
        return WeeklyScheduleResponse(
            staff_id=staff.id,
            slots=[DoctorScheduleResponse.model_validate(row) for row in rows],
            work_status=status,
            has_schedule=has_schedule,
            scheduled_today=scheduled_today,
        )