import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PointOfCareTestCreate(BaseModel):
    """Schema for recording a bedside / point-of-care test result."""

    test_code: str = Field(..., min_length=1, max_length=50)
    test_name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(
        "screening",
        pattern=r"^(screening|rapid_diagnostic|urinalysis|other)$",
    )
    specimen_type: str | None = Field(None, max_length=50)
    result_value: str | None = Field(None, max_length=200)
    result_numeric: float | None = Field(None, ge=0, le=100000)
    result_unit: str | None = Field(None, max_length=50)
    interpretation: str | None = Field(
        None,
        pattern=(
            r"^(normal|abnormal|positive|negative|reactive|non_reactive|inconclusive)$"
        ),
    )
    notes: str | None = Field(None, max_length=2000)


class PointOfCareTestResponse(BaseModel):
    """Schema for point-of-care test API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    performed_by: uuid.UUID
    performed_at: datetime
    test_code: str
    test_name: str
    category: str
    specimen_type: str | None
    result_value: str | None
    result_numeric: float | None
    result_unit: str | None
    interpretation: str | None
    is_abnormal: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
