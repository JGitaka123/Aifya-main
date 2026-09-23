import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Imaging Order schemas ─────────────────────────────────────────────────


class ImagingOrderCreate(BaseModel):
    """Schema for creating an imaging order."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    modality: str = Field(
        ...,
        pattern=r"^(xray|ultrasound|ct|mri|fluoroscopy|mammography|ecg|echo)$",
    )
    body_part: str = Field(..., min_length=1, max_length=100)
    laterality: str | None = Field(
        None, pattern=r"^(left|right|bilateral|na)$"
    )
    views_requested: str | None = Field(None, max_length=200)
    study_description: str = Field(..., min_length=1, max_length=300)
    priority: str = Field(
        default="routine", pattern=r"^(stat|urgent|routine)$"
    )
    clinical_indication: str | None = Field(None, max_length=2000)
    clinical_history: str | None = Field(None, max_length=2000)
    contrast_required: bool = False
    contrast_type: str | None = Field(None, max_length=100)
    pregnancy_status: str | None = Field(
        None, pattern=r"^(not_pregnant|pregnant|unknown|na)$"
    )
    allergies_noted: str | None = Field(None, max_length=500)


class ImagingOrderResponse(BaseModel):
    """Schema for imaging order API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    ordered_by: uuid.UUID
    order_number: str
    accession_number: str | None
    modality: str
    body_part: str
    laterality: str | None
    views_requested: str | None
    study_description: str
    priority: str
    clinical_indication: str | None
    contrast_required: bool
    pregnancy_status: str | None
    status: str
    scheduled_at: datetime | None
    room: str | None
    performed_by: uuid.UUID | None
    performed_at: datetime | None
    total_cost_cents: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Worklist item (order + patient info) ──────────────────────────────────


class ImagingWorklistItem(BaseModel):
    """Imaging order in the worklist with patient details."""

    id: uuid.UUID
    order_number: str
    accession_number: str | None
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    ordered_by: uuid.UUID
    modality: str
    body_part: str
    laterality: str | None
    study_description: str
    priority: str
    status: str
    contrast_required: bool
    has_result: bool = False
    result_status: str | None = None
    is_critical: bool = False
    scheduled_at: datetime | None
    room: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImagingWorklistResponse(BaseModel):
    """Imaging worklist response."""

    items: list[ImagingWorklistItem]
    total: int


# ── Schedule / Perform ────────────────────────────────────────────────────


class ImagingScheduleRequest(BaseModel):
    """Schema for scheduling an imaging study."""

    scheduled_at: datetime
    room: str | None = Field(None, max_length=50)


class ImagingPerformRequest(BaseModel):
    """Schema for marking an imaging study as performed."""

    accession_number: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


# ── Imaging Result schemas ────────────────────────────────────────────────


class ImagingResultCreate(BaseModel):
    """Schema for creating/entering an imaging report (draft)."""

    findings: str | None = Field(None, max_length=10000)
    impression: str | None = Field(None, max_length=5000)
    recommendations: str | None = Field(None, max_length=5000)
    technique: str | None = Field(None, max_length=2000)
    comparison: str | None = Field(None, max_length=2000)
    urgency: str = Field(
        default="normal",
        pattern=r"^(normal|abnormal|critical|incidental)$",
    )
    is_critical: bool = False
    notes: str | None = Field(None, max_length=2000)


class ImagingResultResponse(BaseModel):
    """Schema for imaging result API responses."""

    id: uuid.UUID
    order_id: uuid.UUID
    patient_id: uuid.UUID
    reported_by: uuid.UUID | None
    verified_by: uuid.UUID | None
    findings: str | None
    impression: str | None
    recommendations: str | None
    technique: str | None
    comparison: str | None
    urgency: str
    is_critical: bool
    critical_notified: bool
    critical_notified_to: uuid.UUID | None
    critical_notified_at: datetime | None
    status: str
    reported_at: datetime | None
    verified_at: datetime | None
    image_keys: list[dict[str, str]] | None
    dicom_study_uid: str | None
    dicom_series_count: int | None
    dicom_instance_count: int | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImagingResultVerify(BaseModel):
    """Schema for verifying (finalising) an imaging report."""

    notes: str | None = Field(None, max_length=2000)


class CriticalImagingNotifyRequest(BaseModel):
    """Schema for recording critical imaging finding notification."""

    notified_to: uuid.UUID


# ── Order Detail (order + result + patient) ───────────────────────────────


class ImagingOrderDetail(BaseModel):
    """Full imaging order with result and patient info."""

    order: ImagingOrderResponse
    result: ImagingResultResponse | None = None
    patient_name: str | None = None
    patient_mrn: str | None = None


# ── Radiology Summary ────────────────────────────────────────────────────


class RadiologySummary(BaseModel):
    """Dashboard summary stats for radiology department."""

    total_orders_today: int = 0
    pending_orders: int = 0
    in_progress: int = 0
    completed_today: int = 0
    pending_reports: int = 0
    critical_findings: int = 0
