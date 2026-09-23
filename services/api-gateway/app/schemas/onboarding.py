"""Schemas for facility onboarding (sign-up) and staff invites."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# Pragmatic email check (avoids the email-validator dependency).
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

_ROLE_PATTERN = (
    r"^(facility_admin|doctor|nurse|midwife|clinician|pharmacist|lab_tech|"
    r"cashier|billing_officer|records|receptionist|radiologist|radiographer|"
    r"investigator|research_coordinator)$"
)


class FacilitySignupRequest(BaseModel):
    """Public gated facility sign-up request."""

    facility_name: str = Field(..., min_length=2, max_length=200)
    facility_type: str = Field(
        ..., pattern=r"^(hospital|clinic|dispensary|health_centre|health_center)$"
    )
    county: str | None = Field(None, max_length=100)
    mfl_code: str | None = Field(None, max_length=20)
    facility_phone: str | None = Field(None, max_length=20)
    admin_first_name: str = Field(..., min_length=1, max_length=100)
    admin_last_name: str = Field(..., min_length=1, max_length=100)
    admin_email: str = Field(..., pattern=_EMAIL_PATTERN, max_length=255)
    # Required when AUTH_PROVIDER=internal so the facility-admin login can be
    # created immediately (auto-approve) or provisioned at approval time.
    admin_password: str | None = Field(None, min_length=8, max_length=128)


class FacilitySignupResponse(BaseModel):
    """Result of a facility sign-up request."""

    facility_id: uuid.UUID
    onboarding_status: str
    message: str


class PendingFacility(BaseModel):
    """A facility awaiting approval."""

    id: uuid.UUID
    name: str
    facility_type: str
    county: str | None
    admin_email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApproveFacilityResponse(BaseModel):
    """Result of approving a pending facility."""

    facility_id: uuid.UUID
    onboarding_status: str
    admin_user_created: bool
    message: str


class StaffInviteRequest(BaseModel):
    """Facility-admin invite for a new staff member."""

    email: str = Field(..., pattern=_EMAIL_PATTERN, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern=_ROLE_PATTERN)


class StaffInviteResponse(BaseModel):
    """Result of a staff invite."""

    staff_id: uuid.UUID
    keycloak_user_id: uuid.UUID
    email: str
    role: str
    message: str
