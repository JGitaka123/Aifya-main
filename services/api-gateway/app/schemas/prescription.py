import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PrescriptionCreate(BaseModel):
    """Schema for creating a prescription."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID

    # Drug
    drug_name: str = Field(..., min_length=1, max_length=300)
    drug_code: str | None = Field(None, max_length=50)
    generic_name: str | None = Field(None, max_length=300)
    is_keml: bool = False
    atc_code: str | None = Field(None, max_length=20)

    # Dosage
    dosage: str = Field(..., min_length=1, max_length=100)
    dosage_value: float | None = None
    dosage_unit: str | None = Field(None, max_length=20)
    route: str = Field(
        ...,
        pattern=r"^(oral|iv|im|sc|topical|inhaled|rectal|sublingual|ophthalmic|otic|nasal)$",
    )
    frequency: str = Field(
        ...,
        pattern=r"^(od|bd|tds|qds|prn|stat|nocte|weekly|monthly)$",
    )
    duration_days: int | None = Field(None, ge=1, le=365)
    quantity: int | None = Field(None, ge=1)
    instructions: str | None = Field(None, max_length=1000)
    refills_allowed: int = Field(default=0, ge=0, le=12)

    # Acknowledgement of non-blocking (WARN) safety alerts raised at save time.
    acknowledged_alert_ids: list[str] | None = None
    override_reason: str | None = Field(None, max_length=1000)


class PrescriptionResponse(BaseModel):
    """Schema for prescription API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    prescriber_id: uuid.UUID
    drug_name: str
    drug_code: str | None
    generic_name: str | None
    is_keml: bool
    atc_code: str | None
    dosage: str
    dosage_value: float | None
    dosage_unit: str | None
    route: str
    frequency: str
    duration_days: int | None
    quantity: int | None
    instructions: str | None
    interaction_checked: bool
    interactions: list | None = None
    acknowledged_alerts: list | None = None
    override_reason: str | None = None
    status: str
    dispensed_by: uuid.UUID | None
    dispensed_at: datetime | None
    dispensed_quantity: int | None
    refills_allowed: int
    refills_used: int
    unit_cost_cents: int | None
    total_cost_cents: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DrugInteractionAlert(BaseModel):
    """Drug interaction check result."""

    severity: str  # critical, major, moderate, minor
    interacting_drug: str
    description: str
    category: str | None = None  # e.g. drug_interaction, drug_allergy, drug_dose
    source_rule: str | None = None


class PrescriptionWithInteractions(BaseModel):
    """Prescription response with interaction check results.

    When blocked is True the prescription was NOT saved (critical
    interaction) and the prescription field is null.
    """

    prescription: PrescriptionResponse | None
    interactions: list[DrugInteractionAlert]
    blocked: bool  # True if critical interaction found
