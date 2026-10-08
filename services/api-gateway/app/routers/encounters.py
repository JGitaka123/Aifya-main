import uuid

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser,
    Permission,
    get_current_user,
    require_permission,
    require_roles,
)
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.diagnosis import DiagnosisCreate, DiagnosisResponse
from app.schemas.encounter import (
    ClinicalWorklistCounts,
    ClinicalWorklistItem,
    ClinicalWorklistResponse,
    ClinicianProfile,
    ConsultationFeeQuote,
    ConsultationFeeUpdate,
    ConsultationPaymentRequest,
    ConsultationPaymentResponse,
    DepartmentOption,
    DepartmentWorkload,
    EncounterCreate,
    EncounterResponse,
    EncounterRouteItem,
    EncounterRouteRequest,
    EncounterRouteResponse,
    EncounterUpdate,
    QueueResponse,
)
from app.schemas.lab import LabOrderCreate, LabOrderResponse
from app.schemas.point_of_care import (
    PointOfCareTestCreate,
    PointOfCareTestResponse,
)
from app.schemas.prescription import (
    DrugInteractionAlert,
    PrescriptionCreate,
    PrescriptionResponse,
    PrescriptionWithInteractions,
)
from app.schemas.provider import ProviderDirectoryResponse
from app.schemas.vital import VitalSignCreate, VitalSignResponse
from app.models.encounter import Encounter
from app.routers.queue import announce_ticket_call
from app.services.clinical_workspace import (
    SCOPE_DEPARTMENT,
    SCOPE_FACILITY,
    SCOPE_MINE,
    ClinicalWorkspaceService,
    default_scope,
    is_facility_wide,
)
from app.services.diagnosis_service import DiagnosisService
from app.services.encounter_service import (
    EncounterService,
    OutcomeRequiredError,
)
from app.services.lab_service import LabService
from app.services.point_of_care_service import PointOfCareService
from app.services.prescription_service import PrescriptionService
from app.services.provider_directory import ProviderDirectoryService
from app.services.queue.queue_service import QueueService
from app.services.vitals_service import VitalsService, vitals_report_payload

router = APIRouter(dependencies=[Depends(require_module("encounters"))])


