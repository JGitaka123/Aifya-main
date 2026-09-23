import uuid
from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    """Schema for event timeline responses."""

    id: uuid.UUID
    event_type: str
    event_data: dict
    stream_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TimelineResponse(BaseModel):
    """Paginated event timeline response."""

    items: list[EventResponse]
    total: int
