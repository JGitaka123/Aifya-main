import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Trial ────────────────────────────────────────────────────────────────────


class TrialCreate(BaseModel):
    """Schema for creating a clinical trial."""

    title: str = Field(..., max_length=5000)
    short_title: str | None = Field(None, max_length=200)
    phase: str | None = Field(
        None, pattern=r"^(I|II|III|IV|observational|registry)$"
    )
    study_type: str = Field(
        ...,
        pattern=r"^(interventional|observational|registry|diagnostic|pragmatic|adaptive)$",
    )
    therapeutic_area: str | None = Field(None, max_length=100)
    sponsor: str = Field(..., max_length=200)
    principal_investigator_id: uuid.UUID | None = None
    co_investigators: dict | None = None
    irb_approval_number: str | None = Field(None, max_length=50)
    irb_approval_date: date | None = None
    irb_expiry_date: date | None = None
    ethics_committee: str | None = Field(None, max_length=200)
    nacosti_permit: str | None = Field(None, max_length=50)
    protocol_version: str = Field(..., max_length=20)
    protocol_date: date
    protocol_document_url: str | None = Field(None, max_length=500)
    inclusion_criteria: dict = Field(...)
    exclusion_criteria: dict = Field(...)
    target_enrollment: int | None = Field(None, ge=1)
    nct_number: str | None = Field(None, max_length=20)
    pactr_number: str | None = Field(None, max_length=20)
    redcap_project_id: int | None = None
    redcap_api_url: str | None = Field(None, max_length=500)
    redcap_api_token_vault_key: str | None = Field(None, max_length=100)
    redcap_field_mapping: dict | None = None
    redcap_sync_enabled: bool = True
    redcap_sync_mode: str = Field(
        default="bidirectional",
        pattern=r"^(push_only|pull_only|bidirectional)$",
    )
    start_date: date | None = None
    end_date: date | None = None


class TrialUpdate(BaseModel):
    """Schema for updating a clinical trial."""

    title: str | None = Field(None, max_length=5000)
    short_title: str | None = Field(None, max_length=200)
    phase: str | None = Field(
        None, pattern=r"^(I|II|III|IV|observational|registry)$"
    )
    therapeutic_area: str | None = Field(None, max_length=100)
    principal_investigator_id: uuid.UUID | None = None
    co_investigators: dict | None = None
    irb_approval_number: str | None = Field(None, max_length=50)
    irb_approval_date: date | None = None
    irb_expiry_date: date | None = None
    ethics_committee: str | None = Field(None, max_length=200)
    nacosti_permit: str | None = Field(None, max_length=50)
    protocol_version: str | None = Field(None, max_length=20)
    protocol_date: date | None = None
    protocol_document_url: str | None = Field(None, max_length=500)
    amendments: dict | None = None
    inclusion_criteria: dict | None = None
    exclusion_criteria: dict | None = None
    target_enrollment: int | None = Field(None, ge=1)
    nct_number: str | None = Field(None, max_length=20)
    pactr_number: str | None = Field(None, max_length=20)
    redcap_project_id: int | None = None
    redcap_api_url: str | None = Field(None, max_length=500)
    redcap_api_token_vault_key: str | None = Field(None, max_length=100)
    redcap_field_mapping: dict | None = None
    redcap_sync_enabled: bool | None = None
    redcap_sync_mode: str | None = Field(
        None, pattern=r"^(push_only|pull_only|bidirectional)$"
    )
    start_date: date | None = None
    end_date: date | None = None


class TrialStatusUpdate(BaseModel):
    """Schema for updating trial status."""

    status: str = Field(
        ...,
        pattern=r"^(setup|recruiting|active|follow_up|completed|suspended|terminated|withdrawn)$",
    )


class TrialResponse(BaseModel):
    """Schema for trial responses."""

    id: uuid.UUID
    trial_code: str
    nct_number: str | None
    pactr_number: str | None
    title: str
    short_title: str | None
    phase: str | None
    study_type: str
    therapeutic_area: str | None
    sponsor: str
    principal_investigator_id: uuid.UUID | None
    co_investigators: dict | None
    irb_approval_number: str | None
    irb_approval_date: date | None
    irb_expiry_date: date | None
    ethics_committee: str | None
    nacosti_permit: str | None
    protocol_version: str
    protocol_date: date
    protocol_document_url: str | None
    amendments: dict | None
    inclusion_criteria: dict
    exclusion_criteria: dict
    target_enrollment: int | None
    redcap_project_id: int | None
    redcap_api_url: str | None
    redcap_field_mapping: dict | None
    redcap_sync_enabled: bool
    redcap_sync_mode: str
    status: str
    start_date: date | None
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TrialListItem(BaseModel):
    """Trial in list view."""

    id: uuid.UUID
    trial_code: str
    title: str
    short_title: str | None
    phase: str | None
    study_type: str
    therapeutic_area: str | None
    sponsor: str
    status: str
    target_enrollment: int | None
    enrolled_count: int = 0
    start_date: date | None
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TrialListResponse(BaseModel):
    """Trial list response."""

    items: list[TrialListItem]
    total: int


