"""Internal (Aifya-hosted) authentication endpoints.

Active when AUTH_PROVIDER=internal so the branded login and registration
forms verify credentials against Aifya's own database. Public endpoints:
POST /auth/login, POST /auth/refresh and GET /auth/duties. GET /auth/me
requires a valid token and reuses the shared current_user dependency.

Passwords live in the platform-level auth_accounts table (not RLS-scoped, by
design - it is the identity lookup that maps an email to a staff member).

The flow, in the order it happens:

1. Credentials. auth_accounts is read by email across every facility, which is
   only possible because it sits outside row level security.
2. Tenant binding. The account facility is written to the session as the
   bootstrap tenant, the staff record is read back under that policy, and
   staff.facility_id is the facility the token is issued for. See _resolve_tenant.
   The caller must have named that same hospital on the sign-in form; a
   mismatch is refused before any token is minted. See _facility_matches.
   The caller must also declare the state of duty HR recorded for them, because
   the role is the key that opens a workspace; a mismatch is refused the same
   way. See duty_matches.
3. Token. The signed token carries sub, facility_id, email, name and roles.
   Department is deliberately NOT a claim: it is resolved from the staff record
   on every request, so moving a clinician between units in HR takes effect at
   once instead of at their next login.
4. Every later request. The middleware republishes facility_id to the session,
   so row level security confines each query to that one facility.

Clinical/tenant rows stay isolated by facility via row level security.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, current_user_dependency
from app.auth.internal_tokens import (
    decode_token,
    issue_access_token,
    issue_refresh_token,
)
from app.auth.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    duty_matches,
    duty_options,
    effective_role_permissions,
    resolve_permissions,
)
from app.config import settings
from app.database import get_db
from app.middleware.facility_context import set_facility_context
from app.models.auth_account import AuthAccount
from app.models.facility import Facility
from app.models.staff import Department, Staff
from app.utils.passwords import hash_password, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)
    #: The hospital the employee was registered at. HR records the facility on
    #: the staff row, so asking for it here means a correct email and password
    #: pair still cannot open a session at the wrong hospital.
    facility: str = Field(..., min_length=2, max_length=255)
    #: The state of duty the employee declares at sign-in. HR records the role
    #: on the staff row; stating it here again means the workspace that opens is
    #: the one the declared duty owns, not whichever tabs the account happens to
    #: qualify for. It is compared on the duty family, so Doctor and clinician
    #: are the same duty while Doctor and Nurse are not.
    duty: str = Field(..., min_length=2, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


async def _staff_unit(
    db: AsyncSession, staff: Staff
) -> tuple[uuid.UUID | None, str | None]:
    """
    Resolve the unit a staff member is rostered to.

    The department is what narrows a clinician's queue to their own patients,
    so the web app needs it to explain an empty worklist.

    @param db: Database session
    @param staff: Staff row
    @returns Tuple of (department UUID, department name)
    """
    department_id = staff.department_id or staff.primary_department_id
    if department_id is None:
        return None, None
    name = await db.scalar(
        select(Department.name).where(Department.id == department_id)
    )
    return department_id, name


async def _public_user(
    db: AsyncSession, staff: Staff, facility: Facility
) -> dict:
    """
    Map a Staff row + Facility to the camelCase shape the web app uses.

    The effective permissions travel with the user object so the sidebar can
    hide what this person may not open. The API enforces the same list again on
    every endpoint - this copy is a convenience for the navigation, never the
    control itself.

    @param db: Database session
    @param staff: Staff row
    @param facility: Facility row
    @returns The user object the web app keeps in its auth context
    """
    name = (staff.first_name + " " + staff.last_name).strip()
    department_id, department_name = await _staff_unit(db, staff)
    permissions = await resolve_permissions(
        db,
        CurrentUser(
            user_id=staff.id,
            facility_id=facility.id,
            email=staff.email,
            roles=[staff.role],
            name=name,
        ),
    )
    return {
        "id": str(staff.id),
        "email": staff.email,
        "name": name or staff.email,
        "roles": [staff.role],
        "facilityId": str(facility.id),
        # Every screen shows the hospital the session belongs to, so it travels
        # with the user object rather than needing a second lookup per page.
        "facilityName": facility.name,
        "departmentId": str(department_id) if department_id else None,
        "departmentName": department_name,
        "permissions": sorted(permissions),
    }


#: Why an account could not be bound to a facility. One shared "not active at
#: an approved facility" for every case leaves the hospital nothing to act on;
#: these say which record to go and fix.
_BINDING_MESSAGES: dict[str, str] = {
    "no_staff": (
        "Your sign-in is not linked to a staff record at this facility. "
        "Ask an administrator to check your account."
    ),
    "facility_mismatch": (
        "Your account and your staff record name different facilities. "
        "Ask an administrator to correct your facility."
    ),
    "inactive_staff": (
        "Your staff record is inactive. Ask an administrator to re-activate it."
    ),
    "no_facility": "Your facility could not be found.",
    "inactive_facility": "Your facility is not active.",
}


def _binding_detail(reason: str | None) -> str:
    """
    Explain, for the signed-in user, why the binding did not hold.

    @param reason: Reason code from _resolve_tenant
    @returns A message naming the record that needs correcting
    """
    return _BINDING_MESSAGES.get(
        reason or "", "Your account is not active at an approved facility."
    )


async def _resolve_tenant(
    db: AsyncSession, account: AuthAccount
) -> tuple[Staff | None, Facility | None, str | None]:
    """
    Bind an authenticated account to exactly one facility.

    auth_accounts carries a facility so a bootstrap tenant exists before the
    staff row can be read at all - row level security would otherwise hide it.
    The binding that counts is the one on the staff record, so the facility that
    reaches the token is read back from staff.facility_id rather than assumed
    from the account, and the two are compared so drift is reported as drift
    instead of surfacing as a generic refusal.

    @param db: Database session
    @param account: Verified auth account
    @returns (staff, facility, reason); reason is None when the binding holds
    """
    await set_facility_context(db, str(account.facility_id))

    staff = await db.get(Staff, account.staff_id)
    if staff is None or staff.is_deleted:
        # Under RLS a staff row belonging to another facility is
        # indistinguishable from a missing one. Either way the account cannot
        # be bound, and this is the case worth naming out loud.
        return None, None, "no_staff"
    if staff.facility_id != account.facility_id:
        return None, None, "facility_mismatch"
    if not staff.is_active:
        return None, None, "inactive_staff"

    facility = await db.get(Facility, staff.facility_id)
    if facility is None:
        return None, None, "no_facility"
    if not facility.is_active:
        return None, None, "inactive_facility"

    return staff, facility, None


#: How a refused sign-in is reported. Two of these are HR's to fix and say so;
#: `invalid_credentials` stays deliberately vague, because a wrong password is
#: the one case the person can resolve themselves, and the one where naming the
#: reason would confirm an address somebody was guessing at. Every other state
#: is reported only after the password has proved the caller owns the account,
#: so none of them can be used to enumerate staff.
_LOGIN_REFUSALS: dict[str, tuple[int, str]] = {
    "not_registered": (
        status.HTTP_403_FORBIDDEN,
        "Your employee account has not been registered by HR. "
        "Please contact HR for assistance.",
    ),
    "access_revoked": (
        status.HTTP_403_FORBIDDEN,
        "Your Aifya access has been switched off. Please contact HR/Admin "
        "to have it restored.",
    ),
    "facility_mismatch": (
        status.HTTP_403_FORBIDDEN,
        "These details are not registered at that hospital. Check the "
        "hospital name, or contact HR for assistance.",
    ),
    "role_mismatch": (
        status.HTTP_403_FORBIDDEN,
        "These details are not registered for that state of duty. Check the "
        "duty you selected, or contact HR for assistance.",
    ),
    "invalid_credentials": (
        status.HTTP_401_UNAUTHORIZED,
        "Invalid email or password.",
    ),
}


def _login_refusal(account: AuthAccount | None, password: str) -> str | None:
    """
    Decide why these credentials cannot start a session.

    The order is deliberate. An unknown address is answered first, because there
    is no account to check anything else against. A wrong password is answered
    second, and the account's own state is only reported once the password has
    proved the caller owns it - otherwise the sign-in form would answer
    questions about accounts anyone could enumerate by typing guessed addresses.

    @param account: The account for the submitted address, or None
    @param password: Submitted plaintext password
    @returns A key of ``_LOGIN_REFUSALS``, or None when the credentials pass
    """
    if account is None:
        return "not_registered"
    if not verify_password(password, account.password_hash):
        return "invalid_credentials"
    if not account.is_active:
        return "access_revoked"
    return None


def _normalise_facility(value: str) -> str:
    """
    Fold a hospital name to the one form both sides are compared in.

    HR types the facility once and the employee retypes it at every sign-in,
    so the match has to survive casing, padding and the punctuation people
    vary. ``Nairobi General Hospital`` and ``nairobi  general-hospital`` are
    the same hospital, and the person should not be turned away over a space.

    @param value: Raw facility name or code
    @returns Lowercased, punctuation-free, whitespace-collapsed text
    """
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _facility_matches(submitted: str, facility: Facility) -> bool:
    """
    Whether the hospital the caller named is the one on their staff record.

    Facility is the row resolved from the account's staff record, so this is
    the hospital the token would be issued for. Accepting the short code as
    well as the full name is deliberate: staff know their hospital by either.

    @param submitted: Hospital name or code the caller typed at sign-in
    @param facility: Facility resolved from the signed-in staff record
    @returns True when the two name the same hospital
    """
    typed = _normalise_facility(submitted)
    if not typed:
        return False
    known = {_normalise_facility(facility.name or "")}
    if facility.code:
        known.add(_normalise_facility(facility.code))
    return typed in known


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    if settings.auth_provider != "internal":
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Password login is disabled. Use the OIDC redirect flow.",
        )
    email = data.email.strip().lower()
    account = await db.scalar(
        select(AuthAccount).where(func.lower(AuthAccount.email) == email)
    )

    # Aifya has no self-registration: an account exists only because HR created
    # the employee and issued a password. The three ways this can fail are
    # therefore not the same failure, and only one of them is the person's to
    # fix - so each gets its own answer rather than one blanket "invalid email or
    # password" that sends a new hire round in circles. The code travels with
    # the message so the sign-in screen can word it, and escalate it, without
    # parsing prose.
    refusal = _login_refusal(account, data.password)
    if refusal is not None:
        refusal_status, detail = _LOGIN_REFUSALS[refusal]
        return JSONResponse(
            status_code=refusal_status,
            content={"code": refusal, "detail": detail},
        )

    staff, facility, reason = await _resolve_tenant(db, account)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_binding_detail(reason),
        )

    # The hospital named at sign-in must be the one the staff record belongs
    # to. The password has already proved the caller owns the account, so this
    # can be said plainly rather than hidden behind the vague refusal reserved
    # for a wrong password - and it is what keeps one hospital's valid
    # credentials from opening another hospital's records.
    if not _facility_matches(data.facility, facility):
        refusal_status, detail = _LOGIN_REFUSALS["facility_mismatch"]
        return JSONResponse(
            status_code=refusal_status,
            content={"code": "facility_mismatch", "detail": detail},
        )

    # The duty is the key to the workspace. HR put the role on the staff record
    # and the person restates it here, so a correct password cannot open a
    # clinic the person does not work in; the mismatch is HR's to fix.
    if not duty_matches(data.duty, staff.role):
        refusal_status, detail = _LOGIN_REFUSALS["role_mismatch"]
        return JSONResponse(
            status_code=refusal_status,
            content={"code": "role_mismatch", "detail": detail},
        )

    name = (staff.first_name + " " + staff.last_name).strip()
    roles = [staff.role]
    return {
        "access_token": issue_access_token(
            subject=staff.id,
            facility_id=facility.id,
            email=staff.email,
            name=name,
            roles=roles,
        ),
        "refresh_token": issue_refresh_token(
            subject=staff.id,
            facility_id=facility.id,
            email=staff.email,
            name=name,
            roles=roles,
        ),
        "token_type": "bearer",
        "expires_in": 12 * 60 * 60,
        "user": await _public_user(db, staff, facility),
    }


@router.post("/refresh")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    if settings.auth_provider != "internal":
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        payload = decode_token(data.refresh_token, expected_type="refresh")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
        ) from exc

    account = await db.scalar(
        select(AuthAccount).where(
            AuthAccount.staff_id == uuid.UUID(str(payload.get("sub")))
        )
    )
    if account is None or not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
        )
    # A renewal only needs to know whether the binding still holds; the reason
    # is already on the login screen, so this stays deliberately opaque.
    staff, facility, reason = await _resolve_tenant(db, account)
    if reason is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
        )
    name = (staff.first_name + " " + staff.last_name).strip()
    roles = [staff.role]
    return {
        "access_token": issue_access_token(
            subject=staff.id,
            facility_id=facility.id,
            email=staff.email,
            name=name,
            roles=roles,
        ),
        "refresh_token": issue_refresh_token(
            subject=staff.id,
            facility_id=facility.id,
            email=staff.email,
            name=name,
            roles=roles,
        ),
        "expires_in": 12 * 60 * 60,
        "user": await _public_user(db, staff, facility),
    }


@router.get("/me")
async def me(
    current_user: CurrentUser = current_user_dependency,
    db: AsyncSession = Depends(get_db),
):
    """
    Report the signed-in user, with the permissions the role carries.

    Permissions are resolved fresh on every call, so an edit to
    ``role_permissions`` or to the staff record takes effect at the next page
    load instead of waiting for the access token to expire.

    @param current_user: Authenticated user from JWT
    @param db: Database session
    @returns The user object including facility, department and effective permissions
    """
    permissions = await resolve_permissions(db, current_user)

    department_id: uuid.UUID | None = None
    department_name: str | None = None
    staff = await db.get(Staff, current_user.user_id)
    if staff is not None and not staff.is_deleted:
        department_id, department_name = await _staff_unit(db, staff)

    # Read the name rather than trusting a claim: a facility rename reaches
    # every open session at its next page load.
    facility = await db.get(Facility, current_user.facility_id)
    facility_name = facility.name if facility is not None else None

    return {
        "authenticated": True,
        "user": {
            "id": str(current_user.user_id),
            "email": current_user.email,
            "name": current_user.name,
            "roles": current_user.roles,
            "facilityId": str(current_user.facility_id),
            "facilityName": facility_name,
            "departmentId": str(department_id) if department_id else None,
            "departmentName": department_name,
            "permissions": sorted(permissions),
        },
    }


@router.get("/duties")
async def list_duties() -> dict:
    """
    Report the states of duty the sign-in form offers.

    Public by design: the picker is shown before anyone has a token, and it
    lists only the duty names HR already recognises. The value that reaches the
    API is checked against the staff record at sign-in, so this catalogue is a
    convenience for the form, never the control.

    @returns The duty options as role/label pairs
    """
    return {"duties": duty_options()}


@router.get("/roles")
async def list_roles(
    current_user: CurrentUser = current_user_dependency,
    db: AsyncSession = Depends(get_db),
):
    """
    Report the role-to-permission matrix in force at this facility.

    Reads the shipped baseline and then applies this facility's own
    ``role_permissions`` rows on top, so the Settings -> Roles screen shows
    what actually applies here rather than what ships by default.

    @param current_user: Authenticated user from JWT
    @param db: Database session
    @returns Roles with their effective permissions, plus the full permission list
    """
    roles = []
    for role in sorted(ROLE_PERMISSIONS):
        granted = await effective_role_permissions(db, current_user.facility_id, role)
        roles.append({"role": role, "permissions": sorted(granted)})

    return {
        "roles": roles,
        "all_permissions": sorted(ALL_PERMISSIONS),
        "total_permissions": len(ALL_PERMISSIONS),
    }


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser = current_user_dependency,
    db: AsyncSession = Depends(get_db),
):
    """
    Change the signed-in user's own password.

    HR sets an initial password when it creates the account; this is how the
    employee replaces it with one only they know. The current password is
    required so that a borrowed session cannot be used to lock the owner out.

    @param data: Current and new password
    @param current_user: Authenticated user from JWT
    @param db: Database session
    @returns Confirmation that the password changed
    @raises HTTPException 401: When the current password is wrong
    @raises HTTPException 404: When the account has no login
    """
    if settings.auth_provider != "internal":
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Password login is disabled. Use the OIDC provider.",
        )

    account = await db.scalar(
        select(AuthAccount).where(AuthAccount.staff_id == current_user.user_id)
    )
    if account is None or not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your account does not have an active sign-in.",
        )
    if not verify_password(data.current_password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your current password is not correct.",
        )

    account.password_hash = hash_password(data.new_password)
    await db.flush()
    return {"changed": True, "message": "Your password has been changed."}

