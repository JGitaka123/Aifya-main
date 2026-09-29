"""Schemas for the facility profile settings endpoints.

``code``, ``id`` and ``onboarding_status`` are deliberately read-only: other
records reference the code, and onboarding state is owned by the platform.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

#: Fields that must never be blanked. ``name`` and ``facility_type`` are the
#: facility identity, and ``timezone``/``currency`` are NOT NULL settings the
#: rest of the system reads on every request.
REQUIRED_WHEN_PRESENT = frozenset(
    {"name", "facility_type", "timezone", "currency"}
)


class FacilityResponse(BaseModel):
    """Full facility profile shown on the Settings -> Facility screen."""

    id: uuid.UUID
    name: str
    code: str
    facility_type: str
    keph_level: str | None = None
    mfl_code: str | None = None
    county: str | None = None
    sub_county: str | None = None
    ward: str | None = None
    physical_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    logo_url: str | None = None
    timezone: str
    currency: str
    dhis2_org_unit_id: str | None = None
    onboarding_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FacilityUpdate(BaseModel):
    """
    Editable subset of the facility profile.

    The Settings -> Facility form submits every text input, including the ones
    the operator left blank. Two normalisations keep that form working:

    * A blank optional value (``""``) means "clear this field", so it becomes
      ``None`` rather than being written to the database as an empty string.
      This also lets the numeric ``latitude``/``longitude`` inputs be cleared,
      which a raw ``""`` could never satisfy.
    * A blank value for an identity field is rejected with a message naming the
      field, instead of failing later with an opaque database error.
    """

    name: str | None = Field(None, min_length=1, max_length=200)
    facility_type: str | None = Field(None, max_length=50)
    keph_level: str | None = Field(None, max_length=10)
    mfl_code: str | None = Field(None, max_length=20)
    county: str | None = Field(None, max_length=100)
    sub_county: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    physical_address: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    logo_url: str | None = Field(None, max_length=500)
    timezone: str | None = Field(None, max_length=50)
    currency: str | None = Field(None, max_length=3)
    dhis2_org_unit_id: str | None = Field(None, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def _normalize_blank_values(cls, data: object) -> object:
        """
        Treat blank form inputs as either "clear" or "invalid".

        @param data: Raw request body
        @returns Body with blank strings normalised to ``None``
        @raises ValueError: When a required identity field is blank
        """
        if not isinstance(data, dict):
            return data

        normalized: dict[object, object] = {}
        for key, value in data.items():
            if isinstance(value, str) and not value.strip():
                if key in REQUIRED_WHEN_PRESENT:
                    raise ValueError(f"{key} cannot be blank")
                normalized[key] = None
            else:
                normalized[key] = value
        return normalized
