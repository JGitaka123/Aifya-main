import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Lab Order schemas ──────────────────────────────────────────────────────


class LabOrderCreate(BaseModel):
    """Schema for creating a lab order."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    priority: str = Field(
        default="routine", pattern=r"^(stat|urgent|routine)$"
    )
    specimen_type: str | None = Field(None, max_length=50)
    clinical_info: str | None = Field(None, max_length=1000)
    fasting: bool = False
    total_cost_cents: int | None = None
    tests: list["LabTestRequest"] = Field(..., min_length=1)


class LabTestRequest(BaseModel):
    """Individual test within a lab order."""

    test_code: str = Field(..., min_length=1, max_length=50)
    test_name: str = Field(..., min_length=1, max_length=200)
    loinc_code: str | None = Field(None, max_length=20)
    panel_name: str | None = Field(None, max_length=100)


class LabResultSummary(BaseModel):
    """Summary of a lab result for inclusion in order responses."""
    id: uuid.UUID
    test_code: str
    test_name: str
    status: str
    is_critical: bool = False
    is_abnormal: bool = False
    result_value: str | None = None
    result_unit: str | None = None
    model_config = {"from_attributes": True}


class LabOrderResponse(BaseModel):
    """Schema for lab order API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    ordered_by: uuid.UUID
    order_number: str
    priority: str
    status: str
    specimen_type: str | None
    specimen_collected_at: datetime | None
    clinical_info: str | None
    fasting: bool
    total_cost_cents: int | None
    created_at: datetime
    tests: list["LabResultSummary"] = []

    model_config = {"from_attributes": True}


# ── Lab Order with patient info (for worklist) ────────────────────────────


class LabWorklistItem(BaseModel):
    """Lab order in the worklist with patient details."""

    id: uuid.UUID
    order_number: str
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    ordered_by: uuid.UUID
    priority: str
    status: str
    specimen_type: str | None
    clinical_info: str | None
    fasting: bool
    test_count: int = 0
    pending_count: int = 0
    critical_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class LabWorklistResponse(BaseModel):
    """Lab worklist response."""

    items: list[LabWorklistItem]
    total: int


# ── Specimen Collection ───────────────────────────────────────────────────


class SpecimenCollectRequest(BaseModel):
    """Schema for recording specimen collection."""

    specimen_id: str | None = Field(None, max_length=50)


# ── Lab Result schemas ─────────────────────────────────────────────────────


class LabResultResponse(BaseModel):
    """Schema for lab result API responses."""

    id: uuid.UUID
    order_id: uuid.UUID
    patient_id: uuid.UUID
    performed_by: uuid.UUID | None
    verified_by: uuid.UUID | None
    test_code: str
    test_name: str
    loinc_code: str | None
    panel_name: str | None
    result_value: str | None
    result_numeric: float | None
    result_unit: str | None
    reference_range: str | None
    interpretation: str | None
    is_critical: bool
    is_abnormal: bool
    critical_notified: bool
    critical_notified_to: uuid.UUID | None
    critical_notified_at: datetime | None
    status: str
    resulted_at: datetime | None
    verified_at: datetime | None
    notes: str | None
    method: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LabResultEntry(BaseModel):
    """Schema for entering a lab result."""

    result_value: str | None = Field(None, max_length=200)
    result_numeric: float | None = None
    result_unit: str | None = Field(None, max_length=50)
    reference_range: str | None = Field(None, max_length=100)
    interpretation: str | None = Field(
        None, pattern=r"^(normal|abnormal|critical|inconclusive)$"
    )
    is_abnormal: bool = False
    notes: str | None = Field(None, max_length=2000)
    method: str | None = Field(None, max_length=100)


class LabResultVerify(BaseModel):
    """Schema for verifying (approving) a lab result."""

    notes: str | None = Field(None, max_length=2000)


class CriticalNotifyRequest(BaseModel):
    """Schema for recording critical value notification."""

    notified_to: uuid.UUID


# ── Lab Order Detail (order + results) ─────────────────────────────────────


class LabOrderDetail(BaseModel):
    """Full lab order with all results."""

    order: LabOrderResponse
    results: list[LabResultResponse]
    patient_name: str | None = None
    patient_mrn: str | None = None


# ── Lab Test Catalog (D6) ──────────────────────────────────────────────────


class LabCatalogItem(BaseModel):
    """A single catalog test for the ordering type-ahead."""

    id: uuid.UUID
    test_code: str
    test_name: str
    specimen_type: str | None = None
    panel_name: str | None = None
    price_cents: int
    reference_range: str | None = None

    model_config = {"from_attributes": True}


class LabCatalogResponse(BaseModel):
    """Catalog search response."""

    items: list[LabCatalogItem]
    total: int