# ── Participant ──────────────────────────────────────────────────────────────


class ParticipantEnroll(BaseModel):
    """Schema for enrolling a participant in a trial."""

    patient_id: uuid.UUID
    randomization_arm: str | None = Field(None, max_length=50)
    consent_version: str | None = Field(None, max_length=20)
    consent_date: datetime | None = None
    consent_document_url: str | None = Field(None, max_length=500)
    consent_witness: str | None = Field(None, max_length=200)


class ParticipantStatusUpdate(BaseModel):
    """Schema for updating participant status."""

    status: str = Field(
        ...,
        pattern=r"^(pre_screened|screened|screen_failed|enrolled|active|on_hold|completed|withdrawn|lost_to_followup|deceased)$",
    )
    screen_fail_reason: str | None = None
    withdrawal_reason: str | None = None
    completion_status: str | None = Field(None, max_length=30)


class ParticipantResponse(BaseModel):
    """Schema for participant responses."""

    id: uuid.UUID
    trial_id: uuid.UUID
    patient_id: uuid.UUID
    participant_number: str
    randomization_arm: str | None
    randomization_date: datetime | None
    status: str
    screening_date: datetime | None
    screened_by: uuid.UUID | None
    screen_fail_reason: str | None
    eligibility_check: dict | None
    ai_eligibility_score: float | None
    consent_version: str | None
    consent_date: datetime | None
    consent_document_url: str | None
    consent_witness: str | None
    consent_withdrawn: bool
    consent_withdrawn_date: datetime | None
    consent_withdrawn_reason: str | None
    enrollment_date: datetime | None
    enrolled_by: uuid.UUID | None
    completion_date: datetime | None
    completion_status: str | None
    withdrawal_reason: str | None
    redcap_record_id: str | None
    redcap_sync_status: str
    last_redcap_sync: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParticipantListItem(BaseModel):
    """Participant in list view."""

    id: uuid.UUID
    trial_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    participant_number: str
    randomization_arm: str | None
    status: str
    screening_date: datetime | None
    enrollment_date: datetime | None
    ai_eligibility_score: float | None
    consent_date: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParticipantListResponse(BaseModel):
    """Participant list response."""

    items: list[ParticipantListItem]
    total: int


# ── Visit Schedule ───────────────────────────────────────────────────────────


class VisitScheduleCreate(BaseModel):
    """Schema for creating a visit schedule entry."""

    visit_code: str = Field(..., max_length=20)
    visit_name: str = Field(..., max_length=100)
    day_from_enrollment: int
    window_before_days: int = Field(default=0, ge=0)
    window_after_days: int = Field(default=0, ge=0)
    required_assessments: list[dict] = Field(default_factory=list)
    is_mandatory: bool = True
    sort_order: int = 0


class VisitScheduleResponse(BaseModel):
    """Schema for visit schedule responses."""

    id: uuid.UUID
    trial_id: uuid.UUID
    visit_code: str
    visit_name: str
    day_from_enrollment: int
    window_before_days: int
    window_after_days: int
    required_assessments: list[dict]
    is_mandatory: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Participant Visit ────────────────────────────────────────────────────────


class ParticipantVisitCreate(BaseModel):
    """Schema for recording a participant visit."""

    schedule_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    scheduled_date: date
    actual_date: date | None = None
    status: str = Field(
        default="scheduled",
        pattern=r"^(scheduled|completed|missed|cancelled|out_of_window|unscheduled)$",
    )
    assessments_completed: dict | None = None
    protocol_deviations: dict | None = None


class ParticipantVisitUpdate(BaseModel):
    """Schema for updating a participant visit."""

    encounter_id: uuid.UUID | None = None
    actual_date: date | None = None
    status: str | None = Field(
        None,
        pattern=r"^(scheduled|completed|missed|cancelled|out_of_window|unscheduled)$",
    )
    assessments_completed: dict | None = None
    protocol_deviations: dict | None = None


