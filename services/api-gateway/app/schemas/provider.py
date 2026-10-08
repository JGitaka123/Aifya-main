"""Provider directory for the consultation room's assignment picker.

The consultation room does not hand a patient to a *department*; it hands
them to a qualified person in that department. This module is the shape of
that answer: the clinicians the caller may choose, with the specialty and the
working availability that decide whether they can be chosen at all.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

#: The work states a clinician can be in, independent of account activation.
#: ``is_active`` says the account may sign in; this says whether the person
#: can actually take a patient now.
WORK_STATUSES: tuple[str, ...] = (
    "available",
    "busy",
    "on_leave",
    "off_duty",
    "unavailable",
)


class ProviderItem(BaseModel):
    """One clinician a patient can be handed to."""

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    title: str | None = None
    role: str
    specialty: str | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    #: The effective state, not necessarily the stored one: an approved leave
    #: or an in-flight consultation overrides what the record declares.
    work_status: str
    is_active: bool
    #: True when an approved leave covers today.
    is_on_leave: bool = False
    #: True when the clinician is already holding a consultation.
    is_occupied: bool = False


class ProviderDirectoryResponse(BaseModel):
    """Providers matching the picker's filters, plus the options available."""

    items: list[ProviderItem]
    total: int
    #: Distinct specialties present among the candidates, for the dropdown.
    specialties: list[str]


class ProviderWorkStatusUpdate(BaseModel):
    """Change a clinician's declared availability."""

    work_status: str = Field(
        ...,
        pattern=r"^(available|busy|on_leave|off_duty|unavailable)$",
    )
