"""Internal (Aifya-hosted) authentication endpoints.

Active when AUTH_PROVIDER=internal so the branded login and registration
forms verify credentials against Aifya's own database. Public endpoints:
POST /auth/login and POST /auth/refresh. GET /auth/me requires a valid
token and reuses the shared current_user dependency.

Passwords live in the platform-level auth_accounts table (not RLS-scoped, by
design - it is the identity lookup that maps an email to a staff member).
Clinical/tenant rows stay isolated by facility via row-level security.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, current_user_dependency
from app.auth.internal_tokens import (
    decode_token,
    issue_access_token,
    issue_refresh_token,
)
from app.config import settings
from app.database import get_db
from app.middleware.facility_context import set_facility_context
from app.models.auth_account import AuthAccount
from app.models.facility import Facility
from app.models.staff import Staff
from app.utils.passwords import verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


def _public_user(staff: Staff, facility: Facility) -> dict:
    """Map a Staff row + Facility to the camelCase shape the web app uses."""
    name = (staff.first_name + " " + staff.last_name).strip()
    return {
        "id": str(staff.id),
        "email": staff.email,
        "name": name or staff.email,
        "roles": [staff.role],
        "facilityId": str(facility.id),
    }


async def _load_staff_and_facility(
    db: AsyncSession, account: AuthAccount
) -> tuple[Staff, Facility]:
    """Point RLS at the account's facility, then load staff + facility."""
    await set_facility_context(db, str(account.facility_id))
    staff = await db.get(Staff, account.staff_id)
    facility = await db.get(Facility, account.facility_id)
    return staff, facility


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
    if (
        account is None
        or not account.is_active
        or not verify_password(data.password, account.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    staff, facility = await _load_staff_and_facility(db, account)
    if (
        staff is None
        or staff.is_deleted
        or not staff.is_active
        or facility is None
        or not facility.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not active at an approved facility.",
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
        "user": _public_user(staff, facility),
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
    staff, facility = await _load_staff_and_facility(db, account)
    if (
        staff is None
        or staff.is_deleted
        or not staff.is_active
        or facility is None
        or not facility.is_active
    ):
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
        "user": _public_user(staff, facility),
    }


@router.get("/me")
async def me(current_user: CurrentUser = current_user_dependency):
    return {
        "authenticated": True,
        "user": {
            "id": str(current_user.user_id),
            "email": current_user.email,
            "name": current_user.name,
            "roles": current_user.roles,
            "facilityId": str(current_user.facility_id),
        },
    }