class ParticipantVisitResponse(BaseModel):
    """Schema for participant visit responses."""

    id: uuid.UUID
    participant_id: uuid.UUID
    schedule_id: uuid.UUID
    encounter_id: uuid.UUID | None
    scheduled_date: date
    actual_date: date | None
    status: str
    assessments_completed: dict | None
    protocol_deviations: dict | None
    ai_window_alert: bool
    ai_missing_assessments: dict | None
    redcap_synced: bool
    redcap_sync_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Adverse Event ────────────────────────────────────────────────────────────


class AdverseEventCreate(BaseModel):
    """
    Schema for reporting an adverse event.
    SAE MUST be reportable to sponsor within 24 hours.
    """

    participant_id: uuid.UUID
    ae_term: str = Field(..., max_length=5000)
    meddra_code: str | None = Field(None, max_length=20)
    meddra_pt: str | None = Field(None, max_length=200)
    meddra_soc: str | None = Field(None, max_length=200)
    ctcae_grade: int | None = Field(None, ge=1, le=5)
    severity: str = Field(
        ..., pattern=r"^(mild|moderate|severe)$"
    )
    is_serious: bool = False
    seriousness_criteria: dict | None = None
    relatedness: str | None = Field(
        None,
        pattern=r"^(unrelated|unlikely|possible|probable|definite)$",
    )
    onset_date: date
    resolution_date: date | None = None
    outcome: str | None = Field(None, max_length=30)
    action_taken: str | None = Field(None, max_length=30)


class AdverseEventResponse(BaseModel):
    """Schema for adverse event responses."""

    id: uuid.UUID
    participant_id: uuid.UUID
    trial_id: uuid.UUID
    ae_term: str
    meddra_code: str | None
    meddra_pt: str | None
    meddra_soc: str | None
    ctcae_grade: int | None
    severity: str
    is_serious: bool
    seriousness_criteria: dict | None
    relatedness: str | None
    onset_date: date
    resolution_date: date | None
    outcome: str | None
    action_taken: str | None
    reported_by: uuid.UUID
    reported_date: datetime
    sae_aware_date: datetime | None
    sae_reported_to_sponsor: datetime | None
    sae_reported_to_irb: datetime | None
    sae_report_document_url: str | None
    redcap_synced: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdverseEventListItem(BaseModel):
    """AE in list view."""

    id: uuid.UUID
    participant_id: uuid.UUID
    participant_number: str | None = None
    ae_term: str
    severity: str
    is_serious: bool
    ctcae_grade: int | None
    relatedness: str | None
    onset_date: date
    resolution_date: date | None
    outcome: str | None
    reported_date: datetime

    model_config = {"from_attributes": True}


class AdverseEventListResponse(BaseModel):
    """AE list response."""

    items: list[AdverseEventListItem]
    total: int


class SAEReportSubmit(BaseModel):
    """Schema for submitting SAE report to sponsor/IRB."""

    sae_aware_date: datetime
    sae_report_document_url: str | None = Field(None, max_length=500)
    reported_to_sponsor: bool = False
    reported_to_irb: bool = False


# ── AI Screening ─────────────────────────────────────────────────────────────


class AIScreeningResponse(BaseModel):
    """Schema for AI screening result responses."""

    id: uuid.UUID
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    trial_id: uuid.UUID
    encounter_id: uuid.UUID | None
    eligibility_score: float
    criteria_met: dict
    criteria_not_met: dict | None
    criteria_unknown: dict | None
    ai_reasoning: str | None
    model_version: str | None
    investigator_reviewed: bool
    investigator_id: uuid.UUID | None
    investigator_decision: str | None
    review_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIScreeningListResponse(BaseModel):
    """AI screening list response."""

    items: list[AIScreeningResponse]
    total: int


class AIScreeningCreate(BaseModel):
    """Schema for requesting an AI eligibility screening."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None


class AIScreeningReview(BaseModel):
    """Schema for investigator review of AI screening result."""

    decision: str = Field(
        ...,
        pattern=r"^(proceed_to_screen|not_eligible|defer|already_screened)$",
    )
    review_notes: str | None = Field(None, max_length=2000)


# ── Summary ──────────────────────────────────────────────────────────────────


class TrialsSummary(BaseModel):
    """Clinical trials summary stats."""

    total_trials: int = 0
    recruiting_trials: int = 0
    active_trials: int = 0
    completed_trials: int = 0
    total_participants: int = 0
    enrolled_participants: int = 0
    screen_failures: int = 0
    total_adverse_events: int = 0
    serious_adverse_events: int = 0
    pending_ai_screenings: int = 0
