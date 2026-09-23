from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.middleware.facility_context import set_facility_context

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Celery tasks (app/services/dhis2/scheduler.py) use this name for a
# standalone session outside the request lifecycle.
async_session_factory = async_session


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields an async database session.

    @returns AsyncSession for database operations
    """
    async with async_session() as session:
        request.state.db = session
        facility_id = getattr(request.state, "facility_id", None)
        if facility_id:
            await set_facility_context(session, str(facility_id))

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            if getattr(request.state, "db", None) is session:
                del request.state.db
