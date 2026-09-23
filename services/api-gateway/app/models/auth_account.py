"""Login credentials for Aifya-hosted (internal) authentication.

Stored outside the tenant tables on purpose: staff rows are protected by
row-level security keyed on facility_id, so a global lookup by email for
login would be invisible. auth_accounts is a platform-level table (like the
Keycloak user store it replaces) that simply maps a unique email to its
staff/facility pair. It contains only credentials metadata, never clinical
data, and is not facility-scoped.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthAccount(Base):
    """A platform-level login account bound to one staff member."""

    __tablename__ = "auth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facilities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_auth_accounts_email_lower",
            func.lower(email),  # type: ignore[arg-type]
            unique=True,
        ),
    )
