"""Per-facility overrides of the baseline role permission matrix.

The baseline lives in ``app.auth.permissions.ROLE_PERMISSIONS`` so the system
is safe out of the box.  This table is how a hospital changes its mind without
waiting for a release: a row says "at this facility, this role may (or may not)
do this".  A row with ``facility_id IS NULL`` is the platform default that
every facility inherits, which is how migration 029 seeds the baseline.

Only ``app.auth.permissions.resolve_permissions`` reads this table, and it
reads it as an *override* - a missing row means "keep the baseline", not
"deny".  That is deliberate: a facility that never touches the table still
gets correct access control, and a table that somehow lost its rows degrades
to the shipped baseline instead of locking everyone out.

The API only ever reads here, so the model is intentionally plain.  The
uniqueness rule (one row per role + permission + facility, ignoring soft
deletes) is an expression index that PostgreSQL understands and SQLite does
not, so migration 029 owns it and this model does not repeat it.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RolePermission(Base):
    """One grant or denial, for one role, at one facility (or globally)."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ix_role_permissions_lookup", "role", "permission"),
        Index("ix_role_permissions_facility", "facility_id"),
    )

    # SQLAlchemy requires a primary key on every mapped class. The table has
    # one - a UUID the database defaults - but it still has to be declared
    # here, and every other model in this codebase sets it client-side too.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL means the platform default every facility inherits; a facility UUID
    # means this hospital's own statement about the role.
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(96), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
