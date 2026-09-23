import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Ward schemas ──────────────────────────────────────────────────────────────


class WardCreate(BaseModel):
    """Schema for creating a ward."""

    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    ward_type: str = Field(
        ...,
        pattern=r"^(general|icu|hdu|maternity|paediatric|nicu|psychiatric|isolation|surgical|burns)$",
    )
    department_id: uuid.UUID | None = None
    floor: str | None = Field(None, max_length=20)
    total_beds: int = Field(default=0, ge=0)
    gender_restriction: str | None = Field(
        None, pattern=r"^(male|female|any)$"
    )
    charge_per_day_cents: int = Field(default=0, ge=0)
    notes: str | None = Field(None, max_length=1000)


class WardResponse(BaseModel):
    """Schema for ward API responses."""

    id: uuid.UUID
    name: str
    code: str
    ward_type: str
    department_id: uuid.UUID | None
    floor: str | None
    total_beds: int
    gender_restriction: str | None
    charge_per_day_cents: int
    is_active: bool
    notes: str | None
    available_beds: int = 0
    occupied_beds: int = 0

    model_config = {"from_attributes": True}


# ── Bed schemas ───────────────────────────────────────────────────────────────


class BedCreate(BaseModel):
    """Schema for creating a bed."""

    ward_id: uuid.UUID
    bed_number: str = Field(..., min_length=1, max_length=20)
    bed_type: str = Field(
        default="standard",
        pattern=r"^(standard|icu|hdu|cot|incubator|isolation)$",
    )
    notes: str | None = Field(None, max_length=500)


class BedResponse(BaseModel):
    """Schema for bed API responses."""

    id: uuid.UUID
    ward_id: uuid.UUID
    bed_number: str
    bed_type: str
    status: str
    current_patient_id: uuid.UUID | None
    current_admission_id: uuid.UUID | None
    notes: str | None
    ward_name: str | None = None
    patient_name: str | None = None

    model_config = {"from_attributes": True}


# ── Admission schemas ─────────────────────────────────────────────────────────


class AdmissionCreate(BaseModel):
    """Schema for admitting a patient."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    ward_id: uuid.UUID
    bed_id: uuid.UUID
    attending_doctor_id: uuid.UUID | None = None
    primary_nurse_id: uuid.UUID | None = None
    admission_reason: str | None = Field(None, max_length=2000)
    admission_diagnosis: str | None = Field(None, max_length=500)
    admitted_from: str | None = Field(
        None, pattern=r"^(opd|emergency|referral|direct)$"
    )
    accommodation_type: str | None = Field(
        None, pattern=r"^(general|semi_private|private|icu|hdu)$"
    )


class AdmissionResponse(BaseModel):
    """Schema for admission API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    ward_id: uuid.UUID
    bed_id: uuid.UUID
    admission_number: str
    attending_doctor_id: uuid.UUID | None
    primary_nurse_id: uuid.UUID | None
    status: str
    admission_reason: str | None
    admission_diagnosis: str | None
    admitted_from: str | None
    accommodation_type: str | None
    admitted_at: datetime
    discharged_at: datetime | None
    discharge_type: str | None
    discharge_diagnosis: str | None
    length_of_stay_days: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdmissionListItem(BaseModel):
    """Admission item for ward board / list views."""

    id: uuid.UUID
    admission_number: str
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    ward_name: str | None = None
    bed_number: str | None = None
    status: str
    admission_diagnosis: str | None
    admitted_from: str | None
    admitted_at: datetime
    length_of_stay_days: int | None = None

    model_config = {"from_attributes": True}


class AdmissionListResponse(BaseModel):
    """Paginated admission list."""

    items: list[AdmissionListItem]
    total: int


# ── Discharge schemas ─────────────────────────────────────────────────────────


class DischargeRequest(BaseModel):
    """Schema for discharging a patient."""

    discharge_type: str = Field(
        ...,
        pattern=r"^(improved|recovered|dama|absconded|deceased|transferred|referred)$",
    )
    discharge_diagnosis: str | None = Field(None, max_length=500)
    discharge_summary: str | None = Field(None, max_length=5000)
    follow_up_plan: str | None = Field(None, max_length=2000)
    discharge_medications: str | None = Field(None, max_length=2000)


class TransferToEmergencyRequest(BaseModel):
    '''Schema for transferring an inpatient to the Emergency Department.'''

    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description='Clinical reason for the worsening condition (becomes the ER chief complaint)',
    )
    notes: str | None = Field(None, max_length=2000)


# ── Nursing Note schemas ─────────────────────────────────────────────────────


class NursingNoteCreate(BaseModel):
    """Schema for creating a nursing note."""

    note_type: str = Field(
        ...,
        pattern=r"^(observation|medication|procedure|shift_handover|intake_output|pain_assessment|wound_care)$",
    )
    content: str = Field(..., min_length=1, max_length=5000)
    shift: str | None = Field(None, pattern=r"^(morning|afternoon|night)$")
    severity: str | None = Field(None, pattern=r"^(normal|warning|critical)$")


class NursingNoteResponse(BaseModel):
    """Schema for nursing note API responses."""

    id: uuid.UUID
    admission_id: uuid.UUID
    patient_id: uuid.UUID
    author_id: uuid.UUID
    note_type: str
    content: str
    shift: str | None
    severity: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Ward Board (bed occupancy overview) ───────────────────────────────────────


class WardBoardSummary(BaseModel):
    """Ward overview for the IPD dashboard."""

    total_wards: int
    total_beds: int
    occupied_beds: int
    available_beds: int
    active_admissions: int
    occupancy_rate: float
