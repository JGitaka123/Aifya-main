"""
Pydantic schemas for licensing, tiers, entitlements, telemetry, and updates.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ─── Tier Definitions ─────────────────────────────────────────────────────────

SubscriptionTier = Literal["community", "professional", "enterprise", "government"]
BillingCycle = Literal["monthly", "annual", "perpetual"]
UpdateChannel = Literal["stable", "beta", "canary"]

# Core modules available in community tier
COMMUNITY_MODULES = [
    "patients",
    "encounters",
    "opd",
    "vitals",
    "billing",
]

# Professional adds clinical depth
PROFESSIONAL_MODULES = [
    *COMMUNITY_MODULES,
    "ipd",
    "pharmacy",
    "laboratory",
    "radiology",
    "appointments",
    "mch",
    "dental",
    "emergency",
    "theatre",
    "referrals",
    "insurance",
    "inventory",
    "finance",
    "hr",
    "reports",
]

# Enterprise adds AI + analytics + integrations
ENTERPRISE_MODULES = [
    *PROFESSIONAL_MODULES,
    "scribe_ai",
    "claimflow_ai",
    "clinical_trials",
    "analytics",
    "communications",
    "dhis2_sync",
    "fhir",
    "fhir_api",
    "mpesa_billing",
    "api_access",
]

# Government = Enterprise + county-level features
GOVERNMENT_MODULES = [*ENTERPRISE_MODULES, "multi_facility", "county_dashboard", "aggregate_reporting", "facility_comparison"]

TIER_ENTITLEMENTS: dict[str, dict] = {
    "community": {
        "max_users": 5,
        "max_patients": 500,
        "max_facilities": 1,
        "enabled_modules": COMMUNITY_MODULES,
        "feature_flags": {
            "ai_features": False,
            "custom_reports": False,
            "api_access": False,
            "data_export": False,
            "white_label": False,
            "priority_support": False,
            "sla_guarantee": False,
            "offline_mode": True,
            "multi_language": True,
        },
        "price_monthly_kes": 0,
        "price_annual_kes": 0,
    },
    "professional": {
        "max_users": 50,
        "max_patients": 50_000,
        "max_facilities": 1,
        "enabled_modules": PROFESSIONAL_MODULES,
        "feature_flags": {
            "ai_features": False,
            "custom_reports": True,
            "api_access": False,
            "data_export": True,
            "white_label": False,
            "priority_support": False,
            "sla_guarantee": False,
            "offline_mode": True,
            "multi_language": True,
        },
        "price_monthly_kes": 25_000_00,  # KES 25,000/mo in cents
        "price_annual_kes": 250_000_00,  # KES 250,000/yr in cents
    },
    "enterprise": {
        "max_users": 500,
        "max_patients": 500_000,
        "max_facilities": 10,
        "enabled_modules": ENTERPRISE_MODULES,
        "feature_flags": {
            "ai_features": True,
            "custom_reports": True,
            "api_access": True,
            "data_export": True,
            "white_label": True,
            "priority_support": True,
            "sla_guarantee": True,
            "offline_mode": True,
            "multi_language": True,
        },
        "price_monthly_kes": 150_000_00,  # KES 150,000/mo
        "price_annual_kes": 1_500_000_00,  # KES 1,500,000/yr
    },
    "government": {
        "max_users": 10_000,
        "max_patients": 5_000_000,
        "max_facilities": 500,
        "enabled_modules": GOVERNMENT_MODULES,
        "feature_flags": {
            "ai_features": True,
            "custom_reports": True,
            "api_access": True,
            "data_export": True,
            "white_label": True,
            "priority_support": True,
            "sla_guarantee": True,
            "offline_mode": True,
            "multi_language": True,
        },
        "price_monthly_kes": 0,  # Custom pricing per county
        "price_annual_kes": 0,
    },
}


# ─── License Schemas ──────────────────────────────────────────────────────────

class LicenseCreate(BaseModel):
    """Create a new license for a facility."""

    facility_id: str
    tier: SubscriptionTier = "community"
    billing_cycle: BillingCycle = "monthly"
    expires_at: datetime | None = None
    issued_by: str | None = None
    notes: str | None = None


class LicenseResponse(BaseModel):
    """License details returned to facility.

    The full license_key is never exposed in API responses.
    Only a masked prefix is returned for identification purposes.
    """

    id: str
    facility_id: str
    license_key_prefix: str = Field(
        description="Masked license key showing only the first 8 characters"
    )
    tier: str
    max_users: int
    max_patients: int
    max_facilities: int
    enabled_modules: list[str]
    feature_flags: dict[str, bool]
    billing_cycle: str
    price_cents: int
    currency: str
    issued_at: datetime
    expires_at: datetime | None
    grace_period_days: int
    is_active: bool
    last_heartbeat_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_license(cls, license_key: str, **kwargs: object) -> "LicenseResponse":
        """Create a LicenseResponse with the license key masked.

        @param license_key: The full license key to mask.
        @param kwargs: All other LicenseResponse fields.
        @returns: LicenseResponse with only the key prefix exposed.
        """
        masked = license_key[:8] + "..." if len(license_key) > 8 else license_key
        return cls(license_key_prefix=masked, **kwargs)


class LicenseValidation(BaseModel):
    """License validation response — returned on heartbeat."""

    is_valid: bool
    tier: str
    enabled_modules: list[str]
    feature_flags: dict[str, bool]
    max_users: int
    max_patients: int
    expires_at: datetime | None
    days_remaining: int | None = None
    in_grace_period: bool = False
    upgrade_available: bool = False
    upgrade_message: str | None = None
    latest_version: str | None = None
    update_required: bool = False


class LicenseUpgrade(BaseModel):
    """Request to upgrade a facility's tier."""

    new_tier: SubscriptionTier
    billing_cycle: BillingCycle = "monthly"
    payment_reference: str | None = None  # M-Pesa or bank reference


