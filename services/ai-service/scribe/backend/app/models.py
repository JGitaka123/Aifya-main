from datetime import datetime
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re

# -----------------
# Enum Models
# -----------------

class Severity(str, Enum):
    BLOCK = "BLOCK"
    WARNING = "WARNING"
    INFO = "INFO"

class EncounterType(str, Enum):
    OUTPATIENT = "outpatient"
    INPATIENT = "inpatient"
    EMERGENCY = "emergency"

class EncounterStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    SCRIBED = "scribed"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"

class ScrubStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    BLOCKED = "blocked"
    WARNINGS_ONLY = "warnings_only"
    OVERRIDDEN = "overridden"

class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"

class DischargeStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    SENT_TO_QAFYA = "sent_to_qafya"

class UserRole(str, Enum):
    CLINICIAN = "clinician"
    BILLING_ADMIN = "billing_admin"
    FACILITY_ADMIN = "facility_admin"
    SUPERADMIN = "superadmin"

# -----------------
# Clinical Models
# -----------------

class VitalSign(BaseModel):
    name: str = Field(..., examples=["Blood Pressure"])
    value: str = Field(..., examples=["120/80 mmHg"])
    loinc_code: Optional[str] = Field(None, examples=["85354-9"])
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    model_config = ConfigDict(from_attributes=True)

class Medication(BaseModel):
    name: str = Field(..., examples=["Amoxicillin"])
    dose: str = Field("As prescribed", examples=["500mg"])
    route: str = Field("Oral", examples=["Oral"])
    frequency: str = Field("Once daily", examples=["TID"])
    duration: str = Field("Ongoing", examples=["5 days"])
    is_new: bool = Field(default=True, examples=[True])
    model_config = ConfigDict(from_attributes=True)

class Diagnosis(BaseModel):
    name: str = Field(..., examples=["Essential hypertension"])
    icd11_suggested: Optional[str] = Field(None, examples=["BA00"])
    icd11_validated: Optional[str] = Field(None, examples=["BA00.Z"])
    is_primary: bool = Field(default=False, examples=[True])
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    model_config = ConfigDict(from_attributes=True)

class LabOrder(BaseModel):
    test_name: str = Field(..., examples=["Full Blood Count"])
    loinc_code: Optional[str] = Field(None, examples=["58410-2"])
    urgency: str = Field(default="routine", examples=["stat"])
    model_config = ConfigDict(from_attributes=True)

class Procedure(BaseModel):
    name: str = Field(..., examples=["Appendectomy"])
    ichi_code: Optional[str] = Field(None, examples=["KBD.40"])
    requires_preauth: bool = Field(default=False, examples=[True])
    model_config = ConfigDict(from_attributes=True)

class ClinicalExtraction(BaseModel):
    chief_complaint: Optional[str] = Field(None, examples=["Patient complains of severe headache for 3 days."])
    reporting_problem: Optional[str] = Field(None, examples=["Recurrent migraine-like headaches interfering with work."])
    symptoms: Optional[str] = Field(None, examples=["Throbbing headache, photophobia, nausea."])
    hpi: Optional[str] = Field(None, examples=["Patient is a 45yo male presenting with throbbing bifrontal headache..."])
    vitals: List[VitalSign] = Field(default_factory=list)
    physical_exam: Optional[str] = Field(None, examples=["Neuro exam is non-focal. BP elevated."])
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    lab_orders: List[LabOrder] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    procedures: List[Procedure] = Field(default_factory=list)
    disposition: Optional[str] = Field(None, examples=["Discharge to home."])
    follow_up: Optional[str] = Field(None, examples=["Return in 1 week for BP check."])
    suggested_tests: List[str] = Field(default_factory=list, description="AI-suggested tests based on clinical context.")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during NLP extraction/validation.")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_config = ConfigDict(from_attributes=True)

# -----------------
# Claims Models
# -----------------

class RuleViolation(BaseModel):
    rule_id: str = Field(..., examples=["SHA-R3a"])
    rule_name: str = Field(..., examples=["Clinical Evidence Required"])
    severity: Severity = Field(..., examples=[Severity.BLOCK])
    message: str = Field(..., examples=["Hypertension diagnosis requires BP vitals."])
    suggested_fix: str = Field(..., examples=["Please return to the SOAP note and enter the Blood Pressure reading in the Vitals section."])
    model_config = ConfigDict(from_attributes=True)

class ScrubResult(BaseModel):
    status: ScrubStatus = Field(..., examples=[ScrubStatus.BLOCKED])
    violations: List[RuleViolation] = Field(default_factory=list)
    scrubbed_at: datetime = Field(default_factory=datetime.utcnow)
    can_submit: bool = Field(..., examples=[False])
    model_config = ConfigDict(from_attributes=True)

# -----------------
# Discharge Models
# -----------------

