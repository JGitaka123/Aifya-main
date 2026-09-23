import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class ClinicalTrial(AuditMixin, Base):
    """
    Clinical trial registry.
    Supports ICH-GCP compliance, REDCap integration, and AI-powered screening.
    """

    __tablename__ = "clinical_trials"
    __table_args__ = (
        Index("ix_trials_facility_status", "facility_id", "status"),
    )

    # Trial identification
    trial_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nct_number: Mapped[str | None] = mapped_column(String(20))
    pactr_number: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    short_title: Mapped[str | None] = mapped_column(String(200))

    # Classification
    phase: Mapped[str | None] = mapped_column(
        String(20)
    )  # I, II, III, IV, observational, registry
    study_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # interventional, observational, registry, diagnostic, pragmatic, adaptive
    therapeutic_area: Mapped[str | None] = mapped_column(String(100))

    # Sponsor & oversight
    sponsor: Mapped[str] = mapped_column(String(200), nullable=False)
    principal_investigator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    co_investigators: Mapped[dict | None] = mapped_column(JSONB)
    irb_approval_number: Mapped[str | None] = mapped_column(String(50))
    irb_approval_date: Mapped[date | None] = mapped_column(Date)
    irb_expiry_date: Mapped[date | None] = mapped_column(Date)
    ethics_committee: Mapped[str | None] = mapped_column(String(200))
    nacosti_permit: Mapped[str | None] = mapped_column(String(50))

    # Protocol
    protocol_version: Mapped[str] = mapped_column(String(20), nullable=False)
    protocol_date: Mapped[date] = mapped_column(Date, nullable=False)
    protocol_document_url: Mapped[str | None] = mapped_column(String(500))
    amendments: Mapped[dict | None] = mapped_column(JSONB)

    # Eligibility criteria (structured for AI screening)
    inclusion_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    exclusion_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_enrollment: Mapped[int | None] = mapped_column(Integer)

    # REDCap integration
    redcap_project_id: Mapped[int | None] = mapped_column(Integer)
    redcap_api_url: Mapped[str | None] = mapped_column(String(500))
    redcap_api_token_vault_key: Mapped[str | None] = mapped_column(
        String(100)
    )  # Vault reference — NEVER store token in DB
    redcap_field_mapping: Mapped[dict | None] = mapped_column(JSONB)
    redcap_sync_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    redcap_sync_mode: Mapped[str] = mapped_column(
        String(20), default="bidirectional", nullable=False
    )  # push_only, pull_only, bidirectional

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="setup", nullable=False
    )  # setup, recruiting, active, follow_up, completed, suspended, terminated, withdrawn

    # Dates
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class TrialParticipant(AuditMixin, Base):
    """
    Links patients to clinical trials.
    Trial patients get alert banner on EVERY clinical encounter (CLAUDE.md).
    """

    __tablename__ = "trial_participants"
    __table_args__ = (
        UniqueConstraint("trial_id", "patient_id", name="uq_trial_patient"),
        UniqueConstraint(
            "trial_id", "participant_number", name="uq_trial_participant_number"
        ),
        Index("ix_trial_participants_patient", "facility_id", "patient_id"),
        Index("ix_trial_participants_trial", "trial_id", "status"),
    )

    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_trials.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )

    # Identifiers
    participant_number: Mapped[str] = mapped_column(String(30), nullable=False)
    randomization_arm: Mapped[str | None] = mapped_column(String(50))
    randomization_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="screened", nullable=False
    )  # pre_screened, screened, screen_failed, enrolled, active, on_hold,
    #    completed, withdrawn, lost_to_followup, deceased

    # Screening
    screening_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    screened_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    screen_fail_reason: Mapped[str | None] = mapped_column(Text)
    eligibility_check: Mapped[dict | None] = mapped_column(JSONB)
    ai_eligibility_score: Mapped[float | None] = mapped_column(Float)

    # Consent
    consent_version: Mapped[str | None] = mapped_column(String(20))
    consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_document_url: Mapped[str | None] = mapped_column(String(500))
    consent_witness: Mapped[str | None] = mapped_column(String(200))
    consent_withdrawn: Mapped[bool] = mapped_column(default=False, nullable=False)
    consent_withdrawn_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_withdrawn_reason: Mapped[str | None] = mapped_column(Text)

    # Enrollment
    enrollment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrolled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )

    # Completion
    completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_status: Mapped[str | None] = mapped_column(String(30))
    withdrawal_reason: Mapped[str | None] = mapped_column(Text)

    # REDCap
    redcap_record_id: Mapped[str | None] = mapped_column(String(50))
    last_redcap_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redcap_sync_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # synced, pending, error, conflict


