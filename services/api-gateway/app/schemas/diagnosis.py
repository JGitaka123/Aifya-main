import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.services.icd10_catalog import lookup_icd10, normalize_code


class DiagnosisCreate(BaseModel):
    """Schema for creating a diagnosis."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    icd10_code: str = Field(..., min_length=3, max_length=20)
    icd10_description: str = Field(..., min_length=1, max_length=500)
    diagnosis_type: str = Field(
        ..., pattern=r"^(primary|secondary|differential|ruled_out)$"
    )
    clinical_status: str = Field(
        default="active",
        pattern=r"^(active|recurrence|relapse|inactive|remission|resolved)$",
    )
    certainty: str = Field(
        default="confirmed",
        pattern=r"^(confirmed|provisional|differential|refuted)$",
    )
    onset_date: date | None = None
    notes: str | None = Field(None, max_length=2000)
    is_chronic: bool = False

    @model_validator(mode="after")
    def _validate_icd10(self) -> "DiagnosisCreate":
        """
        Validate the ICD-10 code against the bundled catalog and store the
        canonical code + description (D5). An unknown code is rejected so it
        can never be saved as if valid, and analytics group by a canonical
        code/description pair.
        """
        canonical = lookup_icd10(self.icd10_code)
        if canonical is None:
            raise ValueError(
                f"Unknown ICD-10 code: {self.icd10_code!r}. "
                "Select a code from the diagnosis lookup."
            )
        self.icd10_code = normalize_code(self.icd10_code)
        self.icd10_description = canonical
        return self


class ICD10CodeItem(BaseModel):
    """A single ICD-10 catalog entry (D5)."""

    code: str
    description: str


class ICD10SearchResponse(BaseModel):
    """Type-ahead ICD-10 search results (D5)."""

    items: list[ICD10CodeItem]


class DiagnosisResponse(BaseModel):
    """Schema for diagnosis API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    diagnosed_by: uuid.UUID
    icd10_code: str
    icd10_description: str
    diagnosis_type: str
    clinical_status: str
    certainty: str
    onset_date: date | None
    resolved_date: date | None
    notes: str | None
    is_chronic: bool
    created_at: datetime

    model_config = {"from_attributes": True}
