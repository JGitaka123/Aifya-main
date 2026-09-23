"""
Async database session management for the Knowledge RAG service.
"""

import uuid

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from structlog import get_logger

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

_FACILITY_CONTEXT_SQL = text(
    "SELECT set_config('app.current_facility_id', :facility_id, false)"
)


async def set_facility_context(
    session: AsyncSession, facility_id: uuid.UUID | str
) -> None:
    """
    Publish the caller's facility to PostgreSQL for row-level security.

    ``knowledge_documents`` and ``knowledge_chunks`` carry the same
    ``facility_isolation`` policy as every other tenant table, and that policy
    compares ``facility_id`` against ``current_setting('app.current_facility_id')``.
    Without this call every statement matches zero rows and every insert is
    rejected by the policy's WITH CHECK clause.

    Applied at session scope (is_local=false) so it survives the commits that
    happen part-way through a request.

    @param session: Async database session
    @param facility_id: Facility UUID taken from the verified JWT
    """
    await session.execute(
        _FACILITY_CONTEXT_SQL, {"facility_id": str(facility_id)}
    )


async def get_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncSession:  # type: ignore[misc]
    """
    FastAPI dependency: yield an async database session scoped to the
    caller's facility so RLS filters every statement.
    Automatically commits on success, rolls back on error.

    @param current_user: Authenticated user resolved from the bearer token
    @returns AsyncSession
    """
    async with async_session_factory() as session:
        try:
            await set_facility_context(session, current_user.facility_id)
            yield session
        except Exception:
            await session.rollback()
            raise