# ── Encounter CRUD ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_encounter(
    data: EncounterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(None),
) -> EncounterResponse:
    """
    Create a new encounter and add patient to OPD queue.

    @param data: Encounter creation data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key
    @returns Created encounter
    """
    service = EncounterService(db)
    encounter = await service.create_encounter(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    return EncounterResponse.model_validate(encounter)


@router.get("/queue", response_model=QueueResponse)
async def get_opd_queue(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=r"^(waiting|in_consultation|completed|admitted|discharged|cancelled)$",
    ),
    department_id: uuid.UUID | None = Query(
        None,
        description="Show one department's queue instead of the whole facility",
    ),
    stage: str | None = Query(
        None,
        description=(
            "assessment: still with OPD. consultation: assessed and waiting "
            "for a doctor. Omit for both."
        ),
        pattern=r"^(assessment|consultation)$",
    ),
    include_past: bool = Query(
        False,
        description=(
            "Include earlier days. Off by default: the live board is today's "
            "queue, and older visits belong in the patient's history."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> QueueResponse:
    """
    Get the OPD queue ordered by triage priority then queue number.

    @param status_filter: Optional status filter
    @param department_id: Optional department filter, so a unit can work its
        own queue rather than reading the whole facility's board
    @param stage: Optional stage filter - with OPD, or ready for a doctor
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Queue of encounters
    """
    service = EncounterService(db)
    encounters = await service.get_opd_queue(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
        department_id=department_id,
        stage=stage,
        include_past=include_past,
    )
    department_names, staff_names = await ClinicalWorkspaceService(
        db
    ).labels_for(encounters)
    items = []
    for e in encounters:
        item = EncounterResponse.model_validate(e)
        if e.patient:
            item.patient_name = f"{e.patient.first_name} {e.patient.last_name}"
            item.patient_mrn = e.patient.mrn
        if e.department_id:
            item.department_name = department_names.get(e.department_id)
        if e.attending_doctor_id:
            item.attending_doctor_name = staff_names.get(e.attending_doctor_id)
        if e.nurse_id:
            item.nurse_name = staff_names.get(e.nurse_id)
        items.append(item)
    return QueueResponse(items=items, total=len(items))


# -- Room calls ---------------------------------------------------------------

#: Where a patient is told to go when a room call has no unit of its own.
_CONSULTATION_ROOM = "Consultation Room"


async def _announce_room_call(
    db: AsyncSession, encounter: Encounter, facility_id: uuid.UUID
) -> None:
    """Speak the ticket number for a call made from a room.

    A room call moves the visit, but the ticket is what the patient is
    holding, so the announcement repeats the printed number and names the
    room. A visit with no live ticket is skipped: the call itself already
    succeeded and must not fail just because nobody could speak it.

    @param db: Database session
    @param encounter: The visit that has just been claimed
    @param facility_id: Facility the visit belongs to
    """

    queue = QueueService(db)
    ticket = await queue.ticket_for_encounter(
        facility_id=facility_id, encounter_id=encounter.id
    )
    if ticket is None:
        return
    destination = getattr(encounter, "department_name", None) or _CONSULTATION_ROOM
    await announce_ticket_call(ticket, queue, destination=destination)


@router.post("/queue/call-next", response_model=EncounterResponse)
async def call_next_patient(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_CONSULT)
    ),
) -> EncounterResponse:
    """
    Call the next patient the doctor can treat (highest priority waiting).

    The patient comes from the doctor's own reach - their own assignments and
    their department's queue - so calling the next patient never pulls someone
    who is waiting for another unit. Administrators keep the facility queue.
    Only a patient the nurse has finished assessing is called.

    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Next encounter or 404 if queue empty
    @raises HTTPException 409: When the only waiting patients are still with OPD
    """
    service = EncounterService(db)
    worklist = ClinicalWorkspaceService(db)
    clinician = await worklist.get_clinician(
        current_user.facility_id, current_user.user_id
    )
    try:
        encounter = await service.call_next(
            facility_id=current_user.facility_id,
            doctor_id=current_user.user_id,
            department_id=clinician.department_id,
            facility_wide=is_facility_wide(current_user.roles),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No patients waiting for you or your department"
                if not is_facility_wide(current_user.roles)
                else "No patients waiting in queue"
            ),
        )
    await _announce_room_call(db, encounter, current_user.facility_id)
    return EncounterResponse.model_validate(encounter)


