"""Facility onboarding + staff invite provisioning.

Two flows:

1. **Gated facility sign-up** — a public request creates a PENDING facility (no
   Keycloak user yet). A super-admin approves it, which activates the facility,
   seeds its baseline data (chart of accounts, lab catalog, theatres, essential
   drugs), and provisions the facility-admin user in Keycloak with an invite
   email. (With ``facility_signup_auto_approve`` the approval runs immediately.)

2. **Invite-only staff** — a facility admin invites a staff member; we create the
   Keycloak user (facility_id attribute + realm role + set-password email) and a
   linked Staff record.

Keycloak I/O goes through an injected ``KeycloakAdminClient`` so this service is
unit-testable with a fake.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.facility import Facility
from app.models.auth_account import AuthAccount
from app.models.staff import Staff
from app.middleware.facility_context import set_facility_context
from app.schemas.onboarding import FacilitySignupRequest, StaffInviteRequest
from app.services.finance.seed_data import seed_facility_finance
from app.services.lab_catalog import seed_default_lab_catalog
from app.services.licensing_service import LicensingService
from app.services.pharmacy_seed import seed_essential_drugs
from app.services.theatre_seed import seed_default_theatres
from app.utils.keycloak_admin import KeycloakAdminClient, KeycloakAdminError
from app.utils.passwords import hash_password


class OnboardingError(RuntimeError):
    """Raised for onboarding validation / provisioning failures."""


def _slug_code(name: str) -> str:
    """Derive a short uppercase facility code stem from a name."""
    letters = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    return (letters[:8] or "FAC")


class OnboardingService:
    """Facility sign-up and staff-invite provisioning."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _unique_code(self, stem: str) -> str:
        """Return a facility code based on ``stem`` that isn't already taken."""
        candidate = stem
        suffix = 1
        while True:
            exists = await self.db.scalar(
                select(Facility.id).where(Facility.code == candidate)
            )
            if not exists:
                return candidate
            suffix += 1
            candidate = f"{stem}{suffix}"

    async def request_facility_signup(
        self, data: FacilitySignupRequest
    ) -> Facility:
        """
        Create a facility sign-up request (PENDING) or auto-approve it.

        @param data: Sign-up details
        @returns The created Facility (pending, or approved if auto-approve)
        """
        existing = await self.db.scalar(
            select(Facility.id).where(
                func.lower(Facility.name) == data.facility_name.strip().lower()
            )
        )
        if existing:
            raise OnboardingError(
                "A facility with this name already exists or is pending review."
            )

        mfl_code = (data.mfl_code or "").strip() or None
        if mfl_code:
            existing_mfl = await self.db.scalar(
                select(Facility.id).where(Facility.mfl_code == mfl_code)
            )
            if existing_mfl:
                raise OnboardingError(
                    "A facility with this MFL code is already registered or "
                    "pending review."
                )

        ftype = data.facility_type.replace("health_center", "health_centre")
        onboarding = {
            "admin_first_name": data.admin_first_name,
            "admin_last_name": data.admin_last_name,
            "admin_email": str(data.admin_email),
        }
        if settings.auth_provider == "internal" and data.admin_password:
            # Stored so approval can provision the login without asking the
            # approving admin to invent (or email) a password.
            onboarding["admin_password_hash"] = hash_password(data.admin_password)
        facility = Facility(
            name=data.facility_name.strip(),
            code=await self._unique_code(_slug_code(data.facility_name)),
            facility_type=ftype,
            county=data.county,
            mfl_code=mfl_code,
            phone=data.facility_phone,
            admin_email=str(data.admin_email),
            onboarding_status="pending",
            is_active=False,
            settings={"onboarding": onboarding},
        )
        self.db.add(facility)
        await self.db.flush()
        return facility

    async def list_pending(self) -> list[Facility]:
        """Return facilities awaiting approval, oldest first."""
        rows = await self.db.execute(
            select(Facility)
            .where(Facility.onboarding_status == "pending")
            .order_by(Facility.created_at.asc())
        )
        return list(rows.scalars().all())

    async def approve_facility(
        self,
        facility_id: uuid.UUID,
        admin_client: KeycloakAdminClient,
        approver_id: uuid.UUID | None = None,
    ) -> tuple[Facility, bool]:
        """
        Approve a pending facility: activate it, seed baseline data, and
        provision the facility-admin Keycloak user + Staff record.

        @param facility_id: Facility to approve
        @param admin_client: Keycloak admin client for user provisioning
        @param approver_id: Super-admin performing the approval
        @returns (facility, admin_user_created)
        """
        facility = await self.db.get(Facility, facility_id)
        if facility is None:
            raise OnboardingError("Facility not found")
        if facility.onboarding_status == "approved":
            return facility, False

        facility.onboarding_status = "approved"
        facility.is_active = True

        # All provisioning writes below target this facility's own tables, so
        # point the session RLS context at the facility being activated.
        await set_facility_context(self.db, str(facility_id))

        # Seed baseline data so the facility is usable immediately.
        await seed_facility_finance(self.db, facility_id, approver_id)
        await seed_default_lab_catalog(self.db, facility_id, approver_id)
        await seed_default_theatres(self.db, facility_id, approver_id)
        await seed_essential_drugs(self.db, facility_id, approver_id)

        await LicensingService(self.db).ensure_license(
            facility_id=facility_id,
            tier=settings.facility_signup_tier,
            notes="Auto-issued on facility approval",
        )

        onboarding = (facility.settings or {}).get("onboarding", {})
        admin_email = facility.admin_email or onboarding.get("admin_email")
        admin_created = False
        if admin_email and admin_client.is_configured:
            user_id = await admin_client.create_user(
                email=admin_email,
                first_name=onboarding.get("admin_first_name", "Facility"),
                last_name=onboarding.get("admin_last_name", "Admin"),
                facility_id=str(facility_id),
                roles=["facility_admin"],
                send_invite_email=True,
            )
            await self._create_staff(
                facility_id=facility_id,
                keycloak_user_id=uuid.UUID(user_id),
                first_name=onboarding.get("admin_first_name", "Facility"),
                last_name=onboarding.get("admin_last_name", "Admin"),
                email=admin_email,
                role="facility_admin",
                actor_id=approver_id,
            )
            admin_created = True

        await self.db.flush()
        return facility, admin_created

    async def approve_facility_internal(
        self,
        facility_id: uuid.UUID,
        admin_password: str | None = None,
        approver_id: uuid.UUID | None = None,
    ) -> tuple[Facility, bool]:
        """
        Approve a pending facility in internal-auth mode: activate it, seed
        baseline data, then create the facility-admin Staff row plus its
        password login (auth_accounts) directly - no Keycloak or email flow.

        @param facility_id: Facility to approve
        @param admin_password: Plaintext password used only when the original
            sign-up did not record a password hash
        @param approver_id: Super-admin performing the approval
        @returns (facility, admin_user_created)
        """
        facility = await self.db.get(Facility, facility_id)
        if facility is None:
            raise OnboardingError("Facility not found")
        if facility.onboarding_status == "approved":
            return facility, False

        facility.onboarding_status = "approved"
        facility.is_active = True

        await set_facility_context(self.db, str(facility_id))

        # Seed baseline data so the facility is usable immediately.
        await seed_facility_finance(self.db, facility_id, approver_id)
        await seed_default_lab_catalog(self.db, facility_id, approver_id)
        await seed_default_theatres(self.db, facility_id, approver_id)
        await seed_essential_drugs(self.db, facility_id, approver_id)

        await LicensingService(self.db).ensure_license(
            facility_id=facility_id,
            tier=settings.facility_signup_tier,
            notes="Auto-issued on facility approval",
        )

        onboarding = (facility.settings or {}).get("onboarding", {})
        admin_email = str(
            facility.admin_email or onboarding.get("admin_email") or ""
        ).strip().lower()
        if not admin_email:
            raise OnboardingError(
                "No administrator email was recorded for this facility."
            )

        password_hash = str(onboarding.get("admin_password_hash") or "")
        if not password_hash:
            if not admin_password or len(admin_password) < 8:
                raise OnboardingError(
                    "An admin password (at least 8 characters) is required to "
                    "activate this facility account."
                )
            password_hash = hash_password(admin_password)

        duplicate = await self.db.scalar(
            select(AuthAccount.id).where(
                func.lower(AuthAccount.email) == admin_email
            )
        )
        if duplicate is not None:
            raise OnboardingError(
                "An account with this email already exists in the system. "
                "Please contact the platform administrator."
            )

        staff = await self._create_staff(
            facility_id=facility_id,
            keycloak_user_id=uuid.uuid4(),
            first_name=onboarding.get("admin_first_name", "Facility"),
            last_name=onboarding.get("admin_last_name", "Admin"),
            email=admin_email,
            role="facility_admin",
            actor_id=approver_id,
        )
        self.db.add(
            AuthAccount(
                staff_id=staff.id,
                facility_id=facility_id,
                email=admin_email,
                password_hash=password_hash,
                is_active=True,
            )
        )
        await self.db.flush()
        return facility, True

    async def invite_staff(
        self,
        facility_id: uuid.UUID,
        data: StaffInviteRequest,
        admin_client: KeycloakAdminClient,
        inviter_id: uuid.UUID | None = None,
    ) -> Staff:
        """
        Invite a staff member: create the Keycloak user (facility_id + role +
        set-password email) and a linked Staff record.

        @param facility_id: Facility the staff belongs to
        @param data: Invite details
        @param admin_client: Keycloak admin client
        @param inviter_id: Facility admin performing the invite
        @returns The created Staff record
        """
        if settings.auth_provider == "internal":
            raise OnboardingError(
                "Staff invites are not available yet in internal-auth mode. "
                "Accounts are created when facilities sign up."
            )
        if not admin_client.is_configured:
            raise OnboardingError(
                "User provisioning is not configured (Keycloak admin credentials "
                "missing)."
            )
        # Reject a duplicate active staff email within the facility.
        dup = await self.db.scalar(
            select(Staff.id).where(
                Staff.facility_id == facility_id,
                func.lower(Staff.email) == str(data.email).lower(),
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        if dup:
            raise OnboardingError(
                "A staff member with this email already exists at this facility."
            )

        try:
            user_id = await admin_client.create_user(
                email=str(data.email),
                first_name=data.first_name,
                last_name=data.last_name,
                facility_id=str(facility_id),
                roles=[data.role],
                send_invite_email=True,
            )
        except KeycloakAdminError as exc:
            raise OnboardingError(str(exc)) from exc

        staff = await self._create_staff(
            facility_id=facility_id,
            keycloak_user_id=uuid.UUID(user_id),
            first_name=data.first_name,
            last_name=data.last_name,
            email=str(data.email),
            role=data.role,
            actor_id=inviter_id,
        )
        await self.db.flush()
        return staff

    async def _create_staff(
        self,
        *,
        facility_id: uuid.UUID,
        keycloak_user_id: uuid.UUID,
        first_name: str,
        last_name: str,
        email: str,
        role: str,
        actor_id: uuid.UUID | None,
    ) -> Staff:
        """Create a Staff row with an auto-generated employee number."""
        count = (
            await self.db.scalar(
                select(func.count(Staff.id)).where(Staff.facility_id == facility_id)
            )
        ) or 0
        employee_number = f"EMP-{count + 1:05d}"
        staff = Staff(
            facility_id=facility_id,
            keycloak_user_id=keycloak_user_id,
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            role=role,
            email=email,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.db.add(staff)
        await self.db.flush()
        return staff


def should_auto_approve() -> bool:
    """Whether facility sign-ups are auto-approved (config)."""
    return settings.facility_signup_auto_approve
