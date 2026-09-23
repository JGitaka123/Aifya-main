"""
FHIR R4 Interoperability Gateway router.
Provides read-only FHIR-compliant endpoints for health data exchange.
Responses use application/fhir+json content type per FHIR specification.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user, require_patient_read
from app.auth.license_check import require_module
from app.database import get_db
from app.services.fhir.models import (
    FHIRIssue,
    FHIRIssueCode,
    FHIRIssueSeverity,
    FHIROperationOutcome,
)
from app.services.fhir.service import FHIRService

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("fhir"))])

FHIR_CONTENT_TYPE = "application/fhir+json"


def _fhir_response(data: dict, status_code: int = 200) -> JSONResponse:
    """
    Wrap a FHIR resource dict in a JSONResponse with FHIR content type.

    @param data: FHIR resource dict
    @param status_code: HTTP status code
    @returns JSONResponse with application/fhir+json
    """
    return JSONResponse(
        content=data,
        status_code=status_code,
        media_type=FHIR_CONTENT_TYPE,
    )


def _not_found(resource_type: str, resource_id: str) -> JSONResponse:
    """
    Return a FHIR OperationOutcome for a not-found resource.

    @param resource_type: FHIR resource type
    @param resource_id: Resource ID that was not found
    @returns JSONResponse with 404 and OperationOutcome
    """
    outcome = FHIROperationOutcome(
        issue=[
            FHIRIssue(
                severity=FHIRIssueSeverity.ERROR,
                code=FHIRIssueCode.NOT_FOUND,
                diagnostics=f"{resource_type}/{resource_id} not found",
            )
        ]
    )
    return _fhir_response(outcome.model_dump(exclude_none=True), 404)


# ── Capability Statement ──────────────────────────────────────────────────────


@router.get("/metadata")
async def capability_statement(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """
    FHIR CapabilityStatement — describes server capabilities.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns CapabilityStatement resource
    """
    service = FHIRService(db)
    cap = service.get_capability_statement()
    return _fhir_response(cap.model_dump(exclude_none=True))


# ── Patient ───────────────────────────────────────────────────────────────────


@router.get("/Patient/{patient_id}")
async def read_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Patient read — retrieve a single patient by ID.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Patient resource or OperationOutcome
    """
    service = FHIRService(db)
    patient = await service.get_patient(patient_id, current_user.facility_id)
    if not patient:
        return _not_found("Patient", str(patient_id))
    return _fhir_response(patient.model_dump(exclude_none=True))


@router.get("/Patient")
async def search_patients(
    name: str | None = Query(None),
    identifier: str | None = Query(None),
    birthdate: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Patient search — search patients by name, identifier, or birthdate.

    @param name: Name search string
    @param identifier: MRN or national ID
    @param birthdate: Date of birth (YYYY-MM-DD)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Bundle with matching patients
    """
    service = FHIRService(db)
    bundle = await service.search_patients(
        facility_id=current_user.facility_id,
        name=name,
        identifier=identifier,
        birthdate=birthdate,
    )
    return _fhir_response(bundle.model_dump(exclude_none=True))


# ── Encounter ─────────────────────────────────────────────────────────────────


@router.get("/Encounter/{encounter_id}")
async def read_encounter(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Encounter read — retrieve a single encounter by ID.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Encounter resource or OperationOutcome
    """
    service = FHIRService(db)
    encounter = await service.get_encounter(encounter_id, current_user.facility_id)
    if not encounter:
        return _not_found("Encounter", str(encounter_id))
    return _fhir_response(encounter.model_dump(exclude_none=True))


@router.get("/Encounter")
async def search_encounters(
    patient: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Encounter search — search encounters by patient and/or status.

    @param patient: Patient UUID filter
    @param status: FHIR encounter status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Bundle with matching encounters
    """
    service = FHIRService(db)
    bundle = await service.search_encounters(
        facility_id=current_user.facility_id,
        patient=patient,
        status=status,
    )
    return _fhir_response(bundle.model_dump(exclude_none=True))


# ── Observation ───────────────────────────────────────────────────────────────


@router.get("/Observation")
async def search_observations(
    patient: uuid.UUID | None = Query(None),
    category: str | None = Query(None),
    code: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Observation search — vitals and lab results.

    @param patient: Patient UUID filter
    @param category: vital-signs or laboratory
    @param code: LOINC code filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Bundle with matching observations
    """
    service = FHIRService(db)
    bundle = await service.search_observations(
        facility_id=current_user.facility_id,
        patient=patient,
        category=category,
        code=code,
    )
    return _fhir_response(bundle.model_dump(exclude_none=True))


# ── MedicationRequest ─────────────────────────────────────────────────────────


@router.get("/MedicationRequest")
async def search_medication_requests(
    patient: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR MedicationRequest search — prescriptions.

    @param patient: Patient UUID filter
    @param status: FHIR medication request status
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Bundle with matching medication requests
    """
    service = FHIRService(db)
    bundle = await service.search_medication_requests(
        facility_id=current_user.facility_id,
        patient=patient,
        status=status,
    )
    return _fhir_response(bundle.model_dump(exclude_none=True))


# ── Condition ─────────────────────────────────────────────────────────────────


@router.get("/Condition")
async def search_conditions(
    patient: uuid.UUID | None = Query(None),
    clinical_status: str | None = Query(None, alias="clinical-status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR Condition search — diagnoses.

    @param patient: Patient UUID filter
    @param clinical_status: FHIR clinical status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR Bundle with matching conditions
    """
    service = FHIRService(db)
    bundle = await service.search_conditions(
        facility_id=current_user.facility_id,
        patient=patient,
        clinical_status=clinical_status,
    )
    return _fhir_response(bundle.model_dump(exclude_none=True))


# ── DiagnosticReport ──────────────────────────────────────────────────────────


@router.get("/DiagnosticReport/{order_id}")
async def read_diagnostic_report(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_patient_read),
) -> JSONResponse:
    """
    FHIR DiagnosticReport read — lab order with result references.

    @param order_id: Lab order UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns FHIR DiagnosticReport or OperationOutcome
    """
    service = FHIRService(db)
    report = await service.get_diagnostic_report(order_id, current_user.facility_id)
    if not report:
        return _not_found("DiagnosticReport", str(order_id))
    return _fhir_response(report.model_dump(exclude_none=True))