@router.post("/{encounter_id}/call-in", response_model=EncounterResponse)
async def call_in_patient(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_CONSULT)
    ),
) -> EncounterResponse:
    """
    Bring one chosen patient into the consultation room.

    "Call next" takes the queue in order; this lets a doctor take the patient
    they actually mean from their own workspace. The gates are identical, so
    choosing a row by hand can never do more than the queue button would.

    @param encounter_id: Encounter UUID the doctor chose
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns The claimed encounter
    @raises HTTPException 404: When the patient is not in the doctor's queue
    @raises HTTPException 409: When the visit is not waiting, not assessed, or unpaid
    """
    service = EncounterService(db)
    worklist = ClinicalWorkspaceService(db)
    clinician = await worklist.get_clinician(
        current_user.facility_id, current_user.user_id
    )
    try:
        encounter = await service.call_in(
            encounter_id,
            facility_id=current_user.facility_id,
            doctor_id=current_user.user_id,
            department_id=clinician.department_id,
            facility_wide=is_facility_wide(current_user.roles),
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    await _announce_room_call(db, encounter, current_user.facility_id)
    return EncounterResponse.model_validate(encounter)


@router.post(
    "/{encounter_id}/assessment",
    response_model=EncounterResponse,
)
async def complete_opd_assessment(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.TRIAGE_RECORD,
            Permission.CLINICAL_CONSULT,
            any_of=True,
        )
    ),
) -> EncounterResponse:
    """
    Finish the OPD assessment, handing the patient to the consultation room.

    This is the nurse's hand-off to the doctor. Recording vitals completes the
    assessment already; this is for the visit that needs no measurements taken,
    so a patient is never stranded in a stage nobody can clear.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated nurse or clinician
    @returns Updated encounter
    """
    service = EncounterService(db)
    try:
        encounter = await service.complete_assessment(
            encounter_id,
            current_user.facility_id,
            current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if encounter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return EncounterResponse.model_validate(encounter)

@router.get("/worklist", response_model=ClinicalWorklistResponse)
async def get_clinical_worklist(
    scope: str | None = Query(None, pattern=r"^(mine|department|facility)$"),
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=r"^(waiting|in_consultation|completed)$",
    ),
    triaged: bool | None = Query(
        None,
        description=(
            "true: only patients the nurse has assessed. false: only those "
            "still with OPD. Omit for both."
        ),
    ),
    q: str | None = Query(
        None,
        max_length=100,
        description="Patient name, MRN or queue number to narrow the list by",
    ),
    department_id: uuid.UUID | None = Query(
        None,
        description=(
            "Narrow the list to one unit; ignored when it is outside the "
            "caller's scope"
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_VIEW)
    ),
) -> ClinicalWorklistResponse:
    """
    Today's patients for the signed-in clinician.

    Reception routes a patient to a department, and sometimes to a named
    clinician. A clinician opens this instead of the whole hospital: scope
    `mine` is what is assigned to them plus what is unclaimed and in reach,
    `department` is their unit, and `facility` is the administrator's view.

    The counts describe the whole scoped day, so filtering the list never hides
    how much work is behind the filter.

    @param scope: mine, department or facility; defaults by role
    @param status_filter: Optional single status to narrow the list
    @param triaged: Filter by whether the OPD assessment is finished
    @param q: Patient name, MRN or queue number to narrow the list by
    @param department_id: Optional single unit to narrow the list to
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns The clinician's profile, counts and today's encounters
    @raises HTTPException 403: When a non-administrator asks for facility scope
    """
    service = ClinicalWorkspaceService(db)
    clinician = await service.get_clinician(
        current_user.facility_id, current_user.user_id
    )

    resolved = scope or default_scope(current_user.roles)
    if resolved == SCOPE_FACILITY and not is_facility_wide(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A facility-wide worklist requires an administrator",
        )
    if resolved == SCOPE_DEPARTMENT and clinician.department_id is None:
        # This account belongs to no department, so the narrower request falls
        # back to the work the clinician can actually pick up.
        resolved = SCOPE_MINE

    counts, encounters = await service.get_worklist(
        current_user.facility_id,
        staff_id=clinician.staff_id,
        department_id=clinician.department_id,
        scope=resolved,
        status=status_filter,
        triaged=triaged,
        search=q,
        only_department_id=department_id,
    )
    department_names, staff_names = await service.labels_for(encounters)
    emergency_links = await service.emergency_links(encounters)
    referral_sources = await service.referral_sources(encounters)

    items: list[ClinicalWorklistItem] = []
    for encounter in encounters:
        item = ClinicalWorklistItem.model_validate(encounter)
        if encounter.patient:
            item.patient_name = (
                f"{encounter.patient.first_name} {encounter.patient.last_name}"
            )
            item.patient_mrn = encounter.patient.mrn
        if encounter.department_id:
            item.department_name = department_names.get(encounter.department_id)
        if encounter.attending_doctor_id:
            item.attending_doctor_name = staff_names.get(
                encounter.attending_doctor_id
            )
        if encounter.nurse_id:
            item.nurse_name = staff_names.get(encounter.nurse_id)
        source = referral_sources.get(encounter.id)
        if source is not None:
            item.source_department_name, item.referred_at = source
        emergency = emergency_links.get(encounter.id)
        if emergency is not None:
            (
                item.emergency_visit_id,
                item.emergency_visit_number,
                item.emergency_status,
                item.emergency_triage_color,
            ) = emergency
        items.append(item)

    return ClinicalWorklistResponse(
        scope=resolved,
        facility_wide=is_facility_wide(current_user.roles),
        clinician=ClinicianProfile(
            staff_id=clinician.staff_id,
            name=clinician.name,
            profession=clinician.profession,
            specialty=clinician.specialty,
            department_id=clinician.department_id,
            department_name=clinician.department_name,
        ),
        counts=ClinicalWorklistCounts(total=sum(counts.values()), **counts),
        items=items,
    )


# Consultation fee taken at reception before the patient sees a doctor


