import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DentalChartResponse(BaseModel):
    """Schema for dental chart responses."""

    id: uuid.UUID
    patient_id: uuid.UUID
    teeth: dict
    periodontal_status: str | None
    occlusion_notes: str | None
    last_xray_date: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


class DentalChartUpdate(BaseModel):
    """Schema for updating dental chart."""

    teeth: dict
    periodontal_status: str | None = None
    occlusion_notes: str | None = None
    last_xray_date: datetime | None = None
    notes: str | None = Field(None, max_length=2000)


class DentalVisitCreate(BaseModel):
    """Schema for creating a dental visit."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    dentist_id: uuid.UUID
    visit_date: datetime | None = None
    chief_complaint: str | None = Field(None, max_length=2000)
    examination_findings: str | None = Field(None, max_length=5000)
    procedures: dict | None = None
    diagnosis: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)


class DentalVisitResponse(BaseModel):
    """Schema for dental visit responses."""

    id: uuid.UUID
    visit_number: str
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    dentist_id: uuid.UUID
    visit_date: datetime
    chief_complaint: str | None
    examination_findings: str | None
    procedures: dict | None
    diagnosis: str | None
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DentalVisitListItem(BaseModel):
    """Dental visit in list view."""

    id: uuid.UUID
    visit_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    dentist_name: str | None = None
    visit_date: datetime
    chief_complaint: str | None
    status: str

    model_config = {"from_attributes": True}


class DentalVisitListResponse(BaseModel):
    """Dental visit list response."""

    items: list[DentalVisitListItem]
    total: int


class DentalTreatmentPlanCreate(BaseModel):
    """Schema for creating a treatment plan."""

    patient_id: uuid.UUID
    dentist_id: uuid.UUID
    diagnosis: str | None = Field(None, max_length=2000)
    plan_items: list[dict] = Field(default_factory=list)
    total_estimated_cost: int = Field(0, ge=0)
    notes: str | None = Field(None, max_length=2000)


class DentalTreatmentPlanResponse(BaseModel):
    """Schema for treatment plan responses."""

    id: uuid.UUID
    plan_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    dentist_id: uuid.UUID
    dentist_name: str | None = None
    diagnosis: str | None
    plan_items: list[dict]
    total_estimated_cost: int
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DentalTreatmentPlanStatusUpdate(BaseModel):
    """Schema for moving a treatment plan through its lifecycle."""

    status: str = Field(
        ...,
        pattern=r"^(draft|approved|in_progress|completed|cancelled)$",
    )


class DentalTreatmentPlanListResponse(BaseModel):
    """Treatment plan list response."""

    items: list[DentalTreatmentPlanResponse]
    total: int


class DentalSummary(BaseModel):
    """Dental department summary stats."""

    total_patients: int = 0
    today_visits: int = 0
    pending_treatments: int = 0
    completed_today: int = 0
