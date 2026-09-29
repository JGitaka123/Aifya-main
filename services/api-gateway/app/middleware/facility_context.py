"""
Middleware to publish request context to the PostgreSQL session.

Sets `app.current_facility_id` so the row-level-security policies can filter
rows per facility, and the `app.current_user_*` settings that the clinical
audit trigger (migration 026) reads to attribute each changed row to the API
user who changed it. Every setting is transaction-local.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_facility_context(
    db: AsyncSession,
    facility_id: str,
    *,
    user_id: str | uuid.UUID | None = None,
    email: str | None = None,
    roles: Iterable[str] | None = None,
) -> None:
    """
    Set the tenant and acting-user context for the current DB session.

    A blank argument never overwrites a value the session already holds, so the
    order in which FastAPI happens to resolve the authentication dependency and
    the database dependency cannot silently blank the acting user and leave the
    clinical audit trail unattributed. The facility is always supplied, so it is
    written unconditionally.

    @param db: Async database session
    @param facility_id: Facility UUID string from the JWT
    @param user_id: Acting user id, recorded as audit_logs.actor_user_id
    @param email: Acting user email, recorded as audit_logs.actor_email
    @param roles: Acting user roles, recorded as audit_logs.actor_roles
    """
    normalized_facility_id = str(uuid.UUID(str(facility_id)))
    db.info["facility_id"] = normalized_facility_id

    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return

    role_list = list(roles) if roles else []
    await db.execute(
        text(
            "SELECT set_config('app.current_facility_id', :facility_id, true), "
            "set_config('app.current_user_id', COALESCE(NULLIF(:user_id, ''), "
            "current_setting('app.current_user_id', true), ''), true), "
            "set_config('app.current_user_email', COALESCE(NULLIF(:email, ''), "
            "current_setting('app.current_user_email', true), ''), true), "
            "set_config('app.current_user_roles', COALESCE(NULLIF(:roles, ''), "
            "current_setting('app.current_user_roles', true), ''), true)"
        ),
        {
            "facility_id": normalized_facility_id,
            "user_id": str(user_id) if user_id else "",
            "email": email or "",
            "roles": ",".join(role_list),
        },
    )