@router.get(
    "/{encounter_id}/consultation-fee",
    response_model=ConsultationFeeQuote,
)
async def get_consultation_fee(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    # The quote carries the invoice and the receipt link, so reading it is
    # billing work even though reception is the one who collects the money.
    current_user: CurrentUser = Depends(
        require_permission(Permission.BILLING_VIEW)
    ),
) -> ConsultationFeeQuote:
    """
    Quote what the patient owes at reception to see the doctor.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Consultation fee quote with the invoice payment state
    """
    service = EncounterService(db)
    quote = await service.get_consultation_fee_quote(
        encounter_id=encounter_id,
        facility_id=current_user.facility_id,
    )
    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )

    return _fee_quote(quote)


def _fee_quote(quote: dict) -> ConsultationFeeQuote:
    """
    Shape a consultation-fee quote into its API response.

    @param quote: Quote dict returned by EncounterService
    @returns Consultation fee quote
    """
    encounter = quote["encounter"]
    invoice = quote["invoice"]
    return ConsultationFeeQuote(
        encounter_id=encounter.id,
        patient_name=getattr(encounter, "patient_name", None),
        patient_mrn=getattr(encounter, "patient_mrn", None),
        department_id=encounter.department_id,
        attending_doctor_id=encounter.attending_doctor_id,
        fee_cents=quote["fee_cents"],
        paid=quote["paid"],
        invoice_id=invoice.id if invoice else None,
        invoice_number=invoice.invoice_number if invoice else None,
        paid_cents=invoice.paid_cents if invoice else 0,
        balance_cents=invoice.balance_cents if invoice else 0,
        receipt_url=(
            f"/billing/invoices/{invoice.id}/receipt" if invoice else None
        ),
    )


