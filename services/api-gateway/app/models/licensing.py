"""
Licensing, subscription tiers, and feature entitlements models.

Aifya commercial control plane:
- Facilities are assigned a subscription tier (community/professional/enterprise/government)
- Each tier unlocks specific modules and feature caps
- Licenses are validated via heartbeat to Aifya licensing server
- Usage telemetry is captured for product analytics and upsell signals
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FacilityLicense(Base):
    """
    License record binding a facility to a subscription tier.
    One active license per facility at a time.
    """

    __tablename__ = "facility_licenses"

    __table_args__ = (
        Index(
            "uq_facility_licenses_active",
            "facility_id",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_facility_licenses_key", "license_key", unique=True),
        Index("ix_facility_licenses_facility", "facility_id"),
        Index("ix_facility_licenses_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    license_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # HMAC-signed key: AIFYA-TIER-XXXXXXXX-XXXX

    # Tier: community | professional | enterprise | government
    tier: Mapped[str] = mapped_column(String(30), nullable=False, default="community")

    # Entitlements snapshot — denormalized from TIER_ENTITLEMENTS for offline validation
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_patients: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    max_facilities: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled_modules: Mapped[list] = mapped_column(JSONB, nullable=False)
    feature_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Billing
    billing_cycle: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )  # monthly | annual | perpetual
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")

    # Validity
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Heartbeat tracking — last time this facility phoned home
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_interval_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )

    # Metadata
    issued_by: Mapped[str | None] = mapped_column(String(255))  # admin who issued
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UsageTelemetry(Base):
    """
    Anonymous facility usage telemetry for product analytics and upsell signals.
    Captured daily — no PII, only aggregate counts.
    """

    __tablename__ = "usage_telemetry"

    __table_args__ = (
        Index("ix_usage_telemetry_facility_date", "facility_id", "recorded_date"),
        Index("ix_usage_telemetry_date", "recorded_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    recorded_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Aggregate usage counts — no PII
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    total_patients: Mapped[int] = mapped_column(Integer, default=0)
    encounters_today: Mapped[int] = mapped_column(Integer, default=0)
    prescriptions_today: Mapped[int] = mapped_column(Integer, default=0)
    lab_orders_today: Mapped[int] = mapped_column(Integer, default=0)
    admissions_today: Mapped[int] = mapped_column(Integer, default=0)
    billing_total_cents: Mapped[int] = mapped_column(Integer, default=0)
    ai_requests_today: Mapped[int] = mapped_column(Integer, default=0)

    # Module usage flags — which modules were actually used today
    modules_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # System health
    api_latency_p95_ms: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    offline_sync_queue_size: Mapped[int] = mapped_column(Integer, default=0)

    # Version info
    app_version: Mapped[str | None] = mapped_column(String(30))
    db_version: Mapped[str | None] = mapped_column(String(100))  # alembic revision

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AppUpdate(Base):
    """
    Available application updates published by Aifya HQ.
    Facilities poll for new versions and can apply updates.
    """

    __tablename__ = "app_updates"

    __table_args__ = (
        UniqueConstraint("version", name="uq_app_updates_version"),
        Index("ix_app_updates_published", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)  # semver: 1.2.3
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="stable"
    )  # stable | beta | canary
    min_tier: Mapped[str] = mapped_column(
        String(30), nullable=False, default="community"
    )  # minimum tier that gets this update

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    changelog: Mapped[str] = mapped_column(Text, nullable=False)
    changelog_sw: Mapped[str | None] = mapped_column(Text)  # Swahili changelog
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Deployment
    download_url: Mapped[str | None] = mapped_column(String(500))
    docker_tag: Mapped[str | None] = mapped_column(String(200))
    db_migration_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_version: Mapped[str | None] = mapped_column(String(30))  # min version to upgrade from

    # Status
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FacilityUpdateStatus(Base):
    """
    Tracks which version each facility is running and their update status.
    """

    __tablename__ = "facility_update_status"

    __table_args__ = (
        UniqueConstraint("facility_id", name="uq_facility_update_status_facility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    current_version: Mapped[str] = mapped_column(String(30), nullable=False)
    last_update_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    update_channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="stable"
    )
    auto_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
