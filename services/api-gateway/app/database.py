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

    FastAPI may resolve the authentication dependency before or after this one,
    so when the caller has already been identified the acting user is published
    along with the tenant. Seeding the tenant alone would blank the
    ``app.current_user_*`` settings that the clinical audit trigger reads, and
    every recorded change would be attributed to nobody.

    Request state is read defensively rather than by importing CurrentUser, so
    this module never has to depend on the auth package.

    @returns AsyncSession for database operations
    """
    async with async_session() as session:
        request.state.db = session
        facility_id = getattr(request.state, "facility_id", None)
        if facility_id:
            current_user = getattr(request.state, "current_user", None)
            await set_facility_context(
                session,
                str(facility_id),
                user_id=getattr(current_user, "user_id", None),
                email=getattr(current_user, "email", None),
                roles=getattr(current_user, "roles", None),
            )

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            if getattr(request.state, "db", None) is session:
                del request.state.db
