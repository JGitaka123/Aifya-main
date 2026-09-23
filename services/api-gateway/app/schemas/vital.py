import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VitalSignCreate(BaseModel):
    """Schema for recording vital signs."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID

    # Blood pressure
    systolic_bp: int | None = Field(None, ge=40, le=300)
    diastolic_bp: int | None = Field(None, ge=20, le=200)

    # Heart rate
    heart_rate: int | None = Field(None, ge=20, le=300)

    # Temperature
    temperature: float | None = Field(None, ge=25.0, le=45.0)
    temperature_site: str | None = Field(
        None, pattern=r"^(oral|axillary|rectal|tympanic|temporal)$"
    )

    # Respiratory
    respiratory_rate: int | None = Field(None, ge=4, le=80)
    oxygen_saturation: float | None = Field(None, ge=0, le=100)
    on_supplemental_o2: bool = False
    o2_flow_rate: float | None = Field(None, ge=0, le=60)

    # Anthropometric
    weight_kg: float | None = Field(None, ge=0.1, le=500)
    height_cm: float | None = Field(None, ge=20, le=300)
    head_circumference_cm: float | None = Field(None, ge=10, le=80)
    muac_cm: float | None = Field(None, ge=5, le=50)

    # Pain
    pain_score: int | None = Field(None, ge=0, le=10)

    # Blood glucose
    blood_glucose: float | None = Field(None, ge=0, le=50)
    glucose_timing: str | None = Field(
        None, pattern=r"^(fasting|random|post_prandial)$"
    )

    # GCS
    gcs_eye: int | None = Field(None, ge=1, le=4)
    gcs_verbal: int | None = Field(None, ge=1, le=5)
    gcs_motor: int | None = Field(None, ge=1, le=6)


class VitalSignResponse(BaseModel):
    """Schema for vital signs API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    recorded_by: uuid.UUID
    recorded_at: datetime
    systolic_bp: int | None
    diastolic_bp: int | None
    heart_rate: int | None
    temperature: float | None
    temperature_site: str | None
    respiratory_rate: int | None
    oxygen_saturation: float | None
    on_supplemental_o2: bool
    o2_flow_rate: float | None
    weight_kg: float | None
    height_cm: float | None
    bmi: float | None
    head_circumference_cm: float | None
    muac_cm: float | None
    pain_score: int | None
    blood_glucose: float | None
    glucose_timing: str | None
    gcs_eye: int | None
    gcs_verbal: int | None
    gcs_motor: int | None
    is_critical: bool
    critical_alerts: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
