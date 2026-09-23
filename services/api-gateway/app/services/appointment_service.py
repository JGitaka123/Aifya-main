import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, DoctorSchedule
from app.models.base import EventBase
from app.models.patient import Patient
from app.models.staff import Staff
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentListItem,
    AppointmentSummary,
    AppointmentUpdate,
    AvailableSlot,
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
    DoctorScheduleWithName,
)
from app.services.leave_overlap import staff_ids_on_approved_leave


class AppointmentService:
    """
    Service for appointment scheduling: doctor schedules, booking,
    check-in, rescheduling, cancellation, and availability lookup.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Doctor Schedules ──────────────────────────────────────────────────

    async def create_schedule(
        self,
        data: DoctorScheduleCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> DoctorSchedule:
        """
        Create a doctor availability schedule.

        @param data: Schedule creation data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created schedule
        """
        schedule = DoctorSchedule(
            facility_id=facility_id,
            doctor_id=data.doctor_id,
            department_id=data.department_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_minutes=data.slot_duration_minutes,
            max_patients=data.max_patients,
            room=data.room,
            consultation_type=data.consultation_type,
            effective_from=data.effective_from,
            effective_until=data.effective_until,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(schedule)
        await self.db.flush()
        await self.db.refresh(schedule)
        return schedule

    async def get_schedules(
        self,
        facility_id: uuid.UUID,
        doctor_id: uuid.UUID | None = None,
        consultation_type: str | None = None,
        active_only: bool = True,
    ) -> list[DoctorScheduleWithName]:
        """
        Get doctor schedules with doctor names.

        @param facility_id: Facility UUID
        @param doctor_id: Optional doctor filter
        @param consultation_type: Optional clinic type filter (e.g. dental)
        @param active_only: Only return schedules currently switched on
        @returns List of schedules with doctor names
        """
        query = (
            select(DoctorSchedule, Staff.first_name, Staff.last_name)
            .join(Staff, DoctorSchedule.doctor_id == Staff.id)
            .where(
                DoctorSchedule.facility_id == facility_id,
                DoctorSchedule.is_deleted == False,  # noqa: E712
            )
        )
        if active_only:
            query = query.where(DoctorSchedule.is_active == True)  # noqa: E712
        if doctor_id:
            query = query.where(DoctorSchedule.doctor_id == doctor_id)
        if consultation_type:
            query = query.where(
                DoctorSchedule.consultation_type == consultation_type
            )

        query = query.order_by(DoctorSchedule.day_of_week.asc(), DoctorSchedule.start_time.asc())
        result = await self.db.execute(query)
        rows = result.all()

        items: list[DoctorScheduleWithName] = []
        for sched, first_name, last_name in rows:
            item = DoctorScheduleWithName.model_validate(sched)
            item.doctor_name = f"{first_name or ''} {last_name or ''}".strip() or None
            items.append(item)

        return items

    async def update_schedule(
        self,
        schedule_id: uuid.UUID,
        data: DoctorScheduleUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> DoctorScheduleWithName | None:
        """
        Update a doctor schedule slot.

        @param schedule_id: Schedule UUID
        @param data: Fields to change
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated schedule with doctor name, or None when missing
        """
        result = await self.db.execute(
            select(DoctorSchedule).where(
                DoctorSchedule.id == schedule_id,
                DoctorSchedule.facility_id == facility_id,
                DoctorSchedule.is_deleted == False,  # noqa: E712
            )
        )
        schedule = result.scalar_one_or_none()
        if schedule is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(schedule, field, value)
        schedule.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(schedule)

        staff = await self.db.get(Staff, schedule.doctor_id)
        item = DoctorScheduleWithName.model_validate(schedule)
        if staff is not None:
            item.doctor_name = (
                f"{staff.first_name or ''} {staff.last_name or ''}".strip() or None
            )
        return item

    # ── Available Slots ───────────────────────────────────────────────────

    async def get_available_slots(
        self,
        facility_id: uuid.UUID,
        target_date: date,
        doctor_id: uuid.UUID | None = None,
    ) -> list[AvailableSlot]:
        """
        Get available appointment slots for a given date.

        @param facility_id: Facility UUID
        @param target_date: Date to check
        @param doctor_id: Optional doctor filter
        @returns List of available slots
        """
        day_of_week = target_date.weekday()  # 0=Monday
        on_leave_ids = await staff_ids_on_approved_leave(
            self.db, facility_id, target_date
        )

        query = (
            select(DoctorSchedule, Staff.first_name, Staff.last_name)
            .join(Staff, DoctorSchedule.doctor_id == Staff.id)
            .where(
                DoctorSchedule.facility_id == facility_id,
                DoctorSchedule.is_deleted == False,  # noqa: E712
                DoctorSchedule.is_active == True,  # noqa: E712
                DoctorSchedule.day_of_week == day_of_week,
            )
        )
        if doctor_id:
            query = query.where(DoctorSchedule.doctor_id == doctor_id)

        result = await self.db.execute(query)
        rows = result.all()

        slots: list[AvailableSlot] = []
        for sched, first_name, last_name in rows:
            # Doctors on approved leave for this date are not bookable.
            if sched.doctor_id in on_leave_ids:
                continue
            # Check effective dates
            if sched.effective_from and target_date < sched.effective_from:
                continue
            if sched.effective_until and target_date > sched.effective_until:
                continue

            doctor_name = f"{first_name or ''} {last_name or ''}".strip() or None

            # Generate time slots
            current = datetime.combine(target_date, sched.start_time)
            end = datetime.combine(target_date, sched.end_time)
            duration = timedelta(minutes=sched.slot_duration_minutes)

            while current + duration <= end:
                slot_start = current.time()
                slot_end = (current + duration).time()

                # Check if slot is already booked
                booked = await self.db.execute(
                    select(func.count(Appointment.id)).where(
                        Appointment.facility_id == facility_id,
                        Appointment.doctor_id == sched.doctor_id,
                        Appointment.appointment_date == target_date,
                        Appointment.start_time == slot_start,
                        Appointment.is_deleted == False,  # noqa: E712
                        Appointment.status.notin_(["cancelled", "no_show"]),
                    )
                )
                is_booked = (booked.scalar() or 0) > 0

                slots.append(
                    AvailableSlot(
                        schedule_id=sched.id,
                        doctor_id=sched.doctor_id,
                        doctor_name=doctor_name,
                        date=target_date,
                        start_time=slot_start,
                        end_time=slot_end,
                        room=sched.room,
                        consultation_type=sched.consultation_type,
                        available=not is_booked,
                    )
                )
                current += duration

        return slots

    # ── Appointments ──────────────────────────────────────────────────────

    async def create_appointment(
        self,
        data: AppointmentCreate,
        facility_id: uuid.UUID,
        booked_by: uuid.UUID,
    ) -> Appointment:
        """
        Book a new appointment.

        @param data: Appointment data
        @param facility_id: Facility UUID
        @param booked_by: Staff UUID
        @returns Created appointment
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")

        count_result = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.appointment_number.like(f"APT-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        appointment_number = f"APT-{date_part}-{seq:04d}"

        # Calculate end_time if not provided
        end_time = data.end_time
        if not end_time:
            start_dt = datetime.combine(data.appointment_date, data.start_time)
            end_dt = start_dt + timedelta(minutes=data.duration_minutes)
            end_time = end_dt.time()

        appointment = Appointment(
            facility_id=facility_id,
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            department_id=data.department_id,
            schedule_id=data.schedule_id,
            appointment_number=appointment_number,
            appointment_date=data.appointment_date,
            start_time=data.start_time,
            end_time=end_time,
            duration_minutes=data.duration_minutes,
            appointment_type=data.appointment_type,
            visit_reason=data.visit_reason,
            priority=data.priority,
            status="scheduled",
            room=data.room,
            notes=data.notes,
            is_recurring=data.is_recurring,
            booked_by=booked_by,
            created_by=booked_by,
            updated_by=booked_by,
        )
        self.db.add(appointment)
        await self.db.flush()
        await self.db.refresh(appointment)

        event = EventBase(
            facility_id=facility_id,
            stream_type="appointment",
            stream_id=data.patient_id,
            event_type="AppointmentBooked",
            event_data={
                "appointment_id": str(appointment.id),
                "appointment_number": appointment_number,
                "doctor_id": str(data.doctor_id),
                "date": str(data.appointment_date),
                "type": data.appointment_type,
            },
            version=1,
            created_by=booked_by,
        )
        self.db.add(event)

        return appointment

    async def get_appointments(
        self,
        facility_id: uuid.UUID,
        target_date: date | None = None,
        doctor_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        status: str | None = None,
        appointment_type: str | None = None,
    ) -> list[AppointmentListItem]:
        """
        Get appointments with patient and doctor names.

        @param facility_id: Facility UUID
        @param target_date: Optional date filter
        @param doctor_id: Optional doctor filter
        @param patient_id: Optional patient filter
        @param status: Optional status filter
        @param appointment_type: Optional appointment type filter
        @returns List of appointments
        """
        # Alias for doctor staff table
        DoctorStaff = Staff.__table__.alias("doctor_staff")  # noqa: N806 — SQLAlchemy alias naming

        query = (
            select(
                Appointment,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                Patient.mrn,
                DoctorStaff.c.first_name.label("d_first"),
                DoctorStaff.c.last_name.label("d_last"),
            )
            .join(Patient, Appointment.patient_id == Patient.id)
            .join(DoctorStaff, Appointment.doctor_id == DoctorStaff.c.id)
            .where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
            )
        )

        if target_date:
            query = query.where(Appointment.appointment_date == target_date)
        if doctor_id:
            query = query.where(Appointment.doctor_id == doctor_id)
        if patient_id:
            query = query.where(Appointment.patient_id == patient_id)
        if status:
            query = query.where(Appointment.status == status)
        if appointment_type:
            query = query.where(Appointment.appointment_type == appointment_type)

        query = query.order_by(
            Appointment.appointment_date.asc(),
            Appointment.start_time.asc(),
        )
        result = await self.db.execute(query)
        rows = result.all()

        items: list[AppointmentListItem] = []
        for appt, p_first, p_last, mrn, d_first, d_last in rows:
            patient_name = f"{p_first or ''} {p_last or ''}".strip() or None
            doctor_name = f"{d_first or ''} {d_last or ''}".strip() or None
            items.append(
                AppointmentListItem(
                    id=appt.id,
                    appointment_number=appt.appointment_number,
                    patient_id=appt.patient_id,
                    patient_name=patient_name,
                    patient_mrn=mrn,
                    doctor_id=appt.doctor_id,
                    doctor_name=doctor_name,
                    appointment_date=appt.appointment_date,
                    start_time=appt.start_time,
                    end_time=appt.end_time,
                    appointment_type=appt.appointment_type,
                    priority=appt.priority,
                    status=appt.status,
                    room=appt.room,
                    visit_reason=appt.visit_reason,
                    created_at=appt.created_at,
                )
            )

        return items

    async def get_appointment(
        self,
        appointment_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> Appointment | None:
        """
        Get a single appointment by ID.

        @param appointment_id: Appointment UUID
        @param facility_id: Facility UUID
        @returns Appointment or None
        """
        result = await self.db.execute(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_appointment(
        self,
        appointment_id: uuid.UUID,
        data: AppointmentUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Appointment | None:
        """
        Update an appointment (reschedule, change status, cancel).

        @param appointment_id: Appointment UUID
        @param data: Update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated appointment or None
        """
        appt = await self.get_appointment(appointment_id, facility_id)
        if not appt:
            return None

        if data.appointment_date is not None:
            appt.appointment_date = data.appointment_date
        if data.start_time is not None:
            appt.start_time = data.start_time
        if data.end_time is not None:
            appt.end_time = data.end_time
        if data.room is not None:
            appt.room = data.room
        if data.notes is not None:
            appt.notes = data.notes

        if data.status:
            appt.status = data.status
            if data.status == "cancelled":
                appt.cancelled_at = datetime.now(UTC)
                appt.cancelled_by = updated_by
                appt.cancellation_reason = data.cancellation_reason

        appt.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(appt)
        return appt

    async def check_in(
        self,
        appointment_id: uuid.UUID,
        facility_id: uuid.UUID,
        checked_in_by: uuid.UUID,
    ) -> Appointment | None:
        """
        Check in a patient for their appointment.

        @param appointment_id: Appointment UUID
        @param facility_id: Facility UUID
        @param checked_in_by: Staff UUID
        @returns Updated appointment or None
        """
        appt = await self.get_appointment(appointment_id, facility_id)
        if not appt:
            return None

        appt.status = "checked_in"
        appt.checked_in_at = datetime.now(UTC)
        appt.checked_in_by = checked_in_by
        appt.updated_by = checked_in_by

        await self.db.flush()
        await self.db.refresh(appt)

        event = EventBase(
            facility_id=facility_id,
            stream_type="appointment",
            stream_id=appt.patient_id,
            event_type="AppointmentCheckedIn",
            event_data={
                "appointment_id": str(appt.id),
                "appointment_number": appt.appointment_number,
            },
            version=1,
            created_by=checked_in_by,
        )
        self.db.add(event)

        return appt

    # ── Summary ───────────────────────────────────────────────────────────

    async def get_summary(
        self, facility_id: uuid.UUID
    ) -> AppointmentSummary:
        """
        Get appointment dashboard summary for today.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()

        total = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
            )
        )
        scheduled = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "scheduled",
            )
        )
        confirmed = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "confirmed",
            )
        )
        checked = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "checked_in",
            )
        )
        completed = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "completed",
            )
        )
        cancelled = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "cancelled",
            )
        )
        no_show = await self.db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date == today,
                Appointment.status == "no_show",
            )
        )

        return AppointmentSummary(
            total_today=total.scalar() or 0,
            scheduled=scheduled.scalar() or 0,
            confirmed=confirmed.scalar() or 0,
            checked_in=checked.scalar() or 0,
            completed_today=completed.scalar() or 0,
            cancelled_today=cancelled.scalar() or 0,
            no_show_today=no_show.scalar() or 0,
        )