class HeartbeatRequest(BaseModel):
    """Facility heartbeat payload — sent periodically."""

    license_key: str
    current_version: str
    active_users: int = 0
    total_patients: int = 0
    modules_used: list[str] = Field(default_factory=list)


# ─── Telemetry Schemas ────────────────────────────────────────────────────────

class TelemetryPayload(BaseModel):
    """Daily usage telemetry from facility — no PII."""

    active_users: int = 0
    total_patients: int = 0
    encounters_today: int = 0
    prescriptions_today: int = 0
    lab_orders_today: int = 0
    admissions_today: int = 0
    billing_total_cents: int = 0
    ai_requests_today: int = 0
    modules_used: list[str] = Field(default_factory=list)
    api_latency_p95_ms: int | None = None
    error_count: int = 0
    offline_sync_queue_size: int = 0
    app_version: str | None = None
    db_version: str | None = None


class TelemetryResponse(BaseModel):
    """Ack from telemetry ingestion."""

    received: bool = True
    message: str = "Telemetry recorded"


# ─── Update Schemas ───────────────────────────────────────────────────────────

class UpdateCheckResponse(BaseModel):
    """Response to update check — tells facility if update available."""

    update_available: bool
    current_version: str
    latest_version: str | None = None
    is_critical: bool = False
    is_mandatory: bool = False
    title: str | None = None
    changelog: str | None = None
    download_url: str | None = None
    docker_tag: str | None = None
    db_migration_required: bool = False
    min_version: str | None = None


class AppUpdateCreate(BaseModel):
    """Publish a new application update."""

    version: str
    channel: UpdateChannel = "stable"
    min_tier: SubscriptionTier = "community"
    title: str
    changelog: str
    changelog_sw: str | None = None
    is_critical: bool = False
    is_mandatory: bool = False
    download_url: str | None = None
    docker_tag: str | None = None
    db_migration_required: bool = False
    min_version: str | None = None


class AppUpdateResponse(BaseModel):
    """Published update details."""

    id: str
    version: str
    channel: str
    min_tier: str
    title: str
    changelog: str
    is_critical: bool
    is_mandatory: bool
    is_published: bool
    published_at: datetime | None

    model_config = {"from_attributes": True}


# ─── Admin Schemas ────────────────────────────────────────────────────────────

class FacilityLicenseSummary(BaseModel):
    """Admin view of facility licenses."""

    total_facilities: int
    by_tier: dict[str, int]  # {"community": 45, "professional": 12, ...}
    active_licenses: int
    expired_licenses: int
    expiring_soon: int  # within 30 days
    total_mrr_cents: int  # Monthly Recurring Revenue in cents
    overdue_heartbeats: int  # facilities that haven't phoned home


class DataExportRequest(BaseModel):
    """Request to export facility data — tier-gated."""

    export_format: Literal["csv", "fhir_json", "hl7"] = "csv"
    modules: list[str] = Field(default_factory=list)
    date_from: datetime | None = None
    date_to: datetime | None = None


class DataExportResponse(BaseModel):
    """Export job status."""

    export_id: str
    status: Literal["queued", "processing", "ready", "expired"]
    download_url: str | None = None
    expires_at: datetime | None = None
    record_count: int | None = None
