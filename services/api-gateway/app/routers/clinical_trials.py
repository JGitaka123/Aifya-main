import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.clinical_trial import (
    AdverseEventCreate,
    AdverseEventListResponse,
    AdverseEventResponse,
    AIScreeningCreate,
    AIScreeningListResponse,
    AIScreeningResponse,
    AIScreeningReview,
    ParticipantEnroll,
    ParticipantListResponse,
    ParticipantResponse,
    ParticipantStatusUpdate,
    ParticipantVisitCreate,
    ParticipantVisitResponse,
    ParticipantVisitUpdate,
    SAEReportSubmit,
    TrialCreate,
    TrialListResponse,
    TrialResponse,
    TrialsSummary,
    TrialStatusUpdate,
    TrialUpdate,
    VisitScheduleCreate,
    VisitScheduleResponse,
)
from app.services.clinical_trial_service import ClinicalTrialService

router = APIRouter(dependencies=[Depends(require_module("clinical_trials"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=TrialsSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TrialsSummary:
    """
    Get clinical trials summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Clinical trials summary
    """
    service = ClinicalTrialService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Trials CRUD ──────────────────────────────────────────────────────────────


@router.get("", response_model=TrialListResponse)
async def list_trials(
    trial_status: str | None = Query(None, alias="status", description="Filter by trial status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TrialListResponse:
    """
    Get clinical trials.

    @param trial_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Trial list
    """
    service = ClinicalTrialService(db)
    items = await service.get_trials(facility_id=current_user.facility_id, status=trial_status)
    return TrialListResponse(items=items, total=len(items))


@router.post("", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
async def create_trial(
    data: TrialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator")
    ),
) -> TrialResponse:
    """
    Create a clinical trial.

    @param data: Trial data
    @param db: Database session
    @param current_user: Authenticated research staff
    @returns Created trial
    """
    service = ClinicalTrialService(db)
    trial = await service.create_trial(
        data=data, facility_id=current_user.facility_id, created_by=current_user.user_id
    )
    return TrialResponse.model_validate(trial)


@router.get("/{trial_id}", response_model=TrialResponse)
async def get_trial(
    trial_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TrialResponse:
    """
    Get a single clinical trial.

    @param trial_id: Trial UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Trial details
    """
    service = ClinicalTrialService(db)
    trial = await service.get_trial(trial_id, current_user.facility_id)
    if not trial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")
    return TrialResponse.model_validate(trial)


@router.patch("/{trial_id}", response_model=TrialResponse)
async def update_trial(
    trial_id: uuid.UUID,
    data: TrialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator")
    ),
) -> TrialResponse:
    """
    Update a clinical trial.

    @param trial_id: Trial UUID
    @param data: Update data
    @param db: Database session
    @param current_user: Authenticated research staff
    @returns Updated trial
    """
    service = ClinicalTrialService(db)
    trial = await service.update_trial(
        trial_id=trial_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not trial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")
    return TrialResponse.model_validate(trial)


@router.post("/{trial_id}/status", response_model=TrialResponse)
async def update_trial_status(
    trial_id: uuid.UUID,
    data: TrialStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator")
    ),
) -> TrialResponse:
    """
    Update trial status.

    @param trial_id: Trial UUID
    @param data: Status update
    @param db: Database session
    @param current_user: Authenticated PI or admin
    @returns Updated trial
    """
    service = ClinicalTrialService(db)
    trial = await service.update_trial_status(
        trial_id=trial_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not trial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")
    return TrialResponse.model_validate(trial)


# ── Participants ─────────────────────────────────────────────────────────────


@router.get("/{trial_id}/participants", response_model=ParticipantListResponse)
async def list_participants(
    trial_id: uuid.UUID,
    participant_status: str | None = Query(None, alias="status", description="Filter by participant status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ParticipantListResponse:
    """
    Get participants for a trial.

    @param trial_id: Trial UUID
    @param participant_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Participant list
    """
    service = ClinicalTrialService(db)
    items = await service.get_participants(
        trial_id=trial_id, facility_id=current_user.facility_id, status=participant_status
    )
    return ParticipantListResponse(items=items, total=len(items))


@router.post(
    "/{trial_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_participant(
    trial_id: uuid.UUID,
    data: ParticipantEnroll,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor")
    ),
) -> ParticipantResponse:
    """
    Enroll a patient as a trial participant.

    @param trial_id: Trial UUID
    @param data: Enrollment data
    @param db: Database session
    @param current_user: Authenticated research staff
    @returns Created participant
    """
    service = ClinicalTrialService(db)
    participant = await service.enroll_participant(
        trial_id=trial_id, data=data, facility_id=current_user.facility_id, created_by=current_user.user_id
    )
    return ParticipantResponse.model_validate(participant)


@router.get("/{trial_id}/participants/{participant_id}", response_model=ParticipantResponse)
async def get_participant(
    trial_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ParticipantResponse:
    """
    Get a single participant.

    @param trial_id: Trial UUID
    @param participant_id: Participant UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Participant details
    """
    service = ClinicalTrialService(db)
    participant = await service.get_participant(participant_id, current_user.facility_id)
    if not participant or participant.trial_id != trial_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return ParticipantResponse.model_validate(participant)


@router.patch(
    "/{trial_id}/participants/{participant_id}/status",
    response_model=ParticipantResponse,
)
async def update_participant_status(
    trial_id: uuid.UUID,
    participant_id: uuid.UUID,
    data: ParticipantStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor")
    ),
) -> ParticipantResponse:
    """
    Update participant status.

    @param trial_id: Trial UUID
    @param participant_id: Participant UUID
    @param data: Status update
    @param db: Database session
    @param current_user: Authenticated research staff
    @returns Updated participant
    """
    service = ClinicalTrialService(db)
    participant = await service.update_participant_status(
        participant_id=participant_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not participant or participant.trial_id != trial_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return ParticipantResponse.model_validate(participant)


# ── Visit Schedule ───────────────────────────────────────────────────────────


@router.get("/{trial_id}/visit-schedule", response_model=list[VisitScheduleResponse])
async def get_visit_schedule(
    trial_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[VisitScheduleResponse]:
    """
    Get visit schedule for a trial.

    @param trial_id: Trial UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Visit schedule entries
    """
    service = ClinicalTrialService(db)
    items = await service.get_visit_schedule(trial_id)
    return [VisitScheduleResponse.model_validate(s) for s in items]


@router.post(
    "/{trial_id}/visit-schedule",
    response_model=VisitScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_visit_schedule(
    trial_id: uuid.UUID,
    data: VisitScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator")
    ),
) -> VisitScheduleResponse:
    """
    Create a visit schedule entry.

    @param trial_id: Trial UUID
    @param data: Visit schedule data
    @param db: Database session
    @param current_user: Authenticated research staff
    @returns Created schedule entry
    """
    service = ClinicalTrialService(db)
    schedule = await service.create_visit_schedule(trial_id=trial_id, data=data)
    return VisitScheduleResponse.model_validate(schedule)


# ── Participant Visits ───────────────────────────────────────────────────────


@router.get(
    "/{trial_id}/participants/{participant_id}/visits",
    response_model=list[ParticipantVisitResponse],
)
async def get_participant_visits(
    trial_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ParticipantVisitResponse]:
    """
    Get visits for a participant.

    @param trial_id: Trial UUID
    @param participant_id: Participant UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Participant visit records
    """
    service = ClinicalTrialService(db)
    items = await service.get_participant_visits(participant_id)
    return [ParticipantVisitResponse.model_validate(v) for v in items]


@router.post(
    "/{trial_id}/participants/{participant_id}/visits",
    response_model=ParticipantVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_participant_visit(
    trial_id: uuid.UUID,
    participant_id: uuid.UUID,
    data: ParticipantVisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor", "nurse")
    ),
) -> ParticipantVisitResponse:
    """
    Record a participant visit.

    @param trial_id: Trial UUID
    @param participant_id: Participant UUID
    @param data: Visit data
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Created visit record
    """
    service = ClinicalTrialService(db)
    visit = await service.create_participant_visit(
        participant_id=participant_id, data=data, facility_id=current_user.facility_id, created_by=current_user.user_id
    )
    return ParticipantVisitResponse.model_validate(visit)


@router.patch(
    "/{trial_id}/participants/{participant_id}/visits/{visit_id}",
    response_model=ParticipantVisitResponse,
)
async def update_participant_visit(
    trial_id: uuid.UUID,
    participant_id: uuid.UUID,
    visit_id: uuid.UUID,
    data: ParticipantVisitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor", "nurse")
    ),
) -> ParticipantVisitResponse:
    """
    Update a participant visit.

    @param trial_id: Trial UUID
    @param participant_id: Participant UUID
    @param visit_id: Visit UUID
    @param data: Update data
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Updated visit record
    """
    service = ClinicalTrialService(db)
    visit = await service.update_participant_visit(
        visit_id=visit_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    return ParticipantVisitResponse.model_validate(visit)


# ── Adverse Events ───────────────────────────────────────────────────────────


@router.get("/{trial_id}/adverse-events", response_model=AdverseEventListResponse)
async def list_adverse_events(
    trial_id: uuid.UUID,
    serious_only: bool = Query(False, description="Filter to SAEs only"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdverseEventListResponse:
    """
    Get adverse events for a trial.

    @param trial_id: Trial UUID
    @param serious_only: Filter to SAEs only
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Adverse event list
    """
    service = ClinicalTrialService(db)
    items = await service.get_adverse_events(
        trial_id=trial_id, facility_id=current_user.facility_id, serious_only=serious_only
    )
    return AdverseEventListResponse(items=items, total=len(items))


@router.post(
    "/{trial_id}/adverse-events",
    response_model=AdverseEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_adverse_event(
    trial_id: uuid.UUID,
    data: AdverseEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor", "nurse")
    ),
) -> AdverseEventResponse:
    """
    Report an adverse event. SAEs trigger 24-hour reporting window.

    @param trial_id: Trial UUID
    @param data: AE data
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Created adverse event
    """
    service = ClinicalTrialService(db)
    ae = await service.report_adverse_event(
        trial_id=trial_id, data=data, facility_id=current_user.facility_id, reported_by=current_user.user_id
    )
    return AdverseEventResponse.model_validate(ae)


@router.get("/{trial_id}/adverse-events/{ae_id}", response_model=AdverseEventResponse)
async def get_adverse_event(
    trial_id: uuid.UUID,
    ae_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdverseEventResponse:
    """
    Get a single adverse event.

    @param trial_id: Trial UUID
    @param ae_id: AE UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Adverse event details
    """
    service = ClinicalTrialService(db)
    ae = await service.get_adverse_event(ae_id, current_user.facility_id)
    if not ae or ae.trial_id != trial_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adverse event not found")
    return AdverseEventResponse.model_validate(ae)


@router.post("/{trial_id}/adverse-events/{ae_id}/sae-report", response_model=AdverseEventResponse)
async def submit_sae_report(
    trial_id: uuid.UUID,
    ae_id: uuid.UUID,
    data: SAEReportSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator")
    ),
) -> AdverseEventResponse:
    """
    Submit SAE report to sponsor/IRB. MUST be within 24 hours.

    @param trial_id: Trial UUID
    @param ae_id: AE UUID
    @param data: SAE report data
    @param db: Database session
    @param current_user: Authenticated PI or admin
    @returns Updated adverse event
    """
    service = ClinicalTrialService(db)
    ae = await service.submit_sae_report(
        ae_id=ae_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not ae:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SAE not found or event is not marked as serious",
        )
    return AdverseEventResponse.model_validate(ae)


# ── AI Screening ─────────────────────────────────────────────────────────────


@router.get("/{trial_id}/ai-screening", response_model=AIScreeningListResponse)
async def list_ai_screenings(
    trial_id: uuid.UUID,
    unreviewed_only: bool = Query(False, description="Filter to unreviewed only"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AIScreeningListResponse:
    """
    Get AI screening results for a trial.

    @param trial_id: Trial UUID
    @param unreviewed_only: Filter to unreviewed only
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AI screening results
    """
    service = ClinicalTrialService(db)
    items = await service.get_ai_screenings(
        trial_id=trial_id, facility_id=current_user.facility_id, unreviewed_only=unreviewed_only
    )
    return AIScreeningListResponse(items=items, total=len(items))


@router.post(
    "/{trial_id}/ai-screening",
    response_model=AIScreeningResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_ai_screening(
    trial_id: uuid.UUID,
    data: AIScreeningCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "admin",
            "facility_admin",
            "principal_investigator",
            "research_coordinator",
            "doctor",
        )
    ),
) -> AIScreeningResponse:
    """
    Screen a patient against a trial's eligibility criteria.

    Builds the decision-support assessment the investigator then reviews. The
    result is never auto-committed: a clinician has to sign it off.

    @param trial_id: Trial UUID
    @param data: Screening request with the candidate patient
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns The created or refreshed screening result
    """
    service = ClinicalTrialService(db)
    screening = await service.run_ai_screening(
        trial_id=trial_id,
        patient_id=data.patient_id,
        facility_id=current_user.facility_id,
        encounter_id=data.encounter_id,
    )
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trial or patient not found",
        )
    return screening


@router.post(
    "/{trial_id}/ai-screening/{screening_id}/review",
    response_model=AIScreeningResponse,
)
async def review_ai_screening(
    trial_id: uuid.UUID,
    screening_id: uuid.UUID,
    data: AIScreeningReview,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "principal_investigator", "research_coordinator", "doctor")
    ),
) -> AIScreeningResponse:
    """
    Investigator reviews an AI screening result.
    AI NEVER auto-commits — always requires clinician sign-off.

    @param trial_id: Trial UUID
    @param screening_id: Screening UUID
    @param data: Review data
    @param db: Database session
    @param current_user: Authenticated investigator
    @returns Updated screening result
    """
    service = ClinicalTrialService(db)
    screening = await service.review_ai_screening(
        screening_id=screening_id, data=data, facility_id=current_user.facility_id, investigator_id=current_user.user_id
    )
    if not screening or screening.trial_id != trial_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening result not found")
    return AIScreeningResponse.model_validate(screening)
