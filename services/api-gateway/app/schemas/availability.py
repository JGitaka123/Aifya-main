"""A clinician's weekly working hours, and who may change them.

The roster in ``doctor_schedules`` decides whether a provider is on duty
today, so the shape of that week is employment information: HR owns it. A
clinician may still keep their own week truthful - a locum week, a changed
theatre list - but only the working days and hours, never their role, unit,
specialty or facility. This module is the shape of both edits.
"""

from __future__ import annotations

import uuid
from datetime import time

from pydantic import BaseModel, Field, model_validator

from app.schemas.appointment import DoctorScheduleResponse


class AvailabilitySlot(BaseModel):
    """One weekly working session: the day and the hours."""

    day_of_week: int = Field(
        ..., ge=0, le=6, description="Weekday, 0=Monday .. 6=Sunday"
    )
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _end_after_start(self) -> "AvailabilitySlot":
        """Refuse a session that ends before it begins."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class WeeklyScheduleUpdate(BaseModel):
    """Replace a whole week's availability in one call."""

    slots: list[AvailabilitySlot] = Field(default_factory=list, max_length=28)

    @model_validator(mode="after")
    def _no_duplicate_slots(self) -> "WeeklyScheduleUpdate":
        """Refuse two identical sessions, which would split one shift in two."""
        seen: set[tuple[int, time, time]] = set()
        for slot in self.slots:
            key = (slot.day_of_week, slot.start_time, slot.end_time)
            if key in seen:
                raise ValueError("duplicate availability slot")
            seen.add(key)
        return self


class WeeklyScheduleResponse(BaseModel):
    """A clinician's stored week, with the status it resolves to now."""

    staff_id: uuid.UUID
    slots: list[DoctorScheduleResponse]
    #: The effective work status the patient picker would see right now.
    work_status: str
    #: Whether an active roster is in force for this clinician.
    has_schedule: bool
    #: Whether that roster puts them on duty today.
    scheduled_today: bool