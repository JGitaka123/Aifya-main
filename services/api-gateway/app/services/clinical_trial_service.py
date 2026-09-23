import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_trial import (
    ClinicalTrial,
    TrialAdverseEvent,
    TrialAIScreening,
    TrialParticipant,
    TrialParticipantVisit,
    TrialVisitSchedule,
)
from app.models.diagnosis import Diagnosis
from app.models.patient import Patient
from app.schemas.clinical_trial import (
    AdverseEventCreate,
    AdverseEventListItem,
    AIScreeningCreate,
    AIScreeningResponse,
    AIScreeningReview,
    ParticipantEnroll,
    ParticipantListItem,
    ParticipantStatusUpdate,
    ParticipantVisitCreate,
    ParticipantVisitUpdate,
    SAEReportSubmit,
    TrialCreate,
    TrialListItem,
    TrialsSummary,
    TrialStatusUpdate,
    TrialUpdate,
    VisitScheduleCreate,
)


_AI_SCREENING_MODEL = "aifya-rules-v1"


def _patient_age(date_of_birth: date, today: date) -> int:
    """
    Completed years between a date of birth and a reference date.

    @param date_of_birth: Patient date of birth
    @param today: Reference date
    @returns Age in completed years
    """
    return (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )


def _evaluate_eligibility(
    inclusion: dict,
    exclusion: dict,
    age: int | None,
    conditions: list[str],
) -> tuple[float, dict, dict, dict, str]:
    """
    Score a patient against a trial's eligibility criteria.

    Structured criteria (age_min, age_max, conditions) are checked against the
    patient record. Free-text criteria cannot be judged from structured data,
    so they are reported as unknown and left to the investigator. The score
    counts a met criterion as one and an unknown one as a half, so an
    unevaluated criterion reads as neither a pass nor a fail.

    @param inclusion: Trial inclusion criteria
    @param exclusion: Trial exclusion criteria
    @param age: Patient age in years, or None when unknown
    @param conditions: Active diagnosis descriptions for the patient
    @returns Tuple of score, met, not_met, unknown and reasoning
    """
    met: dict[str, str] = {}
    not_met: dict[str, str] = {}
    unknown: dict[str, str] = {}
    haystack = " | ".join(conditions).lower()

    def check_age(key: str, limit: object, is_minimum: bool) -> None:
        if not isinstance(limit, (int, float)):
            return
        comparison = ">=" if is_minimum else "<="
        label = f"{key} {comparison} {limit}"
        if age is None:
            unknown[key] = f"{label} - patient date of birth unknown"
            return
        passed = age >= limit if is_minimum else age <= limit
        if passed:
            met[key] = f"Age {age} satisfies {label}"
        else:
            not_met[key] = f"Age {age} fails {label}"

    check_age("age_min", inclusion.get("age_min"), True)
    check_age("age_max", inclusion.get("age_max"), False)

    for item in inclusion.get("conditions") or []:
        text = str(item)
        key = f"condition: {text}"
        if text.lower() in haystack:
            met[key] = "Matches an active diagnosis"
        elif not haystack:
            unknown[key] = "No active diagnoses on file to match against"
        else:
            not_met[key] = "No matching active diagnosis"

    for item in inclusion.get("criteria") or []:
        unknown[f"inclusion: {item}"] = "Free-text criterion, needs investigator review"

    for item in exclusion.get("criteria") or []:
        unknown[f"exclusion: {item}"] = "Free-text criterion, needs investigator review"

    total = len(met) + len(not_met) + len(unknown)
    score = 0.0 if total == 0 else (len(met) + 0.5 * len(unknown)) / total
    reasoning = (
        f"{len(met)} of {total} criteria met automatically, "
        f"{len(not_met)} failed, {len(unknown)} need investigator review."
    )
    return round(score, 4), met, not_met, unknown, reasoning