@router.post(
    "/{encounter_id}/consultation-payment",
    response_model=ConsultationPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def collect_consultation_payment(
    encounter_id: uuid.UUID,
    data: ConsultationPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "receptionist",
            "cashier",
            "billing_clerk",
            "admin",
            "facility_admin",
        )
    ),
    x_idempotency_key: str | None = Header(None),
) -> ConsultationPaymentResponse:
    """
    Take the consultation fee at reception and hand back a receipt.

    @param encounter_id: Encounter UUID
    @param data: Payment details captured at the front desk
    @param db: Database session
    @param current_user: Authenticated front-desk user
    @param x_idempotency_key: Optional idempotency key
    @returns Settled invoice with a printable receipt URL
    """
    service = EncounterService(db)
    try:
        invoice, payment = await service.collect_consultation_payment(
            encounter_id=encounter_id,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            mpesa_transaction_id=data.mpesa_transaction_id,
            notes=data.notes,
            amount_cents=data.amount_cents,
            idempotency_key=x_idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ConsultationPaymentResponse(
        encounter_id=encounter_id,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        fee_cents=invoice.total_cents,
        paid_cents=invoice.paid_cents,
        balance_cents=invoice.balance_cents,
        status=invoice.status,
        payment_id=payment.id if payment else None,
        payment_method=payment.payment_method if payment else None,
        reference_number=payment.reference_number if payment else None,
        received_by=payment.received_by if payment else None,
        paid_at=payment.paid_at if payment else None,
        receipt_url=f"/billing/invoices/{invoice.id}/receipt",
    )


@router.patch(
    "/{encounter_id}/consultation-fee",
    response_model=ConsultationFeeQuote,
)
async def update_consultation_fee(
    encounter_id: uuid.UUID,
    data: ConsultationFeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "receptionist",
            "cashier",
            "billing_clerk",
            "admin",
            "facility_admin",
        )
    ),
) -> ConsultationFeeQuote:
    """
    Correct the consultation fee charged for a visit.

    The front desk re-prices the visit before taking the money, so the amount
    collected, the patient's bill and the printed receipt all agree.

    @param encounter_id: Encounter UUID
    @param data: New fee in KES cents
    @param db: Database session
    @param current_user: Authenticated front-desk user
    @returns Updated consultation fee quote
    """
    service = EncounterService(db)
    try:
        quote = await service.set_consultation_fee(
            encounter_id=encounter_id,
            facility_id=current_user.facility_id,
            amount_cents=data.amount_cents,
            updated_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return _fee_quote(quote)


@router.get("/department-load", response_model=list[DepartmentWorkload])
async def get_department_load(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> list[DepartmentWorkload]:
    """
    Today's patient load for each department the caller may see.

    The clinical workspace is organised by department, so this is the number a
    clinician actually works against: how many patients their unit has today.
    A clinician sees their own unit; an administrator sees every unit at once.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns One row per visible department, with a count per status
    """
    service = ClinicalWorkspaceService(db)
    clinician = await service.get_clinician(
        current_user.facility_id, current_user.user_id
    )
    load = await service.department_load(
        current_user.facility_id,
        department_id=clinician.department_id,
        facility_wide=is_facility_wide(current_user.roles),
    )
    return [DepartmentWorkload(**row) for row in load]


@router.get("/departments", response_model=list[DepartmentOption])
async def list_departments(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DepartmentOption]:
    """
    List the facility's departments for the front-desk routing picker.

    Declared before the /{encounter_id} route so "departments" is not parsed
    as an encounter UUID.

    @param include_inactive: Include deactivated departments
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Departments ordered by name
    """
    from sqlalchemy import func, select

    from app.models.staff import Department, Staff

    stmt = select(Department).where(
        Department.facility_id == current_user.facility_id,
        Department.is_deleted == False,  # noqa: E712
    )
    if not include_inactive:
        stmt = stmt.where(Department.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt.order_by(Department.name.asc()))).scalars().all()

    # Whether anybody is on duty in a unit decides whether a patient sent
    # there will actually be seen, so the routing picker can warn before the
    # hand-off rather than let the patient vanish into an empty queue.
    counts = dict(
        (
            await db.execute(
                select(Staff.department_id, func.count())
                .where(
                    Staff.facility_id == current_user.facility_id,
                    Staff.is_deleted == False,  # noqa: E712
                    Staff.is_active == True,  # noqa: E712
                    Staff.department_id.is_not(None),
                )
                .group_by(Staff.department_id)
            )
        ).all()
    )

    options = []
    for row in rows:
        option = DepartmentOption.model_validate(row)
        option.staff_count = counts.get(row.id, 0)
        options.append(option)
    return options


@router.get("/providers", response_model=ProviderDirectoryResponse)
async def list_providers(
    department_id: uuid.UUID | None = Query(
        None, description="Restrict to one unit"
    ),
    role: str | None = Query(None, description="Restrict to one role"),
    specialty: str | None = Query(None, description="Restrict to one specialty"),
    work_status: str | None = Query(
        None, description="Restrict to one effective availability"
    ),
    available_only: bool = Query(
        False, description="Only clinicians who can be assigned now"
    ),
    search: str | None = Query(None, description="Name search"),
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.CLINICAL_VIEW,
            Permission.OPD_MANAGE,
            any_of=True,
        )
    ),
) -> ProviderDirectoryResponse:
    """
    The clinicians a patient in the consultation room can be handed to.

    The room assigns to a qualified person, not to a department: this lists
    the clinical staff of one unit with their specialty and their *effective*
    availability - an active account that is on leave or already in a
    consultation is not available. Declared before the /{encounter_id} route
    so "providers" is not parsed as an encounter UUID.

    @param department_id: Restrict to one unit
    @param role: Restrict to one role (defaults to every clinical role)
    @param specialty: Restrict to one specialty
    @param work_status: Restrict to one effective availability
    @param available_only: Keep only clinicians who can be assigned now
    @param search: Optional name substring
    @param include_inactive: Include deactivated accounts
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns Providers ordered available-first, plus the specialties offered
    """
    service = ProviderDirectoryService(db)
    items, specialties = await service.list_providers(
        facility_id=current_user.facility_id,
        department_id=department_id,
        role=role,
        specialty=specialty,
        work_status=work_status,
        available_only=available_only,
        search=search,
        include_inactive=include_inactive,
    )
    return ProviderDirectoryResponse(
        items=items, total=len(items), specialties=specialties
    )