class DischargeSummary(BaseModel):
    id: Optional[str] = None
    patient_name: str = Field(..., examples=["John Doe"])
    sha_member_no: str = Field(..., examples=["SHA123456789"])
    admission_date: datetime = Field(..., examples=["2026-03-01T10:00:00Z"])
    discharge_date: datetime = Field(..., examples=["2026-03-05T14:00:00Z"])
    length_of_stay_days: int = Field(..., examples=[4])
    admission_diagnosis: str = Field(..., examples=["Community Acquired Pneumonia (CA40)"])
    final_diagnosis: str = Field(..., examples=["Bacterial Pneumonia, resolved (CA40)"])
    
    # Facility specific fields from paper form
    age: str = Field("", examples=["45"])
    sex: str = Field("", examples=["Male"])
    ward: str = Field("", examples=["Medical Ward B"])
    ip_no: str = Field("", examples=["IP-2026-001"])
    attending_doctors: str = Field("", examples=["Dr. Smith, Dr. Jane"])
    other_illness: str = Field("", description="Other illness or comorbidities")
    complications: str = Field("", description="Complications during hospital stay")
    doctor_qualification: str = Field("", examples=["MBChB, MMed"])
    
    history_of_present_illness: str = Field("", description="Brief story of why the patient came to the hospital")
    hospital_course: str = Field("", description="Chronological summary of what happened during admission")
    clinical_narrative: Optional[str] = None # Legacy field fallback
    procedures: List[Procedure] = Field(default_factory=list)
    key_investigations: List[dict] = Field(default_factory=list, description="Trend data for lab results")
    discharge_medications: List[Medication] = Field(default_factory=list)
    condition_at_discharge: str = Field(..., examples=["Stable, afebrile, O2 sat 98% on room air."])
    follow_up_plan: str = Field(..., examples=["Follow up in chest clinic in 2 weeks."])
    red_flags: str = Field(..., examples=["Return if you experience shortness of breath or fever > 38.5C."])
    model_config = ConfigDict(from_attributes=True)

# -----------------
# Auth Models
# -----------------

class LoginRequest(BaseModel):
    email: str = Field(..., examples=["doctor@maryhelphospital.org"])
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email format")
        return v.strip().lower()

class UserCreate(BaseModel):
    email: str = Field(..., examples=["doctor@maryhelphospital.org"])
    password: str = Field(..., min_length=8, examples=["secureP@ssw0rd123!"])
    full_name: str = Field(..., min_length=2, examples=["Dr. Jane Smith"])
    role: UserRole = Field(..., examples=[UserRole.CLINICIAN])
    license_no: Optional[str] = Field(None, examples=["KMPDB-12345"])

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email format")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one digit")
        return v

    model_config = ConfigDict(from_attributes=True)

class AdminUserCreate(UserCreate):
    """Same as UserCreate but used by admin endpoints."""
    pass

class UserResponse(BaseModel):
    id: str = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    email: str = Field(..., examples=["doctor@maryhelphospital.org"])
    full_name: str = Field(..., examples=["Dr. Jane Smith"])
    role: UserRole = Field(..., examples=[UserRole.CLINICIAN])
    is_active: bool = Field(default=True)
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Expiration time in seconds")
    user: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)

# -----------------
# API Request/Response Models
# -----------------

class TranscriptInput(BaseModel):
    transcript: str = Field(..., min_length=10, examples=["[CLINICIAN]: Habari yako? Shida ni nini leo? [PATIENT]: Kichwa inaniuma sana..."])
    model_config = ConfigDict(from_attributes=True)

class ScrubRequest(BaseModel):
    extraction: ClinicalExtraction
    sha_status: str = Field(..., examples=["ACTIVE"])
    sha_package: str = Field(..., examples=["SHIF"])
    amount: float = Field(..., gt=0, examples=[4500.00], description="Amount billed in KES")
    encounter_date: datetime = Field(..., examples=["2026-03-09T10:00:00Z"])
    encounter_type: EncounterType = Field(default=EncounterType.OUTPATIENT)
    has_preauth: bool = Field(default=False)
    model_config = ConfigDict(from_attributes=True)

class DischargeRequest(BaseModel):
    admission_id: str = Field(..., min_length=1, examples=["adm_12345"])
    patient_id: str = Field(..., min_length=1, examples=["pat_67890"])
    model_config = ConfigDict(from_attributes=True)

class SyncNoteRequest(BaseModel):
    qafya_encounter_id: str = Field(..., min_length=1, examples=["enc_qafya_789"])
    soap_json: dict = Field(..., examples=[{"subjective": "...", "objective": "..."}])
    model_config = ConfigDict(from_attributes=True)

class SyncDischargeRequest(BaseModel):
    discharge_id: str = Field(..., min_length=1, examples=["dis_12345"])
    model_config = ConfigDict(from_attributes=True)

class ClaimOverrideRequest(BaseModel):
    reason: str = Field(..., min_length=10, examples=["Clinical justification reviewed and approved by senior billing officer."])
    model_config = ConfigDict(from_attributes=True)

class DischargeStatusUpdate(BaseModel):
    new_status: str = Field(..., examples=["reviewed"])

    @field_validator("new_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"draft", "reviewed", "approved", "sent_to_qafya"}
        if v not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        return v

class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    components: dict[str, str] = Field(..., examples=[{"aifya_db": "connected", "qafya_db": "connected"}])
    model_config = ConfigDict(from_attributes=True)
