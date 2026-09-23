"""
License management, validation, telemetry ingestion, and update checking.

This is the commercial control plane — enforces tiers, captures usage,
and manages the upgrade/update lifecycle.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.licensing import (
    AppUpdate,
    FacilityLicense,
    FacilityUpdateStatus,
    UsageTelemetry,
)
from app.models.patient import Patient
from app.schemas.licensing import (
    TIER_ENTITLEMENTS,
    AppUpdateCreate,
    DataExportRequest,
    HeartbeatRequest,
    LicenseCreate,
    LicenseUpgrade,
    LicenseValidation,
    TelemetryPayload,
)


def _generate_license_key(tier: str) -> str:
    """
    Generate a unique, signed license key.

    @param tier: Subscription tier name
    @returns License key string: AIFYA-TIER-XXXXXXXX-XXXX
    """
    prefix = f"AIFYA-{tier.upper()}"
    random_part = secrets.token_hex(8).upper()
    raw = f"{prefix}-{random_part}"
    sig = hmac.new(
        settings.secret_key.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()[:8].upper()
    return f"{raw}-{sig}"


def _verify_license_key(key: str) -> bool:
    """
    Verify that a license key signature is valid.

    @param key: License key to verify
    @returns True if signature matches
    """
    parts = key.rsplit("-", 1)
    if len(parts) != 2:
        return False
    raw, sig = parts
    expected = hmac.new(
        settings.secret_key.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()[:8].upper()
    return hmac.compare_digest(sig, expected)


class LicensingService:
    """Service for license management and commercial operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─── License CRUD ─────────────────────────────────────────────────────

    async def create_license(self, data: LicenseCreate) -> FacilityLicense:
        """
        Issue a new license for a facility.

        @param data: License creation payload
        @returns Created license record
        """
        tier = data.tier
        entitlements = TIER_ENTITLEMENTS[tier]

        # Deactivate any existing active license for this facility
        existing = await self.db.execute(
            select(FacilityLicense).where(
                FacilityLicense.facility_id == uuid.UUID(data.facility_id),
                FacilityLicense.is_active == True,  # noqa: E712
            )
        )
        for old_license in existing.scalars().all():
            old_license.is_active = False

        license_obj = FacilityLicense(
            facility_id=uuid.UUID(data.facility_id),
            license_key=_generate_license_key(tier),
            tier=tier,
            max_users=entitlements["max_users"],
            max_patients=entitlements["max_patients"],
            max_facilities=entitlements["max_facilities"],
            enabled_modules=entitlements["enabled_modules"],
            feature_flags=entitlements["feature_flags"],
            billing_cycle=data.billing_cycle,
            price_cents=entitlements[
                "price_annual_kes" if data.billing_cycle == "annual" else "price_monthly_kes"
            ],
            expires_at=(
                data.expires_at
                if data.expires_at is not None or data.billing_cycle == "perpetual"
                else datetime.now(UTC)
                + timedelta(days=365 if data.billing_cycle == "annual" else 30)
            ),
            issued_by=data.issued_by,
            notes=data.notes,
        )

        self.db.add(license_obj)
        await self.db.flush()
        await self.db.refresh(license_obj)
        return license_obj

    async def get_facility_license(self, facility_id: uuid.UUID) -> FacilityLicense | None:
        """
        Get the active license for a facility.

        @param facility_id: Facility UUID
        @returns Active license or None
        """
        result = await self.db.execute(
            select(FacilityLicense).where(
                FacilityLicense.facility_id == facility_id,
                FacilityLicense.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def ensure_license(
        self,
        facility_id: uuid.UUID,
        tier: str,
        notes: str | None = None,
    ) -> bool:
        """
        Issue an active perpetual license when the facility has none.

        @param facility_id: Facility UUID
        @param tier: Subscription tier to issue
        @param notes: Optional note recorded on the license
        @returns True when a new license was created, False if one already exists
        """
        if await self.get_facility_license(facility_id) is not None:
            return False
        await self.create_license(
            LicenseCreate(
                facility_id=str(facility_id),
                tier=tier,  # type: ignore[arg-type] -- validated by LicenseCreate
                billing_cycle="perpetual",
                notes=notes,
            )
        )
        return True

    async def validate_license(self, facility_id: uuid.UUID) -> LicenseValidation:
        """
        Validate a facility's license and return entitlements.
        Called on every authenticated request via middleware.

        @param facility_id: Facility UUID from JWT
        @returns License validation result with entitlements
        """
        license_obj = await self.get_facility_license(facility_id)

        if not license_obj:
            # No license = community tier (free, limited)
            community = TIER_ENTITLEMENTS["community"]
            return LicenseValidation(
                is_valid=True,
                tier="community",
                enabled_modules=community["enabled_modules"],
                feature_flags=community["feature_flags"],
                max_users=community["max_users"],
                max_patients=community["max_patients"],
                expires_at=None,
                days_remaining=None,
            )

        now = datetime.now(UTC)
        is_expired = license_obj.expires_at and license_obj.expires_at < now

        # Grace period: still works but with warning
        in_grace = False
        if is_expired and license_obj.expires_at:
            grace_end = license_obj.expires_at + timedelta(days=license_obj.grace_period_days)
            in_grace = now < grace_end

        days_remaining = None
        if license_obj.expires_at:
            delta = license_obj.expires_at - now
            days_remaining = max(0, delta.days)

        is_valid = not is_expired or in_grace

        # If fully expired (past grace), downgrade to community
        if is_expired and not in_grace:
            community = TIER_ENTITLEMENTS["community"]
            return LicenseValidation(
                is_valid=False,
                tier="community",
                enabled_modules=community["enabled_modules"],
                feature_flags=community["feature_flags"],
                max_users=community["max_users"],
                max_patients=community["max_patients"],
                expires_at=license_obj.expires_at,
                days_remaining=0,
                in_grace_period=False,
                upgrade_available=True,
                upgrade_message="Your license has expired. Renew to restore full access.",
            )

        return LicenseValidation(
            is_valid=is_valid,
            tier=license_obj.tier,
            enabled_modules=license_obj.enabled_modules,
            feature_flags=license_obj.feature_flags,
            max_users=license_obj.max_users,
            max_patients=license_obj.max_patients,
            expires_at=license_obj.expires_at,
            days_remaining=days_remaining,
            in_grace_period=in_grace,
            upgrade_available=license_obj.tier in ("community", "professional"),
            upgrade_message=(
                f"License expires in {days_remaining} days. Renew now."
                if days_remaining is not None and days_remaining <= 30
                else None
            ),
        )

    async def upgrade_license(
        self, facility_id: uuid.UUID, data: LicenseUpgrade, upgraded_by: str
    ) -> FacilityLicense:
        """
        Upgrade a facility to a higher tier.

        @param facility_id: Facility UUID
        @param data: Upgrade details
        @param upgraded_by: Admin who processed the upgrade
        @returns New license with upgraded entitlements
        """
        create_data = LicenseCreate(
            facility_id=str(facility_id),
            tier=data.new_tier,
            billing_cycle=data.billing_cycle,
            issued_by=upgraded_by,
            notes=f"Upgraded. Payment ref: {data.payment_reference}" if data.payment_reference else "Upgraded",
        )
        return await self.create_license(create_data)

    # ─── Heartbeat & Telemetry ────────────────────────────────────────────

    async def process_heartbeat(self, data: HeartbeatRequest) -> LicenseValidation:
        """
        Process a facility heartbeat — validates license, updates tracking,
        and returns current entitlements.

        @param data: Heartbeat payload from facility
        @returns License validation with entitlements
        """
        if not _verify_license_key(data.license_key):
            community = TIER_ENTITLEMENTS["community"]
            return LicenseValidation(
                is_valid=False,
                tier="community",
                enabled_modules=community["enabled_modules"],
                feature_flags=community["feature_flags"],
                max_users=community["max_users"],
                max_patients=community["max_patients"],
                expires_at=None,
                upgrade_message="Invalid license key.",
            )

        # Find license by key
        result = await self.db.execute(
            select(FacilityLicense).where(
                FacilityLicense.license_key == data.license_key,
                FacilityLicense.is_active == True,  # noqa: E712
            )
        )
        license_obj = result.scalar_one_or_none()
        if not license_obj:
            community = TIER_ENTITLEMENTS["community"]
            return LicenseValidation(
                is_valid=False,
                tier="community",
                enabled_modules=community["enabled_modules"],
                feature_flags=community["feature_flags"],
                max_users=community["max_users"],
                max_patients=community["max_patients"],
                expires_at=None,
                upgrade_message="License not found or deactivated.",
            )

        # Update heartbeat timestamp
        license_obj.last_heartbeat_at = datetime.now(UTC)
        await self.db.flush()

        # Update facility version tracking
        await self._update_facility_version(license_obj.facility_id, data.current_version)

        # Check for available updates
        validation = await self.validate_license(license_obj.facility_id)

        latest = await self._get_latest_update(license_obj.tier)
        if latest and latest.version != data.current_version:
            validation.latest_version = latest.version
            validation.update_required = latest.is_mandatory

        return validation

    async def record_telemetry(
        self, facility_id: uuid.UUID, data: TelemetryPayload
    ) -> None:
        """
        Record daily usage telemetry from a facility.

        @param facility_id: Facility UUID
        @param data: Telemetry payload — no PII
        """
        telemetry = UsageTelemetry(
            facility_id=facility_id,
            recorded_date=datetime.now(UTC),
            active_users=data.active_users,
            total_patients=data.total_patients,
            encounters_today=data.encounters_today,
            prescriptions_today=data.prescriptions_today,
            lab_orders_today=data.lab_orders_today,
            admissions_today=data.admissions_today,
            billing_total_cents=data.billing_total_cents,
            ai_requests_today=data.ai_requests_today,
            modules_used=data.modules_used,
            api_latency_p95_ms=data.api_latency_p95_ms,
            error_count=data.error_count,
            offline_sync_queue_size=data.offline_sync_queue_size,
            app_version=data.app_version,
            db_version=data.db_version,
        )
        self.db.add(telemetry)
        await self.db.flush()

    # ─── Updates ──────────────────────────────────────────────────────────

    async def check_for_updates(
        self, facility_id: uuid.UUID, current_version: str
    ) -> dict:
        """
        Check if updates are available for a facility.

        @param facility_id: Facility UUID
        @param current_version: Currently running version
        @returns Update check result
        """
        license_obj = await self.get_facility_license(facility_id)
        tier = license_obj.tier if license_obj else "community"

        latest = await self._get_latest_update(tier)
        if not latest or latest.version == current_version:
            return {
                "update_available": False,
                "current_version": current_version,
            }

        return {
            "update_available": True,
            "current_version": current_version,
            "latest_version": latest.version,
            "is_critical": latest.is_critical,
            "is_mandatory": latest.is_mandatory,
            "title": latest.title,
            "changelog": latest.changelog,
            "download_url": latest.download_url,
            "docker_tag": latest.docker_tag,
            "db_migration_required": latest.db_migration_required,
            "min_version": latest.min_version,
        }

    async def publish_update(self, data: AppUpdateCreate) -> AppUpdate:
        """
        Publish a new application update.

        @param data: Update details
        @returns Created update record
        """
        update = AppUpdate(
            version=data.version,
            channel=data.channel,
            min_tier=data.min_tier,
            title=data.title,
            changelog=data.changelog,
            changelog_sw=data.changelog_sw,
            is_critical=data.is_critical,
            is_mandatory=data.is_mandatory,
            download_url=data.download_url,
            docker_tag=data.docker_tag,
            db_migration_required=data.db_migration_required,
            min_version=data.min_version,
            is_published=True,
            published_at=datetime.now(UTC),
        )
        self.db.add(update)
        await self.db.flush()
        await self.db.refresh(update)
        return update

    # ─── Entitlement Checks ───────────────────────────────────────────────

    async def check_module_access(
        self, facility_id: uuid.UUID, module: str
    ) -> bool:
        """
        Check if a facility has access to a specific module.

        @param facility_id: Facility UUID
        @param module: Module name to check
        @returns True if module is enabled for this tier
        """
        validation = await self.validate_license(facility_id)
        return module in validation.enabled_modules

    async def check_feature_flag(
        self, facility_id: uuid.UUID, flag: str
    ) -> bool:
        """
        Check if a feature flag is enabled for a facility.

        @param facility_id: Facility UUID
        @param flag: Feature flag name
        @returns True if flag is enabled
        """
        validation = await self.validate_license(facility_id)
        return validation.feature_flags.get(flag, False)

    async def check_patient_limit(self, facility_id: uuid.UUID) -> dict:
        """
        Check if facility has reached patient registration limit.

        @param facility_id: Facility UUID
        @returns Dict with limit info and whether limit reached
        """
        validation = await self.validate_license(facility_id)

        count_result = await self.db.execute(
            select(func.count(Patient.id)).where(
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        current_count = count_result.scalar_one()

        return {
            "current": current_count,
            "limit": validation.max_patients,
            "remaining": max(0, validation.max_patients - current_count),
            "limit_reached": current_count >= validation.max_patients,
            "tier": validation.tier,
            "upgrade_available": validation.upgrade_available,
        }

    # ─── Data Export (Tier-Gated) ─────────────────────────────────────────

    async def validate_export_access(
        self, facility_id: uuid.UUID, request: DataExportRequest
    ) -> tuple[bool, str]:
        """
        Validate if facility can export data based on tier.

        @param facility_id: Facility UUID
        @param request: Export request details
        @returns Tuple of (allowed, reason)
        """
        validation = await self.validate_license(facility_id)

        if not validation.feature_flags.get("data_export", False):
            return False, (
                "Data export is not available on your current plan. "
                "Upgrade to Professional or higher to export your data."
            )

        # FHIR export only on Enterprise+
        if request.export_format == "fhir_json" and validation.tier not in ("enterprise", "government"):
            return False, "FHIR export requires Enterprise tier or higher."

        return True, "Export permitted"

    # ─── Admin Summary ────────────────────────────────────────────────────

    async def get_admin_summary(self) -> dict:
        """
        Get aggregate license summary for Aifya admin dashboard.

        @returns Summary dict with tier breakdown, MRR, health metrics
        """
        now = datetime.now(UTC)

        # Count by tier
        tier_counts = await self.db.execute(
            select(FacilityLicense.tier, func.count(FacilityLicense.id))
            .where(FacilityLicense.is_active == True)  # noqa: E712
            .group_by(FacilityLicense.tier)
        )
        by_tier = {row[0]: row[1] for row in tier_counts.all()}

        # Active vs expired
        active_result = await self.db.execute(
            select(func.count(FacilityLicense.id)).where(
                FacilityLicense.is_active == True,  # noqa: E712
                (FacilityLicense.expires_at > now) | (FacilityLicense.expires_at.is_(None)),
            )
        )
        active_count = active_result.scalar_one()

        expired_result = await self.db.execute(
            select(func.count(FacilityLicense.id)).where(
                FacilityLicense.is_active == True,  # noqa: E712
                FacilityLicense.expires_at <= now,
            )
        )
        expired_count = expired_result.scalar_one()

        # Expiring within 30 days
        expiring_result = await self.db.execute(
            select(func.count(FacilityLicense.id)).where(
                FacilityLicense.is_active == True,  # noqa: E712
                FacilityLicense.expires_at > now,
                FacilityLicense.expires_at <= now + timedelta(days=30),
            )
        )
        expiring_count = expiring_result.scalar_one()

        # MRR
        mrr_result = await self.db.execute(
            select(func.coalesce(func.sum(FacilityLicense.price_cents), 0)).where(
                FacilityLicense.is_active == True,  # noqa: E712
                FacilityLicense.billing_cycle == "monthly",
            )
        )
        mrr = mrr_result.scalar_one()

        # Overdue heartbeats (>48 hours)
        heartbeat_threshold = now - timedelta(hours=48)
        overdue_result = await self.db.execute(
            select(func.count(FacilityLicense.id)).where(
                FacilityLicense.is_active == True,  # noqa: E712
                (FacilityLicense.last_heartbeat_at < heartbeat_threshold)
                | (FacilityLicense.last_heartbeat_at.is_(None)),
            )
        )
        overdue_count = overdue_result.scalar_one()

        total = sum(by_tier.values())

        return {
            "total_facilities": total,
            "by_tier": by_tier,
            "active_licenses": active_count,
            "expired_licenses": expired_count,
            "expiring_soon": expiring_count,
            "total_mrr_cents": mrr,
            "overdue_heartbeats": overdue_count,
        }

    # ─── Private Helpers ──────────────────────────────────────────────────

    async def _get_latest_update(self, tier: str) -> AppUpdate | None:
        """Get the latest published update for a tier."""
        tier_order = ["community", "professional", "enterprise", "government"]
        allowed_tiers = tier_order[: tier_order.index(tier) + 1]

        result = await self.db.execute(
            select(AppUpdate)
            .where(
                AppUpdate.is_published == True,  # noqa: E712
                AppUpdate.channel == "stable",
                AppUpdate.min_tier.in_(allowed_tiers),
            )
            .order_by(AppUpdate.published_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _update_facility_version(
        self, facility_id: uuid.UUID, version: str
    ) -> None:
        """Update facility's current version tracking."""
        result = await self.db.execute(
            select(FacilityUpdateStatus).where(
                FacilityUpdateStatus.facility_id == facility_id
            )
        )
        status_obj = result.scalar_one_or_none()
        now = datetime.now(UTC)

        if status_obj:
            status_obj.current_version = version
            status_obj.last_update_check = now
        else:
            status_obj = FacilityUpdateStatus(
                facility_id=facility_id,
                current_version=version,
                last_update_check=now,
            )
            self.db.add(status_obj)

        await self.db.flush()