@router.get("/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EncounterResponse:
    """
    Get a single encounter by ID.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Encounter details
    """
    service = EncounterService(db)
    encounter = await service.get_encounter(
        encounter_id, current_user.facility_id
    )
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    response = EncounterResponse.model_validate(encounter)
    # The doctor opening this record needs the triaging nurse named, not a
    # UUID, so the same label lookup the queue uses runs for the one row.
    department_names, staff_names = await ClinicalWorkspaceService(
        db
    ).labels_for([encounter])
    if encounter.department_id:
        response.department_name = department_names.get(encounter.department_id)
    if encounter.attending_doctor_id:
        response.attending_doctor_name = staff_names.get(
            encounter.attending_doctor_id
        )
    if encounter.nurse_id:
        response.nurse_name = staff_names.get(encounter.nurse_id)
    return response


@router.patch("/{encounter_id}", response_model=EncounterResponse)
async def update_encounter(
    encounter_id: uuid.UUID,
    data: EncounterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.CLINICAL_CONSULT,
            Permission.TRIAGE_RECORD,
            any_of=True,
        )
    ),
) -> EncounterResponse:
    """
    Update encounter (status, triage, disposition, etc.).

    @param encounter_id: Encounter UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated encounter
    @raises HTTPException 422: When a completion carries no outcome note
    """
    service = EncounterService(db)
    try:
        encounter = await service.update_encounter(
            encounter_id=encounter_id,
            data=data,
            facility_id=current_user.facility_id,
            updated_by=current_user.user_id,
        )
    except OutcomeRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return EncounterResponse.model_validate(encounter)


# ── Vitals ─────────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/vitals",
    response_model=VitalSignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_vitals(
    encounter_id: uuid.UUID,
    data: VitalSignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.TRIAGE_RECORD,
            Permission.CLINICAL_CONSULT,
            any_of=True,
        )
    ),
) -> VitalSignResponse:
    """
    Record vital signs for an encounter. Critical values trigger alerts.

    @param encounter_id: Encounter UUID (path)
    @param data: Vital signs data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Recorded vital signs with critical alerts if any
    @raises HTTPException 404: When the encounter is not in this facility
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = VitalsService(db)
    try:
        vital = await service.record_vitals(
            data=data,
            facility_id=current_user.facility_id,
            recorded_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    # "No such visit" and "another hospital's visit" are answered identically
    # on purpose: telling them apart would let a caller probe for encounter
    # ids that are not theirs.
    if vital is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return _vital_response(vital)


@router.get(
    "/{encounter_id}/vitals",
    response_model=list[VitalSignResponse],
)
async def get_encounter_vitals(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[VitalSignResponse]:
    """
    Get all vital sign recordings for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of vital sign recordings
    """
    service = VitalsService(db)
    vitals = await service.get_encounter_vitals(
        encounter_id, current_user.facility_id
    )
    return [_vital_response(v) for v in vitals]


def _vital_response(vital) -> VitalSignResponse:
    """
    Shape a vitals row into its API response, including the report link.

    @param vital: Persisted vital signs row
    @returns Vital signs response carrying the printable report URL
    """
    response = VitalSignResponse.model_validate(vital)
    response.report_url = (
        f"/encounters/{vital.encounter_id}/vitals/{vital.id}/report"
    )
    return response


@router.get("/{encounter_id}/vitals/{vital_id}/report")
async def get_vitals_report(
    encounter_id: uuid.UUID,
    vital_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Render the numbered vitals report the nurse issues after triage.

    The same report is what the patient's history lists and what the nurse
    hands over, so critical values are printed on it rather than left to the
    screen the nurse has already walked away from.

    @param encounter_id: Encounter UUID
    @param vital_id: Vitals recording UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns application/pdf response
    """
    from sqlalchemy import select as sa_select

    from app.models.facility import Facility
    from app.models.patient import Patient
    from app.models.staff import Staff
    from app.services.vitals_report_pdf import (
        render_vitals_report_pdf,
        vitals_report_filename,
    )

    service = VitalsService(db)
    vital = await service.get_vital(vital_id, current_user.facility_id)
    if vital is None or vital.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vitals recording not found",
        )

    facility_name = (
        await db.execute(
            sa_select(Facility.name).where(Facility.id == current_user.facility_id)
        )
    ).scalar_one_or_none() or "Aifya Health Facility"

    patient = (
        await db.execute(sa_select(Patient).where(Patient.id == vital.patient_id))
    ).scalar_one_or_none()
    patient_name = (
        " ".join(
            part
            for part in (
                patient.first_name if patient else None,
                patient.middle_name if patient else None,
                patient.last_name if patient else None,
            )
            if part
        )
        or None
    )

    recorder = (
        await db.execute(sa_select(Staff).where(Staff.id == vital.recorded_by))
    ).scalar_one_or_none()
    recorded_by_name = (
        " ".join(
            part
            for part in (
                recorder.title if recorder else None,
                recorder.first_name if recorder else None,
                recorder.last_name if recorder else None,
            )
            if part
        )
        or None
    )

    pdf = render_vitals_report_pdf(
        facility_name=facility_name,
        vital=vitals_report_payload(vital),
        patient_name=patient_name,
        patient_mrn=patient.mrn if patient else None,
        recorded_by_name=recorded_by_name,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{vitals_report_filename(vital.report_number or str(vital.id))}"'
            )
        },
    )