class TrialVisitSchedule(Base):
    """Defines the visit schedule template for a trial protocol."""

    __tablename__ = "trial_visit_schedule"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_trials.id"), nullable=False
    )
    visit_code: Mapped[str] = mapped_column(String(20), nullable=False)
    visit_name: Mapped[str] = mapped_column(String(100), nullable=False)
    day_from_enrollment: Mapped[int] = mapped_column(Integer, nullable=False)
    window_before_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_after_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_assessments: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    is_mandatory: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TrialParticipantVisit(AuditMixin, Base):
    """Actual visit record for a trial participant."""

    __tablename__ = "trial_participant_visits"
    __table_args__ = (
        Index("ix_tpv_participant", "participant_id", "status"),
    )

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trial_participants.id"), nullable=False
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trial_visit_schedule.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )

    # Timing
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, completed, missed, cancelled, out_of_window, unscheduled

    # Completion tracking
    assessments_completed: Mapped[dict | None] = mapped_column(JSONB)
    protocol_deviations: Mapped[dict | None] = mapped_column(JSONB)

    # AI monitoring
    ai_window_alert: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_missing_assessments: Mapped[dict | None] = mapped_column(JSONB)

    # REDCap sync
    redcap_synced: Mapped[bool] = mapped_column(default=False, nullable=False)
    redcap_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrialAdverseEvent(AuditMixin, Base):
    """
    Adverse event in a clinical trial.
    SAE MUST be reportable to sponsor within 24 hours (CLAUDE.md: Clinical Safety).
    """

    __tablename__ = "trial_adverse_events"
    __table_args__ = (
        Index("ix_tae_participant", "participant_id"),
        Index("ix_tae_trial_serious", "trial_id", "is_serious"),
    )

    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trial_participants.id"), nullable=False
    )
    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_trials.id"), nullable=False
    )

    # Classification
    ae_term: Mapped[str] = mapped_column(Text, nullable=False)
    meddra_code: Mapped[str | None] = mapped_column(String(20))
    meddra_pt: Mapped[str | None] = mapped_column(String(200))
    meddra_soc: Mapped[str | None] = mapped_column(String(200))
    ctcae_grade: Mapped[int | None] = mapped_column(SmallInteger)  # 1-5

    # Severity & seriousness
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # mild, moderate, severe
    is_serious: Mapped[bool] = mapped_column(default=False, nullable=False)
    seriousness_criteria: Mapped[dict | None] = mapped_column(JSONB)

    # Causality
    relatedness: Mapped[str | None] = mapped_column(
        String(30)
    )  # unrelated, unlikely, possible, probable, definite

    # Dates
    onset_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolution_date: Mapped[date | None] = mapped_column(Date)

    # Outcome
    outcome: Mapped[str | None] = mapped_column(String(30))
    action_taken: Mapped[str | None] = mapped_column(String(30))

    # Reporting
    reported_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )
    reported_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # SAE reporting (time-critical: 24-hour window)
    sae_aware_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sae_reported_to_sponsor: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    sae_reported_to_irb: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sae_report_document_url: Mapped[str | None] = mapped_column(String(500))

    # REDCap
    redcap_synced: Mapped[bool] = mapped_column(default=False, nullable=False)


class TrialAIScreening(Base):
    """
    AI screening log — tracks AI-suggested trial matches.
    Runs as async Celery task scanning encounters against active trial criteria.
    """

    __tablename__ = "trial_ai_screening"
    __table_args__ = (
        Index("ix_screening_patient_trial", "patient_id", "trial_id"),
        Index("ix_screening_facility", "facility_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_trials.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )

    # AI assessment
    eligibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_met: Mapped[dict] = mapped_column(JSONB, nullable=False)
    criteria_not_met: Mapped[dict | None] = mapped_column(JSONB)
    criteria_unknown: Mapped[dict | None] = mapped_column(JSONB)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(50))

    # Investigator action
    investigator_reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)
    investigator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id")
    )
    investigator_decision: Mapped[str | None] = mapped_column(
        String(20)
    )  # proceed_to_screen, not_eligible, defer, already_screened
    review_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
