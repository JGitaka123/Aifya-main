"""Facility profile endpoints backing the Settings -> Facility screen.

Any signed-in user may read the profile so the screen renders; only an
administrator or the HR administrator may change it. HR keeps the hospital's
own details - its name, contacts and currency - as part of running the staff,
so refusing them here left the Settings screen openable but unusable. The
tenant is taken from the access token, so a facility can only ever read or edit
its own record.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user, require_roles
from app.database import get_db
from app.models.facility import Facility
from app.schemas.facility import FacilityResponse, FacilityUpdate

router = APIRouter()


async def _load_facility(db: AsyncSession, facility_id: uuid.UUID) -> Facility:
    """
    Load the caller's facility or fail with 404.

    @param db: Database session
    @param facility_id: Facility UUID from the access token
    @returns The facility record
    @raises HTTPException 404: when the facility no longer exists
    """
    facility = (
        await db.execute(select(Facility).where(Facility.id == facility_id))
    ).scalar_one_or_none()
    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found"
        )
    return facility


@router.get("", response_model=FacilityResponse)
async def get_facility(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FacilityResponse:
    """
    Read the signed-in user's facility profile.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns The facility profile
    """
    facility = await _load_facility(db, current_user.facility_id)
    return FacilityResponse.model_validate(facility, from_attributes=True)


@router.patch("", response_model=FacilityResponse)
async def update_facility(
    data: FacilityUpdate | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "admin",
            "facility_admin",
            "hospital_administrator",
            "hr_admin",
        )
    ),
) -> FacilityResponse:
    """
    Update the editable fields of the facility profile.

    Only fields present in the request body are written, so a partial payload
    cannot blank out values the operator did not touch.

    @param data: Editable facility fields
    @param db: Database session
    @param current_user: Authenticated administrator or HR administrator
    @returns The updated facility profile
    @raises HTTPException 400: When the request carries no JSON body
    """
    if data is None:
        # FastAPI answers a missing body with a bare 422 that names no cause.
        # When the body is dropped in transit (a proxy, a stale cached client,
        # an offline replay) that reads as "the form is invalid" and hides the
        # real problem, so say what actually happened instead.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The request body was empty, so nothing was saved. Re-submit "
                "the form; if it keeps failing, the request is being sent "
                "without its JSON payload."
            ),
        )

    facility = await _load_facility(db, current_user.facility_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(facility, field, value)

    await db.commit()
    await db.refresh(facility)
    return FacilityResponse.model_validate(facility, from_attributes=True)
