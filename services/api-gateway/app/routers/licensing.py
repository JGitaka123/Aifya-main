"""
Licensing, heartbeat, telemetry, and update endpoints.

Public endpoints (no auth): heartbeat, update check
Authenticated endpoints: license info, telemetry, export
Admin endpoints: create/upgrade licenses, publish updates, admin summary
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user, require_roles
from app.database import get_db
from app.schemas.licensing import (
    AppUpdateCreate,
    AppUpdateResponse,
    DataExportRequest,
    HeartbeatRequest,
    LicenseCreate,
    LicenseResponse,
    LicenseUpgrade,
    LicenseValidation,
    TelemetryPayload,
    TelemetryResponse,
    UpdateCheckResponse,
)
from app.services.licensing_service import LicensingService

router = APIRouter()


# ─── Public Endpoints (no auth — called by facility instances) ────────────────

@router.post("/heartbeat", response_model=LicenseValidation)
async def heartbeat(
    data: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
) -> LicenseValidation:
    """
    Facility heartbeat — validates license and returns entitlements.
    Called periodically by each facility instance (every 24h default).
    No auth required since the license_key itself is the credential.

    @param data: Heartbeat payload with license key and usage info
    @param db: Database session
    @returns License validation with entitlements
    """
    service = LicensingService(db)
    return await service.process_heartbeat(data)


@router.post("/update-check", response_model=UpdateCheckResponse)
async def check_for_updates(
    current_version: str,
    facility_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> UpdateCheckResponse:
    """
    Check if application updates are available.

    @param current_version: Currently running semver version
    @param facility_id: Optional facility UUID for tier-specific updates
    @param db: Database session
    @returns Update availability info
    """
    service = LicensingService(db)
    result = await service.check_for_updates(
        facility_id=facility_id or uuid.UUID(int=0),
        current_version=current_version,
    )
    return UpdateCheckResponse(**result)


# ─── Authenticated Endpoints ──────────────────────────────────────────────────

@router.get("/license", response_model=LicenseValidation)
async def get_my_license(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LicenseValidation:
    """
    Get current facility's license and entitlements.

    @param db: Database session
    @param current_user: Authenticated user
    @returns License validation with full entitlements
    """
    service = LicensingService(db)
    return await service.validate_license(current_user.facility_id)


@router.get("/license/patient-limit")
async def check_patient_limit(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Check if facility has reached patient registration limit.

    @param db: Database session
    @param current_user: Authenticated user
    @returns Patient limit info
    """
    service = LicensingService(db)
    return await service.check_patient_limit(current_user.facility_id)


@router.get("/license/module/{module}")
async def check_module_access(
    module: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str | bool]:
    """
    Check if facility has access to a specific module.

    @param module: Module name
    @param db: Database session
    @param current_user: Authenticated user
    @returns Access result
    """
    service = LicensingService(db)
    allowed = await service.check_module_access(current_user.facility_id, module)
    return {"module": module, "allowed": allowed}


@router.post("/telemetry", response_model=TelemetryResponse)
async def submit_telemetry(
    data: TelemetryPayload,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TelemetryResponse:
    """
    Submit daily usage telemetry — no PII.

    @param data: Telemetry payload
    @param db: Database session
    @param current_user: Authenticated user
    @returns Ack response
    """
    service = LicensingService(db)
    await service.record_telemetry(current_user.facility_id, data)
    return TelemetryResponse()


@router.post("/export/validate")
async def validate_export(
    data: DataExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> dict:
    """
    Validate if data export is allowed for this facility's tier.

    @param data: Export request details
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Validation result
    """
    service = LicensingService(db)
    allowed, reason = await service.validate_export_access(
        current_user.facility_id, data
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )
    return {"allowed": True, "message": reason}


# ─── Admin Endpoints (Aifya HQ only) ─────────────────────────────────────────

@router.post("/admin/licenses", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
async def create_license(
    data: LicenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("super_admin")),
) -> LicenseResponse:
    """
    Issue a new license for a facility (Aifya admin only).

    @param data: License creation payload
    @param db: Database session
    @param current_user: Aifya super admin
    @returns Created license
    """
    service = LicensingService(db)
    license_obj = await service.create_license(data)
    return LicenseResponse.from_license(
        license_key=license_obj.license_key,
        id=str(license_obj.id),
        facility_id=str(license_obj.facility_id),
        tier=license_obj.tier,
        max_users=license_obj.max_users,
        max_patients=license_obj.max_patients,
        max_facilities=license_obj.max_facilities,
        enabled_modules=license_obj.enabled_modules,
        feature_flags=license_obj.feature_flags,
        billing_cycle=license_obj.billing_cycle,
        price_cents=license_obj.price_cents,
        currency=license_obj.currency,
        issued_at=license_obj.issued_at,
        expires_at=license_obj.expires_at,
        grace_period_days=license_obj.grace_period_days,
        is_active=license_obj.is_active,
        last_heartbeat_at=license_obj.last_heartbeat_at,
    )


@router.post("/admin/licenses/{facility_id}/upgrade", response_model=LicenseResponse)
async def upgrade_license(
    facility_id: uuid.UUID,
    data: LicenseUpgrade,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("super_admin")),
) -> LicenseResponse:
    """
    Upgrade a facility to a higher tier (Aifya admin only).

    @param facility_id: Facility to upgrade
    @param data: Upgrade details
    @param db: Database session
    @param current_user: Aifya super admin
    @returns New upgraded license
    """
    service = LicensingService(db)
    license_obj = await service.upgrade_license(
        facility_id, data, current_user.name
    )
    return LicenseResponse.from_license(
        license_key=license_obj.license_key,
        id=str(license_obj.id),
        facility_id=str(license_obj.facility_id),
        tier=license_obj.tier,
        max_users=license_obj.max_users,
        max_patients=license_obj.max_patients,
        max_facilities=license_obj.max_facilities,
        enabled_modules=license_obj.enabled_modules,
        feature_flags=license_obj.feature_flags,
        billing_cycle=license_obj.billing_cycle,
        price_cents=license_obj.price_cents,
        currency=license_obj.currency,
        issued_at=license_obj.issued_at,
        expires_at=license_obj.expires_at,
        grace_period_days=license_obj.grace_period_days,
        is_active=license_obj.is_active,
        last_heartbeat_at=license_obj.last_heartbeat_at,
    )


@router.get("/admin/summary")
async def admin_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("super_admin")),
) -> dict:
    """
    Get aggregate licensing summary (Aifya admin dashboard).

    @param db: Database session
    @param current_user: Aifya super admin
    @returns Summary with tier breakdown, MRR, health metrics
    """
    service = LicensingService(db)
    return await service.get_admin_summary()


@router.post("/admin/updates", response_model=AppUpdateResponse, status_code=status.HTTP_201_CREATED)
async def publish_update(
    data: AppUpdateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("super_admin")),
) -> AppUpdateResponse:
    """
    Publish a new application update (Aifya admin only).

    @param data: Update details
    @param db: Database session
    @param current_user: Aifya super admin
    @returns Published update record
    """
    service = LicensingService(db)
    update = await service.publish_update(data)
    return AppUpdateResponse.model_validate(update)
