import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
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
    EncounterCreate,
    EncounterResponse,
    EncounterUpdate,
    QueueResponse,
)
from app.schemas.lab import LabOrderCreate, LabOrderResponse
from app.schemas.prescription import (
    DrugInteractionAlert,
    PrescriptionCreate,
    PrescriptionResponse,
    PrescriptionWithInteractions,
)
from app.schemas.vital import VitalSignCreate, VitalSignResponse
from app.services.clinical_workspace import (
    SCOPE_DEPARTMENT,
    SCOPE_FACILITY,
    SCOPE_MINE,
    ClinicalWorkspaceService,
    default_scope,
    is_facility_wide,
)
from app.services.diagnosis_service import DiagnosisService
from app.services.encounter_service import EncounterService
from app.services.lab_service import LabService
from app.services.prescription_service import PrescriptionService
from app.services.vitals_service import VitalsService

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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> QueueResponse:
    """
    Get the OPD queue ordered by triage priority then queue number.

    @param status_filter: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Queue of encounters
    """
    service = EncounterService(db)
    encounters = await service.get_opd_queue(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
    )
    items = []
    for e in encounters:
        item = EncounterResponse.model_validate(e)
        if e.patient:
            item.patient_name = f"{e.patient.first_name} {e.patient.last_name}"
            item.patient_mrn = e.patient.mrn
        items.append(item)
    return QueueResponse(items=items, total=len(items))


@router.post("/queue/call-next", response_model=EncounterResponse)
async def call_next_patient(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> EncounterResponse:
    """
    Call the next patient in the OPD queue (highest priority waiting).

    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Next encounter or 404 if queue empty
    """
    service = EncounterService(db)
    try:
        encounter = await service.call_next(
            facility_id=current_user.facility_id,
            doctor_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patients waiting in queue",
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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
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
    )
    department_names, staff_names = await service.labels_for(encounters)

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
    current_user: CurrentUser = Depends(get_current_user),
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
    from sqlalchemy import select

    from app.models.staff import Department

    stmt = select(Department).where(
        Department.facility_id == current_user.facility_id,
        Department.is_deleted == False,  # noqa: E712
    )
    if not include_inactive:
        stmt = stmt.where(Department.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt.order_by(Department.name.asc()))).scalars().all()
    return [DepartmentOption.model_validate(row) for row in rows]


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
    return EncounterResponse.model_validate(encounter)


@router.patch("/{encounter_id}", response_model=EncounterResponse)
async def update_encounter(
    encounter_id: uuid.UUID,
    data: EncounterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EncounterResponse:
    """
    Update encounter (status, triage, disposition, etc.).

    @param encounter_id: Encounter UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated encounter
    """
    service = EncounterService(db)
    encounter = await service.update_encounter(
        encounter_id=encounter_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
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
    current_user: CurrentUser = Depends(get_current_user),
) -> VitalSignResponse:
    """
    Record vital signs for an encounter. Critical values trigger alerts.

    @param encounter_id: Encounter UUID (path)
    @param data: Vital signs data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Recorded vital signs with critical alerts if any
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = VitalsService(db)
    vital = await service.record_vitals(
        data=data,
        facility_id=current_user.facility_id,
        recorded_by=current_user.user_id,
    )
    return VitalSignResponse.model_validate(vital)


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
    return [VitalSignResponse.model_validate(v) for v in vitals]


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
        require_roles("doctor", "admin", "facility_admin")
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
        require_roles("doctor", "admin", "facility_admin")
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
        require_roles("doctor", "admin", "facility_admin")
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