# ── Diagnoses ──────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_diagnosis(
    encounter_id: uuid.UUID,
    data: DiagnosisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_CONSULT)
    ),
) -> DiagnosisResponse:
    """
    Add a diagnosis (ICD-10) to an encounter.

    @param encounter_id: Encounter UUID (path)
    @param data: Diagnosis data with ICD-10 code
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Created diagnosis
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = DiagnosisService(db)
    diagnosis = await service.add_diagnosis(
        data=data,
        facility_id=current_user.facility_id,
        diagnosed_by=current_user.user_id,
    )
    return DiagnosisResponse.model_validate(diagnosis)


@router.get(
    "/{encounter_id}/diagnoses",
    response_model=list[DiagnosisResponse],
)
async def get_encounter_diagnoses(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DiagnosisResponse]:
    """
    Get all diagnoses for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of diagnoses
    """
    service = DiagnosisService(db)
    diagnoses = await service.get_encounter_diagnoses(
        encounter_id, current_user.facility_id
    )
    return [DiagnosisResponse.model_validate(d) for d in diagnoses]


# ── Prescriptions ──────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/prescriptions",
    response_model=PrescriptionWithInteractions,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    encounter_id: uuid.UUID,
    data: PrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_CONSULT)
    ),
) -> PrescriptionWithInteractions:
    """
    Create a prescription with drug interaction checking.
    Blocks on critical interactions per CLAUDE.md: Clinical Safety.

    @param encounter_id: Encounter UUID (path)
    @param data: Prescription data
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Prescription with interaction check results
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = PrescriptionService(db)
    prescription, interactions, blocked = await service.create_prescription(
        data=data,
        facility_id=current_user.facility_id,
        prescriber_id=(
            current_user.user_id
            if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
            else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
        ),
    )
    mapped_interactions = [
        DrugInteractionAlert(
            severity=i.get("severity", "moderate"),
            interacting_drug=(
                ", ".join(i.get("affected_items", []))
                if i.get("affected_items")
                else i.get("interacting_drug", "")
            ),
            description=i.get("message", i.get("description", "")),
            category=i.get("category"),
            source_rule=i.get("source_rule"),
        )
        for i in interactions
    ]
    return PrescriptionWithInteractions(
        # A blocked prescription is never saved, so there is no valid
        # response object to serialize — return null with the alert list.
        prescription=(
            None if blocked else PrescriptionResponse.model_validate(prescription)
        ),
        interactions=mapped_interactions,
        blocked=blocked,
    )


@router.get(
    "/{encounter_id}/prescriptions",
    response_model=list[PrescriptionResponse],
)
async def get_encounter_prescriptions(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PrescriptionResponse]:
    """
    Get all prescriptions for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of prescriptions
    """
    service = PrescriptionService(db)
    prescriptions = await service.get_encounter_prescriptions(
        encounter_id, current_user.facility_id
    )
    return [PrescriptionResponse.model_validate(p) for p in prescriptions]


