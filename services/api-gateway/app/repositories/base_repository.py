import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base


class BaseRepository[T: Base]:
    """
    Base repository with facility-scoped queries.
    All data access is filtered by facility_id — no cross-facility leaks.
    Soft-delete only — 20-year retention per CLAUDE.md.
    """

    model: type[T]

    def __init__(self, db: AsyncSession, facility_id: uuid.UUID) -> None:
        """
        @param db: Async database session
        @param facility_id: Facility UUID from JWT (mandatory for multi-tenancy)
        """
        self.db = db
        self.facility_id = facility_id

    async def get_by_id(self, entity_id: uuid.UUID) -> T | None:
        """
        Fetch entity by ID, scoped to facility, excluding soft-deleted.

        @param entity_id: Entity UUID
        @returns Entity or None
        """
        result = await self.db.execute(
            select(self.model).where(
                self.model.id == entity_id,  # type: ignore[attr-defined]
                self.model.facility_id == self.facility_id,  # type: ignore[attr-defined]
                self.model.is_deleted == False,  # type: ignore[attr-defined] # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create(self, entity: T) -> T:
        """
        Insert a new entity.

        @param entity: Model instance
        @returns Persisted entity
        """
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def soft_delete(
        self, entity_id: uuid.UUID, deleted_by: uuid.UUID
    ) -> bool:
        """
        Soft-delete an entity. Never hard-delete clinical data.

        @param entity_id: Entity UUID
        @param deleted_by: Staff UUID performing the deletion
        @returns True if found and deleted, False if not found
        """
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False

        entity.is_deleted = True  # type: ignore[attr-defined]
        entity.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        entity.updated_by = deleted_by  # type: ignore[attr-defined]
        await self.db.flush()
        return True

    async def count(self) -> int:
        """
        Count non-deleted entities for this facility.

        @returns Total count
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(self.model)
            .where(
                self.model.facility_id == self.facility_id,  # type: ignore[attr-defined]
                self.model.is_deleted == False,  # type: ignore[attr-defined] # noqa: E712
            )
        )
        return result.scalar_one()
