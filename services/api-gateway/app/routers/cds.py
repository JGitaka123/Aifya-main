"""
CDS (Clinical Decision Support) API Router.
Exposes endpoints for evaluating prescription, vitals, and lab result
CDS rules. All endpoints require authentication and the 'encounters' module.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.cds import (
    CDSAlertResponse,
    CDSEvaluationApiResponse,
    CDSLabRequest,
    CDSPrescriptionRequest,
    CDSVitalsRequest,
)
from app.services.cds.engine import (
    evaluate_lab_result,
    evaluate_prescription,
    evaluate_vitals,
)
from app.services.cds.models import CDSAlert, CDSEvaluationResponse

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("encounters"))])


def _alert_to_response(alert: CDSAlert) -> CDSAlertResponse:
    """
    Convert an internal CDSAlert model to the API response schema.

    @param alert: Internal CDS alert object
    @returns CDSAlertResponse for API serialization
    """
    return CDSAlertResponse(
        alert_id=alert.alert_id,
        severity=alert.severity.value,
        category=alert.category.value,
        action=alert.action.value,
        title=alert.title,
        message=alert.message,
        source_rule=alert.source_rule,
        affected_items=alert.affected_items,
        evidence=alert.evidence,
        overridable=alert.overridable,
        requires_reason=alert.requires_reason,
        created_at=alert.created_at,
    )


def _evaluation_to_response(result: CDSEvaluationResponse) -> CDSEvaluationApiResponse:
    """
    Convert an internal CDSEvaluationResponse to the API response schema.

    @param result: Internal CDS evaluation result
    @returns CDSEvaluationApiResponse for API serialization
    """
    return CDSEvaluationApiResponse(
        alerts=[_alert_to_response(a) for a in result.alerts],
        is_blocked=result.is_blocked,
        blocking_alerts=[_alert_to_response(a) for a in result.blocking_alerts],
        evaluation_time_ms=result.evaluation_time_ms,
    )


@router.post(
    "/evaluate/prescription",
    response_model=CDSEvaluationApiResponse,
    status_code=status.HTTP_200_OK,
)
async def evaluate_prescription_endpoint(
    data: CDSPrescriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CDSEvaluationApiResponse:
    """
    Evaluate CDS rules for a prescription before saving.
    Checks drug interactions, allergies, contraindications, age/pregnancy safety,
    and duplicate therapy.

    @param data: Prescription evaluation request (patient_id, drug_name, encounter_id)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns CDS evaluation response with alerts and blocking status
    """
    facility_id: uuid.UUID = current_user.facility_id

    logger.info(
        "cds_evaluate_prescription_request",
        patient_id=str(data.patient_id),
        drug_name=data.drug_name,
        facility_id=str(facility_id),
    )

    result = await evaluate_prescription(
        db=db,
        patient_id=data.patient_id,
        facility_id=facility_id,
        drug_name=data.drug_name,
        encounter_id=data.encounter_id,
        dosage_value=data.dosage_value,
        dosage_unit=data.dosage_unit,
    )

    return _evaluation_to_response(result)


@router.post(
    "/evaluate/vitals",
    response_model=CDSEvaluationApiResponse,
    status_code=status.HTTP_200_OK,
)
async def evaluate_vitals_endpoint(
    data: CDSVitalsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CDSEvaluationApiResponse:
    """
    Evaluate CDS rules for vital signs.
    Checks age-adjusted vital thresholds and sepsis screening.

    @param data: Vitals evaluation request (patient_id, vitals dict)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns CDS evaluation response with alerts
    """
    facility_id: uuid.UUID = current_user.facility_id

    logger.info(
        "cds_evaluate_vitals_request",
        patient_id=str(data.patient_id),
        facility_id=str(facility_id),
    )

    result = await evaluate_vitals(
        db=db,
        patient_id=data.patient_id,
        facility_id=facility_id,
        vitals=data.vitals,
    )

    return _evaluation_to_response(result)


@router.post(
    "/evaluate/lab",
    response_model=CDSEvaluationApiResponse,
    status_code=status.HTTP_200_OK,
)
async def evaluate_lab_endpoint(
    data: CDSLabRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CDSEvaluationApiResponse:
    """
    Evaluate CDS rules for a lab result.
    Checks trend analysis and organ dysfunction patterns.

    @param data: Lab evaluation request (patient_id, test_code, result_numeric)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns CDS evaluation response with alerts
    """
    facility_id: uuid.UUID = current_user.facility_id

    logger.info(
        "cds_evaluate_lab_request",
        patient_id=str(data.patient_id),
        test_code=data.test_code,
        facility_id=str(facility_id),
    )

    result = await evaluate_lab_result(
        db=db,
        patient_id=data.patient_id,
        facility_id=facility_id,
        test_code=data.test_code,
        result_numeric=data.result_numeric,
    )

    return _evaluation_to_response(result)