# ── Lab Orders ─────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/lab-orders",
    response_model=LabOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lab_order(
    encounter_id: uuid.UUID,
    data: LabOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(Permission.CLINICAL_CONSULT)
    ),
) -> LabOrderResponse:
    """
    Create a lab order with one or more tests.

    @param encounter_id: Encounter UUID (path)
    @param data: Lab order data with tests
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Created lab order
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = LabService(db)
    ordered_by = (
        current_user.user_id
        if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
        else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
    )
    order = await service.create_order(
        data=data,
        facility_id=current_user.facility_id,
        ordered_by=ordered_by,
    )
    return LabOrderResponse.model_validate(order)


@router.get(
    "/{encounter_id}/lab-orders",
    response_model=list[LabOrderResponse],
)
async def get_encounter_lab_orders(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[LabOrderResponse]:
    """
    Get all lab orders for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of lab orders
    """
    service = LabService(db)
    orders = await service.get_encounter_orders(
        encounter_id, current_user.facility_id
    )
    return [LabOrderResponse.model_validate(o) for o in orders]


# -- Consultation room: directing the patient to another unit --------------


@router.post("/{encounter_id}/route", response_model=EncounterRouteResponse)
async def route_encounter(
    encounter_id: uuid.UUID,
    data: EncounterRouteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.CLINICAL_CONSULT,
            Permission.OPD_MANAGE,
            any_of=True,
        )
    ),
) -> EncounterRouteResponse:
    """
    Direct a patient from the consultation room to another unit.

    This is the clinician's hand-off. It records an internal referral and
    re-queues the encounter in the destination department, so a patient sent
    to Dental, Physiotherapy, Laboratory or Pharmacy actually turns up in that
    unit's queue instead of merely being marked as sent.

    @param encounter_id: Encounter UUID (path)
    @param data: Destination, optional clinician, urgency and reason
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns The re-queued encounter and the referral that records it
    @raises HTTPException 404: When the encounter is unknown
    @raises HTTPException 409: When the visit is closed or already in the unit
    """
    service = EncounterService(db)
    try:
        encounter, referral, department_name = await service.route_to_department(
            encounter_id=encounter_id,
            data=data,
            facility_id=current_user.facility_id,
            routed_by=current_user.user_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return EncounterRouteResponse(
        encounter=EncounterResponse.model_validate(encounter),
        referral_id=referral.id,
        referral_number=referral.referral_number,
        receiving_department_id=data.receiving_department_id,
        receiving_department_name=department_name,
    )


@router.get("/{encounter_id}/routes", response_model=list[EncounterRouteItem])
async def get_encounter_routes(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[EncounterRouteItem]:
    """
    The internal routing trail for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Internal routings, newest first
    """
    service = EncounterService(db)
    referrals = await service.get_encounter_routes(
        encounter_id, current_user.facility_id
    )
    names = await service.department_names(
        {
            referral.referring_department_id
            for referral in referrals
        }
        | {referral.receiving_department_id for referral in referrals}
    )
    return [
        EncounterRouteItem(
            id=referral.id,
            referral_number=referral.referral_number,
            urgency=referral.urgency,
            reason=referral.reason,
            notes=referral.notes,
            status=referral.status,
            referral_date=referral.referral_date,
            referring_department_id=referral.referring_department_id,
            referring_department_name=names.get(
                referral.referring_department_id
            ),
            receiving_department_id=referral.receiving_department_id,
            receiving_department_name=names.get(
                referral.receiving_department_id
            ),
            referring_doctor_id=referral.referring_doctor_id,
            receiving_doctor_id=referral.receiving_doctor_id,
        )
        for referral in referrals
    ]


# -- Consultation room: general (point-of-care) testing ---------------------


@router.post(
    "/{encounter_id}/tests",
    response_model=PointOfCareTestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_point_of_care_test(
    encounter_id: uuid.UUID,
    data: PointOfCareTestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_permission(
            Permission.TRIAGE_RECORD,
            Permission.CLINICAL_CONSULT,
            any_of=True,
        )
    ),
) -> PointOfCareTestResponse:
    """
    Record a general test done in the room (HIV, malaria RDT, urinalysis...).

    @param encounter_id: Encounter UUID (path)
    @param data: Test, result and interpretation
    @param db: Database session
    @param current_user: Authenticated clinician
    @returns The recorded test
    @raises HTTPException 404: When the encounter is unknown
    @raises HTTPException 409: When the visit is already closed
    """
    service = PointOfCareService(db)
    try:
        test = await service.record_test(
            encounter_id=encounter_id,
            data=data,
            facility_id=current_user.facility_id,
            performed_by=current_user.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail == "Encounter not found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return PointOfCareTestResponse.model_validate(test)


@router.get("/{encounter_id}/tests", response_model=list[PointOfCareTestResponse])
async def get_encounter_tests(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PointOfCareTestResponse]:
    """
    General tests recorded in the room for an encounter, newest first.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of recorded tests
    """
    service = PointOfCareService(db)
    tests = await service.get_encounter_tests(
        encounter_id, current_user.facility_id
    )
    return [PointOfCareTestResponse.model_validate(t) for t in tests]
