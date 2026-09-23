"""Facility onboarding (gated sign-up) + staff invite endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.auth.dependencies import require_roles
from app.config import settings
from app.database import get_db
from app.schemas.onboarding import (
    ApproveFacilityResponse,
    FacilitySignupRequest,
    FacilitySignupResponse,
    PendingFacility,
    StaffInviteRequest,
    StaffInviteResponse,
)
from app.services.onboarding_service import (
    OnboardingError,
    OnboardingService,
    should_auto_approve,
)
from app.utils.keycloak_admin import (
    KeycloakAdminClient,
    get_keycloak_admin_client,
)

router = APIRouter()


class FacilityApprovalRequest(BaseModel):
    """Optional body for approving a facility in internal-auth mode."""

    admin_password: str | None = Field(None, min_length=8, max_length=128)


@router.post(
    "/facility-signup",
    response_model=FacilitySignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def facility_signup(
    data: FacilitySignupRequest,
    db: AsyncSession = Depends(get_db),
    admin_client: KeycloakAdminClient = Depends(get_keycloak_admin_client),
) -> FacilitySignupResponse:
    """
    Request a new facility account (public, gated). Creates a pending facility;
    a super-admin approves it before the admin user is provisioned. When
    auto-approve is on, provisioning runs immediately.

    @param data: Facility + admin details
    @param db: Database session
    @param admin_client: Keycloak admin client (used only on auto-approve)
    @returns The created facility and its onboarding status
    """
    service = OnboardingService(db)
    try:
        facility = await service.request_facility_signup(data)
        if should_auto_approve():
            if settings.auth_provider == "internal":
                if not data.admin_password:
                    raise OnboardingError(
                        "Set an admin password (at least 8 characters) to "
                        "complete your facility account."
                    )
                facility, _ = await service.approve_facility_internal(
                    facility.id, data.admin_password
                )
            else:
                facility, _ = await service.approve_facility(
                    facility.id, admin_client
                )
        await db.commit()
    except OnboardingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        # Race or a unique constraint we don't pre-check: report the clash
        # instead of leaking a 500 to the sign-up form.
        detail = str(getattr(exc, "orig", exc))
        message = (
            "A facility with this MFL code is already registered or "
            "pending review."
            if "mfl_code" in detail
            else "That facility is already registered. Check the details and "
            "try again."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=message
        ) from exc

    pending = facility.onboarding_status == "pending"
    if pending:
        message = (
            "Your facility request has been received and is pending review. "
            "The platform admin will approve it, then you can sign in."
        )
    else:
        message = (
            "Your facility is approved. Sign in with the administrator email "
            "and password you set."
            if settings.auth_provider == "internal"
            else "Facility approved. Check your email to set your password."
        )
    return FacilitySignupResponse(
        facility_id=facility.id,
        onboarding_status=facility.onboarding_status,
        message=message,
    )


@router.get("/pending", response_model=list[PendingFacility])
async def list_pending_facilities(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(*settings.super_admin_role_list)
    ),
) -> list[PendingFacility]:
    """List facilities awaiting approval (super-admin only)."""
    service = OnboardingService(db)
    return [PendingFacility.model_validate(f) for f in await service.list_pending()]


@router.post(
    "/facilities/{facility_id}/approve",
    response_model=ApproveFacilityResponse,
)
async def approve_facility(
    facility_id: uuid.UUID,
    body: FacilityApprovalRequest | None = None,
    db: AsyncSession = Depends(get_db),
    admin_client: KeycloakAdminClient = Depends(get_keycloak_admin_client),
    current_user: CurrentUser = Depends(
        require_roles(*settings.super_admin_role_list)
    ),
) -> ApproveFacilityResponse:
    """
    Approve a pending facility: activate it, seed baseline data, and provision
    the facility-admin user (super-admin only).
    """
    service = OnboardingService(db)
    try:
        if settings.auth_provider == "internal":
            facility, created = await service.approve_facility_internal(
                facility_id,
                admin_password=body.admin_password if body else None,
                approver_id=current_user.user_id,
            )
        else:
            if not admin_client.is_configured:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "User provisioning is not configured "
                        "(Keycloak admin credentials)."
                    ),
                )
            facility, created = await service.approve_facility(
                facility_id, admin_client, approver_id=current_user.user_id
            )
        await db.commit()
    except HTTPException:
        raise
    except OnboardingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return ApproveFacilityResponse(
        facility_id=facility.id,
        onboarding_status=facility.onboarding_status,
        admin_user_created=created,
        message=(
            (
                "Facility approved. The administrator can now sign in."
                if settings.auth_provider == "internal"
                else "Facility approved and admin invited."
            )
            if created
            else "Facility approved."
        ),
    )


@router.post(
    "/staff-invite",
    response_model=StaffInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_staff(
    data: StaffInviteRequest,
    db: AsyncSession = Depends(get_db),
    admin_client: KeycloakAdminClient = Depends(get_keycloak_admin_client),
    current_user: CurrentUser = Depends(require_roles("facility_admin", "admin")),
) -> StaffInviteResponse:
    """
    Invite a staff member to the caller's facility (facility-admin only).
    Creates the Keycloak user (role + facility_id + set-password email) and a
    linked Staff record.
    """
    if not admin_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User provisioning is not configured (Keycloak admin credentials).",
        )
    service = OnboardingService(db)
    try:
        staff = await service.invite_staff(
            facility_id=current_user.facility_id,
            data=data,
            admin_client=admin_client,
            inviter_id=current_user.user_id,
        )
        await db.commit()
    except OnboardingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return StaffInviteResponse(
        staff_id=staff.id,
        keycloak_user_id=staff.keycloak_user_id,
        email=staff.email,
        role=staff.role,
        message=f"{staff.email} invited — they'll get an email to set their password.",
    )
