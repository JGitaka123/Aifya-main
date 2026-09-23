"""First-run bootstrap for Aifya's two authentication modes.

In internal mode the platform super-admin (role 'admin') and its facility are
created when no account exists yet, so the first password login has an account
to use. In Keycloak mode the realm-imported users already carry a facility_id
attribute, so the facility and staff row those attributes refer to are created
instead. Both are no-ops when their configuration is unset.
"""

import uuid

from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.middleware.facility_context import set_facility_context
from app.models.auth_account import AuthAccount
from app.models.facility import Facility
from app.models.staff import Staff
from app.services.licensing_service import LicensingService
from app.utils.passwords import hash_password

_KEYCLOAK_FACILITY_CODE = "PLATFORM-KC"


async def ensure_internal_super_admin() -> None:
    """Create the internal bootstrap super-admin on first startup."""
    if settings.auth_provider != "internal":
        return
    email = (settings.internal_bootstrap_email or "").strip().lower()
    if not email or not settings.internal_bootstrap_password:
        return

    async with async_session() as db:
        # auth_accounts is platform-level (no RLS) so this lookup is safe.
        existing = await db.scalar(
            select(AuthAccount.id).where(func.lower(AuthAccount.email) == email)
        )
        if existing is not None:
            return

        facility = await db.scalar(
            select(Facility).where(Facility.code == "PLATFORM")
        )
        if facility is None:
            facility = Facility(
                name=settings.internal_bootstrap_facility_name
                or "Aifya Platform",
                code="PLATFORM",
                facility_type="health_centre",
                county=None,
                onboarding_status="approved",
                is_active=True,
                admin_email=email,
            )
            db.add(facility)
            await db.flush()

        # Staff rows are RLS-scoped to their facility, so point the session at
        # the platform facility before reading/writing staff.
        await set_facility_context(db, str(facility.id))

        count = (
            await db.scalar(
                select(func.count(Staff.id)).where(
                    Staff.facility_id == facility.id
                )
            )
        ) or 0
        staff = Staff(
            facility_id=facility.id,
            keycloak_user_id=uuid.uuid4(),
            employee_number="EMP-" + str(count + 1).zfill(5),
            first_name="Aifya",
            last_name="Administrator",
            role="admin",
            email=email,
            is_active=True,
        )
        db.add(staff)
        await db.flush()

        db.add(
            AuthAccount(
                staff_id=staff.id,
                facility_id=facility.id,
                email=email,
                password_hash=hash_password(
                    settings.internal_bootstrap_password
                ),
                is_active=True,
            )
        )
        await LicensingService(db).ensure_license(
            facility_id=facility.id,
            tier=settings.facility_signup_tier,
            notes="Auto-issued platform facility",
        )
        await db.commit()


async def ensure_keycloak_bootstrap() -> None:
    """
    Keycloak mode: create the facility the realm's seeded users point at.

    The realm import gives its seeded users a ``facility_id`` attribute, but
    that UUID has no row in this database, so a first Keycloak login would
    resolve to an empty tenant and every module-gated page would return 403.
    Creating the facility (and a staff row for the bootstrap email) once makes
    the seeded admin land in a licensed, usable tenant.

    No-op in internal mode and when the bootstrap email is unset. It uses its
    own facility code, so it can never collide with the internal-mode platform
    facility.
    """
    if settings.auth_provider == "internal":
        return
    email = (settings.internal_bootstrap_email or "").strip().lower()
    if not email:
        return

    facility_id = uuid.UUID(settings.keycloak_bootstrap_facility_id)

    async with async_session() as db:
        facility = await db.get(Facility, facility_id)
        if facility is None:
            code_taken = await db.scalar(
                select(Facility.id).where(Facility.code == _KEYCLOAK_FACILITY_CODE)
            )
            if code_taken is not None:
                # Another facility already owns the code; leave the database
                # alone rather than failing this and every later startup.
                return
            db.add(
                Facility(
                    id=facility_id,
                    name=settings.internal_bootstrap_facility_name
                    or "Aifya Platform",
                    code=_KEYCLOAK_FACILITY_CODE,
                    facility_type="health_centre",
                    county=None,
                    onboarding_status="approved",
                    is_active=True,
                    admin_email=email,
                )
            )
            await db.flush()

        # Staff rows are RLS-scoped to their facility, so point the session at
        # it before reading or writing staff.
        await set_facility_context(db, str(facility_id))

        staff_exists = await db.scalar(
            select(Staff.id).where(
                Staff.facility_id == facility_id,
                func.lower(Staff.email) == email,
                Staff.is_deleted == False,  # noqa: E712
            )
        )
        if staff_exists is None:
            count = (
                await db.scalar(
                    select(func.count(Staff.id)).where(
                        Staff.facility_id == facility_id
                    )
                )
            ) or 0
            db.add(
                Staff(
                    facility_id=facility_id,
                    keycloak_user_id=uuid.UUID(settings.keycloak_bootstrap_user_id),
                    employee_number="EMP-" + str(count + 1).zfill(5),
                    first_name="Aifya",
                    last_name="Administrator",
                    role="admin",
                    email=email,
                    is_active=True,
                )
            )
            await db.flush()

        await LicensingService(db).ensure_license(
            facility_id=facility_id,
            tier=settings.facility_signup_tier,
            notes="Auto-issued Keycloak bootstrap facility",
        )
        await db.commit()


async def ensure_all_facility_licenses() -> None:
    """Backfill an active license for every approved facility missing one."""
    async with async_session() as db:
        facilities = (
            await db.execute(
                select(Facility).where(
                    Facility.onboarding_status == "approved",
                    Facility.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        for facility in facilities:
            await set_facility_context(db, str(facility.id))
            await LicensingService(db).ensure_license(
                facility_id=facility.id,
                tier=settings.facility_signup_tier,
                notes="Auto-issued startup backfill",
            )
        await db.commit()
