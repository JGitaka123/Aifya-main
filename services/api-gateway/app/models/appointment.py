import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class DoctorSchedule(AuditMixin, Base):
    """
    Doctor weekly availability schedule.
    Defines recurring time slots when a doctor is available for appointments.
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        Index("ix_doctor_schedules_doctor", "facility_id", "doctor_id"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )

    # Schedule
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )  # Duration per appointment slot
    max_patients: Mapped[int | None] = mapped_column(Integer)  # Max per session

    # Location
    room: Mapped[str | None] = mapped_column(String(50))
    consultation_type: Mapped[str] = mapped_column(
        String(30), default="general", nullable=False
    )  # general, specialist, follow_up, procedure, anc, dental

    # Availability
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)

    notes: Mapped[str | None] = mapped_column(Text)


class Appointment(AuditMixin, Base):
    """
    Patient appointment booking.
    Lifecycle: scheduled → confirmed → checked_in → in_consultation → completed.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("facility_id", "appointment_number", name="uq_appointments_appointment_number"),
        Index("ix_appointments_patient", "facility_id", "patient_id"),
        Index("ix_appointments_doctor", "facility_id", "doctor_id"),
        Index("ix_appointments_date", "facility_id", "appointment_date"),
        Index("ix_appointments_status", "facility_id", "status"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctor_schedules.id")
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )

    # Booking
    appointment_number: Mapped[str] = mapped_column(String(50), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    # Type
    appointment_type: Mapped[str] = mapped_column(
        String(30), default="consultation", nullable=False
    )  # consultation, follow_up, procedure, lab, radiology, anc, dental, vaccination
    visit_reason: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(
        String(20), default="routine", nullable=False
    )  # routine, urgent, emergency

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, confirmed, checked_in, in_consultation, completed, cancelled, no_show

    # Check-in
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    # Reminder
    reminder_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Recurrence (for follow-up series)
    is_recurring: Mapped[bool] = mapped_column(default=False, nullable=False)
    recurrence_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id")
    )

    # Location
    room: Mapped[str | None] = mapped_column(String(50))

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)  # Staff-only notes

    # Booked by
    booked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
