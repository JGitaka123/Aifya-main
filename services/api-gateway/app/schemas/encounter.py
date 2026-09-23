import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EncounterCreate(BaseModel):
    """Schema for creating a new encounter."""

    patient_id: uuid.UUID
    encounter_type: str = Field(
        ..., pattern=r"^(opd|ipd|emergency|mch|dental|surgical|follow_up)$"
    )
    department_id: uuid.UUID | None = None
    attending_doctor_id: uuid.UUID | None = None
    chief_complaint: str | None = Field(None, max_length=2000)
    triage_category: str | None = Field(
        None, pattern=r"^(emergency|urgent|standard|non_urgent|dead)$"
    )
    priority: int = 0


class EncounterUpdate(BaseModel):
    """Schema for updating an encounter."""

    status: str | None = Field(
        None,
        pattern=r"^(waiting|in_consultation|completed|admitted|discharged|cancelled)$",
    )
    attending_doctor_id: uuid.UUID | None = None
    nurse_id: uuid.UUID | None = None
    chief_complaint: str | None = Field(None, max_length=2000)
    triage_category: str | None = Field(
        None, pattern=r"^(emergency|urgent|standard|non_urgent|dead)$"
    )
    priority: int | None = None
    disposition: str | None = Field(
        None,
        pattern=r"^(discharged|admitted|referred|follow_up|deceased)$",
    )
    discharge_summary: str | None = None


class EncounterResponse(BaseModel):
    """Schema for encounter API responses."""

    id: uuid.UUID
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_type: str
    encounter_date: datetime
    department_id: uuid.UUID | None
    attending_doctor_id: uuid.UUID | None
    nurse_id: uuid.UUID | None
    queue_number: int | None
    triage_category: str | None
    priority: int
    status: str
    chief_complaint: str | None
    disposition: str | None
    billing_status: str
    trial_participant_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    # Joined fields for display
    patient_name: str | None = None
    patient_mrn: str | None = None

    model_config = {"from_attributes": True}


class QueueResponse(BaseModel):
    """OPD queue list response."""

    items: list[EncounterResponse]
    total: int

class ConsultationFeeQuote(BaseModel):
    """What the patient owes at reception to see the doctor."""

    encounter_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    department_id: uuid.UUID | None = None
    attending_doctor_id: uuid.UUID | None = None
    fee_cents: int
    paid: bool
    invoice_id: uuid.UUID | None = None
    invoice_number: str | None = None
    paid_cents: int = 0
    balance_cents: int = 0
    receipt_url: str | None = None


class ConsultationPaymentRequest(BaseModel):
    """Receptionist settling a consultation fee at the front desk."""

    payment_method: str = Field(
        ..., pattern=r"^(cash|mpesa|insurance|exemption)$"
    )
    amount_cents: int | None = Field(None, gt=0)
    reference_number: str | None = Field(None, max_length=100)
    mpesa_transaction_id: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


class ConsultationFeeUpdate(BaseModel):
    """Front-desk correction to the fee charged for a visit."""

    amount_cents: int = Field(..., gt=0)


class ConsultationPaymentResponse(BaseModel):
    """Outcome of collecting a consultation fee, with a receipt to print."""

    encounter_id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    fee_cents: int
    paid_cents: int
    balance_cents: int
    status: str
    payment_id: uuid.UUID | None = None
    payment_method: str | None = None
    reference_number: str | None = None
    received_by: uuid.UUID | None = None
    paid_at: datetime | None = None
    receipt_url: str


class DepartmentOption(BaseModel):
    """Minimal department option for the front-desk routing picker."""

    id: uuid.UUID
    code: str
    name: str
    department_type: str
    is_active: bool

    model_config = {"from_attributes": True}


class ClinicianProfile(BaseModel):
    """Who the signed-in clinician is, and which unit they answer for."""

    staff_id: uuid.UUID | None = None
    name: str = ""
    profession: str = ""
    specialty: str | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None


class ClinicalWorklistCounts(BaseModel):
    """Today's scoped workload, counted by encounter status."""

    waiting: int = 0
    in_consultation: int = 0
    completed: int = 0
    total: int = 0


class ClinicalWorklistItem(EncounterResponse):
    """One encounter in a clinician's worklist, with its routing labels."""

    department_name: str | None = None
    attending_doctor_name: str | None = None


class ClinicalWorklistResponse(BaseModel):
    """A clinician's workspace: who they are, and whose care they owe today."""

    scope: str
    facility_wide: bool = False
    clinician: ClinicianProfile
    counts: ClinicalWorklistCounts
    items: list[ClinicalWorklistItem]
