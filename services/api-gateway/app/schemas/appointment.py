import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

# ── Doctor Schedule ──────────────────────────────────────────────────────────


class DoctorScheduleCreate(BaseModel):
    """Schema for creating a doctor schedule slot."""

    doctor_id: uuid.UUID
    department_id: uuid.UUID | None = None
    day_of_week: int = Field(..., ge=0, le=6)  # 0=Mon, 6=Sun
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(15, ge=5, le=120)
    max_patients: int | None = Field(None, ge=1)
    room: str | None = Field(None, max_length=50)
    consultation_type: str = Field(
        default="general",
        pattern=r"^(general|specialist|follow_up|procedure|anc|dental)$",
    )
    effective_from: date | None = None
    effective_until: date | None = None
    notes: str | None = Field(None, max_length=500)


class DoctorScheduleResponse(BaseModel):
    """Schema for doctor schedule API responses."""

    id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    max_patients: int | None
    room: str | None
    consultation_type: str
    is_active: bool
    effective_from: date | None
    effective_until: date | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DoctorScheduleWithName(DoctorScheduleResponse):
    """Doctor schedule with doctor name for display."""

    doctor_name: str | None = None


class DoctorScheduleUpdate(BaseModel):
    """Schema for updating a doctor schedule slot."""

    day_of_week: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_minutes: int | None = Field(None, ge=5, le=120)
    max_patients: int | None = Field(None, ge=1)
    room: str | None = Field(None, max_length=50)
    consultation_type: str | None = Field(
        None,
        pattern=r"^(general|specialist|follow_up|procedure|anc|dental)$",
    )
    is_active: bool | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    notes: str | None = Field(None, max_length=500)


# ── Available Slots ──────────────────────────────────────────────────────────


class AvailableSlot(BaseModel):
    """Available time slot for booking."""

    schedule_id: uuid.UUID
    doctor_id: uuid.UUID
    doctor_name: str | None = None
    date: date
    start_time: time
    end_time: time
    room: str | None
    consultation_type: str
    available: bool = True


# ── Appointment ──────────────────────────────────────────────────────────────


class AppointmentCreate(BaseModel):
    """Schema for creating an appointment."""

    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID | None = None
    schedule_id: uuid.UUID | None = None
    appointment_date: date
    start_time: time
    end_time: time | None = None
    duration_minutes: int = Field(15, ge=5, le=240)
    appointment_type: str = Field(
        default="consultation",
        pattern=r"^(consultation|follow_up|procedure|lab|radiology|anc|dental|vaccination)$",
    )
    visit_reason: str | None = Field(None, max_length=1000)
    priority: str = Field(
        default="routine", pattern=r"^(routine|urgent|emergency)$"
    )
    room: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    is_recurring: bool = False


class AppointmentResponse(BaseModel):
    """Schema for appointment API responses."""

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID | None
    schedule_id: uuid.UUID | None
    encounter_id: uuid.UUID | None
    appointment_number: str
    appointment_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    appointment_type: str
    visit_reason: str | None
    priority: str
    status: str
    checked_in_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    reminder_sent: bool
    is_recurring: bool
    room: str | None
    notes: str | None
    booked_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentListItem(BaseModel):
    """Appointment in list view with patient and doctor names."""

    id: uuid.UUID
    appointment_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    doctor_id: uuid.UUID
    doctor_name: str | None = None
    appointment_date: date
    start_time: time
    end_time: time
    appointment_type: str
    priority: str
    status: str
    room: str | None
    visit_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentListResponse(BaseModel):
    """Paginated appointment list response."""

    items: list[AppointmentListItem]
    total: int


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""

    appointment_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: str | None = Field(
        None,
        pattern=r"^(scheduled|confirmed|checked_in|in_consultation|completed|cancelled|no_show)$",
    )
    room: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    cancellation_reason: str | None = Field(None, max_length=1000)


class AppointmentCheckIn(BaseModel):
    """Schema for checking in a patient."""

    notes: str | None = Field(None, max_length=500)


# ── Summary ──────────────────────────────────────────────────────────────────


class AppointmentSummary(BaseModel):
    """Dashboard summary stats for appointments."""

    total_today: int = 0
    scheduled: int = 0
    confirmed: int = 0
    checked_in: int = 0
    completed_today: int = 0
    cancelled_today: int = 0
    no_show_today: int = 0
