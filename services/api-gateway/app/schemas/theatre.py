import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Theatres ─────────────────────────────────────────────────────────────────


class TheatreCreate(BaseModel):
    """Schema for creating an operating theatre."""

    name: str = Field(..., max_length=100)
    theatre_type: str = Field(
        default="general",
        pattern=r"^(general|orthopaedic|cardiac|neuro|ophthalmic|obstetric|ent|dental|minor)$",
    )
    floor: str | None = Field(None, max_length=20)
    equipment: dict | None = None
    notes: str | None = Field(None, max_length=1000)


class TheatreResponse(BaseModel):
    """Schema for theatre API responses."""

    id: uuid.UUID
    name: str
    code: str
    theatre_type: str
    status: str
    floor: str | None
    equipment: dict | None
    is_active: bool
    notes: str | None

    model_config = {"from_attributes": True}


# ── Surgical Cases ───────────────────────────────────────────────────────────


class SurgicalCaseCreate(BaseModel):
    """Schema for scheduling a surgical case."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    theatre_id: uuid.UUID | None = None
    scheduled_date: datetime
    estimated_duration_min: int = Field(60, ge=15, le=1440)
    priority: str = Field(
        default="elective",
        pattern=r"^(emergency|urgent|elective)$",
    )
    procedure_name: str = Field(..., max_length=500)
    procedure_code: str | None = Field(None, max_length=20)
    laterality: str | None = Field(None, pattern=r"^(left|right|bilateral|na)$")
    diagnosis: str | None = Field(None, max_length=2000)
    anaesthesia_type: str | None = Field(
        None,
        pattern=r"^(general|spinal|epidural|regional|local|sedation)$",
    )
    anaesthetist_id: uuid.UUID | None = None
    lead_surgeon_id: uuid.UUID
    assistant_surgeon_id: uuid.UUID | None = None
    scrub_nurse_id: uuid.UUID | None = None
    circulating_nurse_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)


class SurgicalCaseResponse(BaseModel):
    """Schema for surgical case API responses."""

    id: uuid.UUID
    case_number: str
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    theatre_id: uuid.UUID | None
    scheduled_date: datetime
    estimated_duration_min: int
    priority: str
    procedure_name: str
    procedure_code: str | None
    laterality: str | None
    diagnosis: str | None
    anaesthesia_type: str | None
    anaesthetist_id: uuid.UUID | None
    lead_surgeon_id: uuid.UUID
    assistant_surgeon_id: uuid.UUID | None
    scrub_nurse_id: uuid.UUID | None
    circulating_nurse_id: uuid.UUID | None
    status: str
    preop_start: datetime | None
    surgery_start: datetime | None
    surgery_end: datetime | None
    recovery_start: datetime | None
    recovery_end: datetime | None
    operative_findings: str | None
    operative_notes: str | None
    specimens: dict | None
    implants: dict | None
    complications: str | None
    blood_loss_ml: int | None
    postop_instructions: str | None
    preop_checklist: dict | None
    timeout_checklist: dict | None
    signout_checklist: dict | None
    cancellation_reason: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SurgicalCaseListItem(BaseModel):
    """Surgical case in list view."""

    id: uuid.UUID
    case_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    theatre_name: str | None = None
    scheduled_date: datetime
    procedure_name: str
    priority: str
    lead_surgeon_name: str | None = None
    status: str

    model_config = {"from_attributes": True}


class SurgicalCaseListResponse(BaseModel):
    """Surgical case list response."""

    items: list[SurgicalCaseListItem]
    total: int


class OperativeNotesRequest(BaseModel):
    """Schema for recording operative notes post-surgery."""

    operative_findings: str | None = Field(None, max_length=5000)
    operative_notes: str | None = Field(None, max_length=5000)
    specimens: dict | None = None
    implants: dict | None = None
    complications: str | None = Field(None, max_length=2000)
    blood_loss_ml: int | None = Field(None, ge=0)
    postop_instructions: str | None = Field(None, max_length=2000)


class TheatreSummary(BaseModel):
    """Theatre department summary stats."""

    total_theatres: int = 0
    available_theatres: int = 0
    in_use_theatres: int = 0
    scheduled_today: int = 0
    completed_today: int = 0
    emergency_cases: int = 0
    cancelled_today: int = 0