class ClinicalTrialService:
    """Service for clinical trial management — ICH-GCP compliant."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Trials ───────────────────────────────────────────────────────────────

    async def create_trial(
        self, data: TrialCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> ClinicalTrial:
        """
        Create a clinical trial.

        @param data: Trial data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created trial
        """
        count = await self.db.execute(
            select(func.count(ClinicalTrial.id)).where(
                ClinicalTrial.facility_id == facility_id,
                ClinicalTrial.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count.scalar() or 0) + 1
        trial_code = f"TRL-{seq:04d}"

        trial = ClinicalTrial(
            facility_id=facility_id,
            trial_code=trial_code,
            title=data.title,
            short_title=data.short_title,
            phase=data.phase,
            study_type=data.study_type,
            therapeutic_area=data.therapeutic_area,
            sponsor=data.sponsor,
            principal_investigator_id=data.principal_investigator_id,
            co_investigators=data.co_investigators,
            irb_approval_number=data.irb_approval_number,
            irb_approval_date=data.irb_approval_date,
            irb_expiry_date=data.irb_expiry_date,
            ethics_committee=data.ethics_committee,
            nacosti_permit=data.nacosti_permit,
            protocol_version=data.protocol_version,
            protocol_date=data.protocol_date,
            protocol_document_url=data.protocol_document_url,
            inclusion_criteria=data.inclusion_criteria,
            exclusion_criteria=data.exclusion_criteria,
            target_enrollment=data.target_enrollment,
            nct_number=data.nct_number,
            pactr_number=data.pactr_number,
            redcap_project_id=data.redcap_project_id,
            redcap_api_url=data.redcap_api_url,
            redcap_api_token_vault_key=data.redcap_api_token_vault_key,
            redcap_field_mapping=data.redcap_field_mapping,
            redcap_sync_enabled=data.redcap_sync_enabled,
            redcap_sync_mode=data.redcap_sync_mode,
            start_date=data.start_date,
            end_date=data.end_date,
            status="setup",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(trial)
        await self.db.flush()
        await self.db.refresh(trial)
        return trial

    async def get_trials(
        self, facility_id: uuid.UUID, status: str | None = None
    ) -> list[TrialListItem]:
        """
        Get trials with enrolled count.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of trials with enrollment counts
        """
        enrolled_sub = (
            select(
                TrialParticipant.trial_id,
                func.count(TrialParticipant.id).label("enrolled_count"),
            )
            .where(
                TrialParticipant.status.in_(["enrolled", "active", "completed"]),
                TrialParticipant.is_deleted == False,  # noqa: E712
            )
            .group_by(TrialParticipant.trial_id)
            .subquery()
        )

        query = (
            select(
                ClinicalTrial,
                func.coalesce(enrolled_sub.c.enrolled_count, 0).label("enrolled_count"),
            )
            .outerjoin(enrolled_sub, ClinicalTrial.id == enrolled_sub.c.trial_id)
            .where(
                ClinicalTrial.facility_id == facility_id,
                ClinicalTrial.is_deleted == False,  # noqa: E712
            )
        )
        if status:
            query = query.where(ClinicalTrial.status == status)
        query = query.order_by(ClinicalTrial.created_at.desc())

        result = await self.db.execute(query)
        return [
            TrialListItem(
                id=t.id,
                trial_code=t.trial_code,
                title=t.title,
                short_title=t.short_title,
                phase=t.phase,
                study_type=t.study_type,
                therapeutic_area=t.therapeutic_area,
                sponsor=t.sponsor,
                status=t.status,
                target_enrollment=t.target_enrollment,
                enrolled_count=ec,
                start_date=t.start_date,
                end_date=t.end_date,
                created_at=t.created_at,
            )
            for t, ec in result.all()
        ]

    async def get_trial(
        self, trial_id: uuid.UUID, facility_id: uuid.UUID
    ) -> ClinicalTrial | None:
        """
        Get a single trial.

        @param trial_id: Trial UUID
        @param facility_id: Facility UUID
        @returns Trial or None
        """
        result = await self.db.execute(
            select(ClinicalTrial).where(
                ClinicalTrial.id == trial_id,
                ClinicalTrial.facility_id == facility_id,
                ClinicalTrial.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_trial(
        self,
        trial_id: uuid.UUID,
        data: TrialUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> ClinicalTrial | None:
        """
        Update a clinical trial.

        @param trial_id: Trial UUID
        @param data: Update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated trial or None
        """
        trial = await self.get_trial(trial_id, facility_id)
        if not trial:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(trial, field, value)
        trial.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(trial)
        return trial

    async def update_trial_status(
        self,
        trial_id: uuid.UUID,
        data: TrialStatusUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> ClinicalTrial | None:
        """
        Update trial status.

        @param trial_id: Trial UUID
        @param data: Status update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated trial or None
        """
        trial = await self.get_trial(trial_id, facility_id)
        if not trial:
            return None

        trial.status = data.status
        trial.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(trial)
        return trial

    # ── Participants ─────────────────────────────────────────────────────────

    async def enroll_participant(
        self,
        trial_id: uuid.UUID,
        data: ParticipantEnroll,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> TrialParticipant:
        """
        Enroll a patient as a trial participant.

        @param trial_id: Trial UUID
        @param data: Enrollment data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created participant
        """
        now = datetime.now(UTC)

        count = await self.db.execute(
            select(func.count(TrialParticipant.id)).where(
                TrialParticipant.trial_id == trial_id,
            )
        )
        seq = (count.scalar() or 0) + 1
        participant_number = f"P-{seq:04d}"

        participant = TrialParticipant(
            facility_id=facility_id,
            trial_id=trial_id,
            patient_id=data.patient_id,
            participant_number=participant_number,
            randomization_arm=data.randomization_arm,
            status="screened",
            screening_date=now,
            screened_by=created_by,
            consent_version=data.consent_version,
            consent_date=data.consent_date,
            consent_document_url=data.consent_document_url,
            consent_witness=data.consent_witness,
            redcap_sync_status="pending",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(participant)
        await self.db.flush()
        await self.db.refresh(participant)
        return participant

    async def get_participants(
        self, trial_id: uuid.UUID, facility_id: uuid.UUID, status: str | None = None
    ) -> list[ParticipantListItem]:
        """
        Get trial participants with patient names.

        @param trial_id: Trial UUID
        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of participants
        """
        query = (
            select(
                TrialParticipant,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
            )
            .join(Patient, TrialParticipant.patient_id == Patient.id)
            .where(
                TrialParticipant.trial_id == trial_id,
                TrialParticipant.facility_id == facility_id,
                TrialParticipant.is_deleted == False,  # noqa: E712
            )
        )
        if status:
            query = query.where(TrialParticipant.status == status)
        query = query.order_by(TrialParticipant.created_at.desc())

        result = await self.db.execute(query)
        return [
            ParticipantListItem(
                id=p.id,
                trial_id=p.trial_id,
                patient_id=p.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                participant_number=p.participant_number,
                randomization_arm=p.randomization_arm,
                status=p.status,
                screening_date=p.screening_date,
                enrollment_date=p.enrollment_date,
                ai_eligibility_score=p.ai_eligibility_score,
                consent_date=p.consent_date,
                created_at=p.created_at,
            )
            for p, pf, pl in result.all()
        ]

    async def get_participant(
        self, participant_id: uuid.UUID, facility_id: uuid.UUID
    ) -> TrialParticipant | None:
        """
        Get a single participant.

        @param participant_id: Participant UUID
        @param facility_id: Facility UUID
        @returns Participant or None
        """
        result = await self.db.execute(
            select(TrialParticipant).where(
                TrialParticipant.id == participant_id,
                TrialParticipant.facility_id == facility_id,
                TrialParticipant.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_participant_status(
        self,
        participant_id: uuid.UUID,
        data: ParticipantStatusUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> TrialParticipant | None:
        """
        Update participant status with enrollment/completion tracking.

        @param participant_id: Participant UUID
        @param data: Status update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated participant or None
        """
        participant = await self.get_participant(participant_id, facility_id)
        if not participant:
            return None

        now = datetime.now(UTC)
        participant.status = data.status
        participant.updated_by = updated_by

        if data.status == "enrolled" and not participant.enrollment_date:
            participant.enrollment_date = now
            participant.enrolled_by = updated_by
        elif data.status == "screen_failed":
            participant.screen_fail_reason = data.screen_fail_reason
        elif data.status in ("completed", "withdrawn", "lost_to_followup", "deceased"):
            participant.completion_date = now
            participant.completion_status = data.completion_status
            if data.status == "withdrawn":
                participant.withdrawal_reason = data.withdrawal_reason
                participant.consent_withdrawn = True
                participant.consent_withdrawn_date = now
                participant.consent_withdrawn_reason = data.withdrawal_reason

        await self.db.flush()
        await self.db.refresh(participant)
        return participant

    # ── Visit Schedule ───────────────────────────────────────────────────────

    async def create_visit_schedule(
        self, trial_id: uuid.UUID, data: VisitScheduleCreate
    ) -> TrialVisitSchedule:
        """
        Create a visit schedule entry for a trial protocol.

        @param trial_id: Trial UUID
        @param data: Visit schedule data
        @returns Created schedule entry
        """
        schedule = TrialVisitSchedule(
            trial_id=trial_id,
            visit_code=data.visit_code,
            visit_name=data.visit_name,
            day_from_enrollment=data.day_from_enrollment,
            window_before_days=data.window_before_days,
            window_after_days=data.window_after_days,
            required_assessments=data.required_assessments,
            is_mandatory=data.is_mandatory,
            sort_order=data.sort_order,
        )
        self.db.add(schedule)
        await self.db.flush()
        await self.db.refresh(schedule)
        return schedule

    async def get_visit_schedule(
        self, trial_id: uuid.UUID
    ) -> list[TrialVisitSchedule]:
        """
        Get visit schedule for a trial.

        @param trial_id: Trial UUID
        @returns List of visit schedule entries
        """
        result = await self.db.execute(
            select(TrialVisitSchedule)
            .where(TrialVisitSchedule.trial_id == trial_id)
            .order_by(TrialVisitSchedule.sort_order.asc())
        )
        return list(result.scalars().all())

    # ── Participant Visits ───────────────────────────────────────────────────

    async def create_participant_visit(
        self,
        participant_id: uuid.UUID,
        data: ParticipantVisitCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> TrialParticipantVisit:
        """
        Record a participant visit.

        @param participant_id: Participant UUID
        @param data: Visit data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created visit record
        """
        visit = TrialParticipantVisit(
            facility_id=facility_id,
            participant_id=participant_id,
            schedule_id=data.schedule_id,
            encounter_id=data.encounter_id,
            scheduled_date=data.scheduled_date,
            actual_date=data.actual_date,
            status=data.status,
            assessments_completed=data.assessments_completed,
            protocol_deviations=data.protocol_deviations,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def get_participant_visits(
        self, participant_id: uuid.UUID
    ) -> list[TrialParticipantVisit]:
        """
        Get visits for a participant.

        @param participant_id: Participant UUID
        @returns List of visits
        """
        result = await self.db.execute(
            select(TrialParticipantVisit)
            .where(TrialParticipantVisit.participant_id == participant_id)
            .order_by(TrialParticipantVisit.scheduled_date.asc())
        )
        return list(result.scalars().all())

    async def update_participant_visit(
        self,
        visit_id: uuid.UUID,
        data: ParticipantVisitUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> TrialParticipantVisit | None:
        """
        Update a participant visit.

        @param visit_id: Visit UUID
        @param data: Update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated visit or None
        """
        result = await self.db.execute(
            select(TrialParticipantVisit).where(
                TrialParticipantVisit.id == visit_id,
                TrialParticipantVisit.facility_id == facility_id,
            )
        )
        visit = result.scalar_one_or_none()
        if not visit:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(visit, field, value)
        visit.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    # ── Adverse Events ───────────────────────────────────────────────────────

    async def report_adverse_event(
        self,
        trial_id: uuid.UUID,
        data: AdverseEventCreate,
        facility_id: uuid.UUID,
        reported_by: uuid.UUID,
    ) -> TrialAdverseEvent:
        """
        Report an adverse event. SAE triggers 24-hour reporting window.

        @param trial_id: Trial UUID
        @param data: AE data
        @param facility_id: Facility UUID
        @param reported_by: Staff UUID
        @returns Created adverse event
        """
        now = datetime.now(UTC)

        ae = TrialAdverseEvent(
            facility_id=facility_id,
            trial_id=trial_id,
            participant_id=data.participant_id,
            ae_term=data.ae_term,
            meddra_code=data.meddra_code,
            meddra_pt=data.meddra_pt,
            meddra_soc=data.meddra_soc,
            ctcae_grade=data.ctcae_grade,
            severity=data.severity,
            is_serious=data.is_serious,
            seriousness_criteria=data.seriousness_criteria,
            relatedness=data.relatedness,
            onset_date=data.onset_date,
            resolution_date=data.resolution_date,
            outcome=data.outcome,
            action_taken=data.action_taken,
            reported_by=reported_by,
            reported_date=now,
            sae_aware_date=now if data.is_serious else None,
            created_by=reported_by,
            updated_by=reported_by,
        )
        self.db.add(ae)
        await self.db.flush()
        await self.db.refresh(ae)
        return ae

    async def get_adverse_events(
        self, trial_id: uuid.UUID, facility_id: uuid.UUID, serious_only: bool = False
    ) -> list[AdverseEventListItem]:
        """
        Get adverse events for a trial.

        @param trial_id: Trial UUID
        @param facility_id: Facility UUID
        @param serious_only: Filter to SAEs only
        @returns List of adverse events
        """
        query = (
            select(
                TrialAdverseEvent,
                TrialParticipant.participant_number.label("p_num"),
            )
            .join(TrialParticipant, TrialAdverseEvent.participant_id == TrialParticipant.id)
            .where(
                TrialAdverseEvent.trial_id == trial_id,
                TrialAdverseEvent.facility_id == facility_id,
                TrialAdverseEvent.is_deleted == False,  # noqa: E712
            )
        )
        if serious_only:
            query = query.where(TrialAdverseEvent.is_serious == True)  # noqa: E712
        query = query.order_by(TrialAdverseEvent.reported_date.desc())

        result = await self.db.execute(query)
        return [
            AdverseEventListItem(
                id=ae.id,
                participant_id=ae.participant_id,
                participant_number=pn,
                ae_term=ae.ae_term,
                severity=ae.severity,
                is_serious=ae.is_serious,
                ctcae_grade=ae.ctcae_grade,
                relatedness=ae.relatedness,
                onset_date=ae.onset_date,
                resolution_date=ae.resolution_date,
                outcome=ae.outcome,
                reported_date=ae.reported_date,
            )
            for ae, pn in result.all()
        ]

    async def get_adverse_event(
        self, ae_id: uuid.UUID, facility_id: uuid.UUID
    ) -> TrialAdverseEvent | None:
        """
        Get a single adverse event.

        @param ae_id: AE UUID
        @param facility_id: Facility UUID
        @returns AE or None
        """
        result = await self.db.execute(
            select(TrialAdverseEvent).where(
                TrialAdverseEvent.id == ae_id,
                TrialAdverseEvent.facility_id == facility_id,
                TrialAdverseEvent.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def submit_sae_report(
        self,
        ae_id: uuid.UUID,
        data: SAEReportSubmit,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> TrialAdverseEvent | None:
        """
        Submit SAE report to sponsor/IRB. MUST be within 24 hours of awareness.

        @param ae_id: AE UUID
        @param data: SAE report data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated AE or None
        """
        ae = await self.get_adverse_event(ae_id, facility_id)
        if not ae or not ae.is_serious:
            return None

        now = datetime.now(UTC)
        ae.sae_aware_date = data.sae_aware_date
        ae.sae_report_document_url = data.sae_report_document_url
        if data.reported_to_sponsor:
            ae.sae_reported_to_sponsor = now
        if data.reported_to_irb:
            ae.sae_reported_to_irb = now
        ae.updated_by = updated_by

        await self.db.flush()
        await self.db.refresh(ae)
        return ae

    # ── AI Screening ─────────────────────────────────────────────────────────

    async def get_ai_screenings(
        self, trial_id: uuid.UUID, facility_id: uuid.UUID, unreviewed_only: bool = False
    ) -> list[AIScreeningResponse]:
        """
        Get AI screening results for a trial, with the candidate's name.

        @param trial_id: Trial UUID
        @param facility_id: Facility UUID
        @param unreviewed_only: Filter to unreviewed only
        @returns Screening results, highest eligibility first
        """
        query = (
            select(
                TrialAIScreening,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
            )
            .join(Patient, TrialAIScreening.patient_id == Patient.id)
            .where(
                TrialAIScreening.trial_id == trial_id,
                TrialAIScreening.facility_id == facility_id,
            )
        )
        if unreviewed_only:
            query = query.where(
                TrialAIScreening.investigator_reviewed == False  # noqa: E712
            )
        query = query.order_by(TrialAIScreening.eligibility_score.desc())

        result = await self.db.execute(query)
        return [
            AIScreeningResponse.model_validate(screening).model_copy(
                update={"patient_name": f"{first or ''} {last or ''}".strip() or None}
            )
            for screening, first, last in result.all()
        ]

    async def review_ai_screening(
        self,
        screening_id: uuid.UUID,
        data: AIScreeningReview,
        facility_id: uuid.UUID,
        investigator_id: uuid.UUID,
    ) -> TrialAIScreening | None:
        """
        Investigator reviews an AI screening result.

        @param screening_id: Screening UUID
        @param data: Review data
        @param facility_id: Facility UUID
        @param investigator_id: Investigator staff UUID
        @returns Updated screening or None
        """
        result = await self.db.execute(
            select(TrialAIScreening).where(
                TrialAIScreening.id == screening_id,
                TrialAIScreening.facility_id == facility_id,
            )
        )
        screening = result.scalar_one_or_none()
        if not screening:
            return None

        screening.investigator_reviewed = True
        screening.investigator_id = investigator_id
        screening.investigator_decision = data.decision
        screening.review_notes = data.review_notes

        await self.db.flush()
        await self.db.refresh(screening)
        return screening

    async def run_ai_screening(
        self,
        trial_id: uuid.UUID,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        encounter_id: uuid.UUID | None = None,
    ) -> AIScreeningResponse | None:
        """
        Score a patient against a trial's eligibility criteria.

        Deterministic and auditable: structured criteria are checked against
        the patient record and free-text criteria are reported as unknown, so
        nothing is auto-committed. Re-running refreshes the assessment for the
        (patient, trial) pair and clears any earlier sign-off, because that
        sign-off applied to results that have now been superseded.

        @param trial_id: Trial UUID
        @param patient_id: Candidate patient UUID
        @param facility_id: Facility UUID
        @param encounter_id: Optional encounter that prompted the screening
        @returns The screening row, or None when the trial or patient is missing
        """
        trial = (
            await self.db.execute(
                select(ClinicalTrial).where(
                    ClinicalTrial.id == trial_id,
                    ClinicalTrial.facility_id == facility_id,
                    ClinicalTrial.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not trial:
            return None

        patient = (
            await self.db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.facility_id == facility_id,
                    Patient.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not patient:
            return None

        diagnoses = (
            (
                await self.db.execute(
                    select(Diagnosis.icd10_description).where(
                        Diagnosis.patient_id == patient_id,
                        Diagnosis.facility_id == facility_id,
                        Diagnosis.clinical_status == "active",
                        Diagnosis.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )

        age = _patient_age(patient.date_of_birth, datetime.now(UTC).date())
        score, met, not_met, unknown, reasoning = _evaluate_eligibility(
            trial.inclusion_criteria or {},
            trial.exclusion_criteria or {},
            age,
            [description for description in diagnoses if description],
        )

        existing = (
            await self.db.execute(
                select(TrialAIScreening).where(
                    TrialAIScreening.trial_id == trial_id,
                    TrialAIScreening.patient_id == patient_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            screening = existing
            screening.encounter_id = encounter_id or screening.encounter_id
            screening.investigator_reviewed = False
            screening.investigator_id = None
            screening.investigator_decision = None
            screening.review_notes = None
        else:
            screening = TrialAIScreening(
                facility_id=facility_id,
                patient_id=patient_id,
                trial_id=trial_id,
                encounter_id=encounter_id,
            )
            self.db.add(screening)

        screening.eligibility_score = score
        screening.criteria_met = met
        screening.criteria_not_met = not_met
        screening.criteria_unknown = unknown
        screening.ai_reasoning = reasoning
        screening.model_version = _AI_SCREENING_MODEL

        await self.db.flush()
        await self.db.refresh(screening)

        patient_name = f"{patient.first_name} {patient.last_name}".strip() or None
        return AIScreeningResponse.model_validate(screening).model_copy(
            update={"patient_name": patient_name}
        )

    # ── Summary ──────────────────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> TrialsSummary:
        """
        Get clinical trials summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        t_base = [ClinicalTrial.facility_id == facility_id, ClinicalTrial.is_deleted == False]  # noqa: E712
        p_base = [TrialParticipant.facility_id == facility_id, TrialParticipant.is_deleted == False]  # noqa: E712
        ae_base = [TrialAdverseEvent.facility_id == facility_id, TrialAdverseEvent.is_deleted == False]  # noqa: E712

        total_trials = await self.db.execute(
            select(func.count(ClinicalTrial.id)).where(*t_base)
        )
        recruiting = await self.db.execute(
            select(func.count(ClinicalTrial.id)).where(
                *t_base, ClinicalTrial.status == "recruiting"
            )
        )
        active = await self.db.execute(
            select(func.count(ClinicalTrial.id)).where(
                *t_base, ClinicalTrial.status == "active"
            )
        )
        completed = await self.db.execute(
            select(func.count(ClinicalTrial.id)).where(
                *t_base, ClinicalTrial.status == "completed"
            )
        )

        total_participants = await self.db.execute(
            select(func.count(TrialParticipant.id)).where(*p_base)
        )
        enrolled = await self.db.execute(
            select(func.count(TrialParticipant.id)).where(
                *p_base, TrialParticipant.status.in_(["enrolled", "active"])
            )
        )
        screen_failures = await self.db.execute(
            select(func.count(TrialParticipant.id)).where(
                *p_base, TrialParticipant.status == "screen_failed"
            )
        )

        total_ae = await self.db.execute(
            select(func.count(TrialAdverseEvent.id)).where(*ae_base)
        )
        sae = await self.db.execute(
            select(func.count(TrialAdverseEvent.id)).where(
                *ae_base, TrialAdverseEvent.is_serious == True  # noqa: E712
            )
        )

        pending_screenings = await self.db.execute(
            select(func.count(TrialAIScreening.id)).where(
                TrialAIScreening.facility_id == facility_id,
                TrialAIScreening.investigator_reviewed == False,  # noqa: E712
            )
        )

        return TrialsSummary(
            total_trials=total_trials.scalar() or 0,
            recruiting_trials=recruiting.scalar() or 0,
            active_trials=active.scalar() or 0,
            completed_trials=completed.scalar() or 0,
            total_participants=total_participants.scalar() or 0,
            enrolled_participants=enrolled.scalar() or 0,
            screen_failures=screen_failures.scalar() or 0,
            total_adverse_events=total_ae.scalar() or 0,
            serious_adverse_events=sae.scalar() or 0,
            pending_ai_screenings=pending_screenings.scalar() or 0,
        )
