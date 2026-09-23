import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

# Oldest verified human age is ~122; reject DOBs implying more than this.
_MAX_AGE_YEARS = 120

# Kenyan mobile numbers: 07######## / 01######## / +2547######## / 2547########.
_KE_PHONE_RE = re.compile(r"^(?:\+?254|0)?[17]\d{8}$")


def _validate_dob(value: date) -> date:
    """Reject a future or implausibly old date of birth (D8)."""
    today = date.today()
    if value > today:
        raise ValueError("Date of birth cannot be in the future")
    if value.year < today.year - _MAX_AGE_YEARS:
        raise ValueError(f"Date of birth cannot be more than {_MAX_AGE_YEARS} years ago")
    return value


def _validate_phone(value: str) -> str:
    """Reject a non-phone string (QA F16). Accepts common Kenyan formats."""
    if not _KE_PHONE_RE.match(value.replace(" ", "").replace("-", "")):
        raise ValueError(
            "Enter a valid Kenyan phone number, e.g. 0712345678"
        )
    return value


class PatientCreate(BaseModel):
    """Schema for creating a new patient registration."""

    first_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str = Field(..., pattern=r"^(male|female|other)$")

    @field_validator("date_of_birth")
    @classmethod
    def _check_dob(cls, value: date) -> date:
        return _validate_dob(value)

    # Identification
    national_id: str | None = Field(None, max_length=50)
    passport_number: str | None = Field(None, max_length=50)

    # Contact
    phone_number: str = Field(..., min_length=9, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return _validate_phone(value)
    alternate_phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)

    # Address
    county: str | None = Field(None, max_length=100)
    sub_county: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    village: str | None = Field(None, max_length=200)
    postal_address: str | None = Field(None, max_length=200)

    # Personal
    occupation: str | None = Field(None, max_length=100)
    marital_status: str | None = Field(
        None, pattern=r"^(single|married|divorced|widowed)$"
    )

    # Next of Kin
    next_of_kin_name: str | None = Field(None, max_length=200)
    next_of_kin_phone: str | None = Field(None, max_length=20)
    next_of_kin_relationship: str | None = Field(None, max_length=50)

    # Insurance
    insurance_provider: str | None = Field(None, max_length=100)
    insurance_member_number: str | None = Field(None, max_length=100)
    sha_number: str | None = Field(None, max_length=50)

    # Medical
    blood_group: str | None = Field(None)
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None


class PatientUpdate(BaseModel):
    """Schema for updating patient data. All fields optional."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, pattern=r"^(male|female|other)$")
    national_id: str | None = Field(None, max_length=50)
    passport_number: str | None = Field(None, max_length=50)
    phone_number: str | None = Field(None, min_length=9, max_length=20)
    alternate_phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    county: str | None = Field(None, max_length=100)
    sub_county: str | None = Field(None, max_length=100)
    ward: str | None = Field(None, max_length=100)
    village: str | None = Field(None, max_length=200)
    postal_address: str | None = Field(None, max_length=200)
    occupation: str | None = Field(None, max_length=100)
    marital_status: str | None = Field(
        None, pattern=r"^(single|married|divorced|widowed)$"
    )
    next_of_kin_name: str | None = Field(None, max_length=200)
    next_of_kin_phone: str | None = Field(None, max_length=20)
    next_of_kin_relationship: str | None = Field(None, max_length=50)
    insurance_provider: str | None = Field(None, max_length=100)
    insurance_member_number: str | None = Field(None, max_length=100)
    sha_number: str | None = Field(None, max_length=50)
    blood_group: str | None = Field(None)
    allergies: list[str] | None = None
    chronic_conditions: list[str] | None = None


class PatientResponse(BaseModel):
    """Schema for patient API responses."""

    id: uuid.UUID
    mrn: str
    facility_id: uuid.UUID
    first_name: str
    middle_name: str | None
    last_name: str
    date_of_birth: date
    gender: str
    national_id: str | None
    passport_number: str | None
    phone_number: str
    alternate_phone: str | None
    email: str | None
    county: str | None
    sub_county: str | None
    ward: str | None
    village: str | None
    postal_address: str | None
    occupation: str | None
    marital_status: str | None
    next_of_kin_name: str | None
    next_of_kin_phone: str | None
    next_of_kin_relationship: str | None
    insurance_provider: str | None
    insurance_member_number: str | None
    sha_number: str | None
    blood_group: str | None
    allergies: list[str] | None
    chronic_conditions: list[str] | None
    photo_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    """Paginated patient list response."""

    items: list[PatientResponse]
    total: int
    page: int
    page_size: int


class DuplicateCheckRequest(BaseModel):
    """Request to check for likely-duplicate patients before registering (D7)."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    phone_number: str | None = Field(None, max_length=20)
    national_id: str | None = Field(None, max_length=50)
    passport_number: str | None = Field(None, max_length=50)


class DuplicateMatch(BaseModel):
    """A single possible-duplicate patient and why it matched (D7)."""

    patient: PatientResponse
    match_reasons: list[str]


class DuplicateCheckResponse(BaseModel):
    """Result of a pre-registration duplicate check (D7)."""

    has_duplicates: bool
    matches: list[DuplicateMatch]
