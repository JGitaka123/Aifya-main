import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase


class EventService:
    """Service for querying the event store."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_patient_timeline(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        limit: int = 50,
    ) -> tuple[list[EventBase], int]:
        """
        Get the event timeline for a patient across all streams.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID from JWT
        @param limit: Max events to return
        @returns Tuple of (events, total count)
        """
        base = select(EventBase).where(
            EventBase.facility_id == facility_id,
            EventBase.stream_id == patient_id,
        )

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Fetch recent events
        result = await self.db.execute(
            base.order_by(EventBase.created_at.desc()).limit(limit)
        )
        events = list(result.scalars().all())

        return events, total
