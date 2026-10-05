"""Request and response shapes for the queue and patient calling API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

#: Triage categories Aifya already uses on the encounter.
TRIAGE_PATTERN = "^(emergency|urgent|standard|non_urgent|dead)$"
#: What a patient is called into.
SERVICE_POINT_KIND_PATTERN = "^(room|counter|bay|desk|pharmacy|lab)$"
#: Permanent ticket states, mirroring app.services.queue.state_machine.
TICKET_STATUS_PATTERN = "^(WAITING|CALLED|IN_SERVICE|COMPLETED|NO_SHOW|CANCELLED|TRANSFERRED)$"


class QueueServicePointCreate(BaseModel):
    """Register a room or counter that patients can be called into."""

    name: str = Field(min_length=1, max_length=120)
    department_id: uuid.UUID | None = None
    kind: str = Field("room", pattern=SERVICE_POINT_KIND_PATTERN)
    display_label: str | None = Field(None, max_length=120)


class QueueServicePointResponse(BaseModel):
    """A room or counter as the board sees it."""

    id: uuid.UUID
    facility_id: uuid.UUID
    department_id: uuid.UUID | None = None
    name: str
    kind: str
    display_label: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueTicketCreate(BaseModel):
    """Issue a ticket to a patient who is now waiting."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    service_point_id: uuid.UUID | None = None
    triage_category: str | None = Field(None, pattern=TRIAGE_PATTERN)
    # 0 is normal. Higher is seen sooner; the caller sets it from the same
    # deterministic triage rules the OPD queue already uses.
    priority: int | None = Field(None, ge=0, le=100)
    notes: str | None = Field(None, max_length=2000)
    # Repeat the same key to make a retried registration idempotent.
    idempotency_key: str | None = Field(None, max_length=255)


class QueueTicketResponse(BaseModel):
    """One ticket, with the display fields the board needs."""

    id: uuid.UUID
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    service_point_id: uuid.UUID | None = None
    ticket_number: str
    priority: int
    triage_category: str | None = None
    status: str
    issued_at: datetime
    called_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    called_by: uuid.UUID | None = None
    recall_count: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    # Display and voice fields. The board may only ever show the ticket
    # number and the room: no names, no identifiers (privacy rule).
    patient_name: str | None = None
    patient_mrn: str | None = None
    department_name: str | None = None
    service_point_name: str | None = None
    service_point_label: str | None = None
    waiting_position: int | None = None
    waiting_minutes: int | None = None

    model_config = {"from_attributes": True}


class QueueBoardResponse(BaseModel):
    """The live board: everything waiting, called or in service."""

    items: list[QueueTicketResponse]
    total: int
    waiting: int
    called: int
    in_service: int


class QueueCallNextRequest(BaseModel):
    """Claim the highest priority waiting patient."""

    department_id: uuid.UUID | None = None
    service_point_id: uuid.UUID | None = None
    triage_category: str | None = Field(None, pattern=TRIAGE_PATTERN)
    # Announce the call to the public board, if the facility has voice on.
    announce: bool = True


class QueueCallRequest(BaseModel):
    """Call one specific ticket (the doctor picked it off their own list)."""

    service_point_id: uuid.UUID | None = None
    announce: bool = True


class QueueStartRequest(BaseModel):
    """The patient has walked in: service has started."""

    service_point_id: uuid.UUID | None = None


class QueueCancelRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class QueueTransferRequest(BaseModel):
    """Send the patient to another department's queue."""

    department_id: uuid.UUID
    service_point_id: uuid.UUID | None = None
    reason: str | None = Field(None, max_length=500)


class QueuePriorityRequest(BaseModel):
    """Re-rank a waiting ticket after triage changed."""

    priority: int = Field(ge=0, le=100)
    triage_category: str | None = Field(None, pattern=TRIAGE_PATTERN)


class QueueEventResponse(BaseModel):
    """One entry in a ticket's immutable history."""

    id: uuid.UUID
    ticket_id: uuid.UUID
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    actor_id: uuid.UUID | None = None
    service_point_id: uuid.UUID | None = None
    detail: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueAnnouncementResponse(BaseModel):
    """What the speaker should say for a ticket, and where the audio is."""

    ticket_id: uuid.UUID
    ticket_number: str
    text: str
    normalized_text: str
    language: str
    voice_enabled: bool
    audio_url: str | None = None
    content_type: str | None = None
    cached: bool = False


class QueueStatsResponse(BaseModel):
    """Operational counters for the staff dashboard."""

    waiting: int
    called: int
    in_service: int
    completed_today: int
    no_show_today: int
    average_wait_minutes: float | None = None
    longest_wait_minutes: int | None = None
    by_department: list[dict]
