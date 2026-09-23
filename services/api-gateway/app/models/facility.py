import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Facility(Base):
    """
    Healthcare facility (hospital, clinic, health centre).
    Top-level tenant — all data is scoped by facility_id.
    """

    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    facility_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # hospital, clinic, dispensary, health_centre
    keph_level: Mapped[str | None] = mapped_column(
        String(10)
    )  # Kenya Essential Package for Health level (2-6)
    mfl_code: Mapped[str | None] = mapped_column(
        String(20), unique=True
    )  # Kenya Master Facility List code

    # Location
    county: Mapped[str | None] = mapped_column(String(100))
    sub_county: Mapped[str | None] = mapped_column(String(100))
    ward: Mapped[str | None] = mapped_column(String(100))
    physical_address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()

    # Contact
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))

    # Branding
    logo_url: Mapped[str | None] = mapped_column(String(500))

    # Settings
    timezone: Mapped[str] = mapped_column(
        String(50), default="Africa/Nairobi", nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="KES", nullable=False
    )
    settings: Mapped[dict | None] = mapped_column(JSONB)

    # DHIS2 integration
    dhis2_org_unit_id: Mapped[str | None] = mapped_column(String(50))

    # Onboarding (facility sign-up): pending -> approved / rejected.
    onboarding_status: Mapped[str] = mapped_column(
        String(20), default="approved", nullable=False
    )
    admin_email: Mapped[str | None] = mapped_column(String(255))

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
