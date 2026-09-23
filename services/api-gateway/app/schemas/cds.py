"""
Pydantic schemas for Clinical Decision Support (CDS) API endpoints.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CDSPrescriptionRequest(BaseModel):
    """
    Request to evaluate CDS rules for a prescription.

    @param patient_id: Patient UUID
    @param drug_name: Drug being prescribed
    @param encounter_id: Optional current encounter UUID
    @param dosage_value: Optional per-dose amount (for weight-based dosing)
    @param dosage_unit: Optional dose unit
    """

    patient_id: uuid.UUID
    drug_name: str = Field(..., min_length=1, max_length=255)
    encounter_id: uuid.UUID | None = None
    dosage_value: float | None = None
    dosage_unit: str | None = Field(None, max_length=20)

    model_config = ConfigDict(from_attributes=True)


class CDSVitalsRequest(BaseModel):
    """
    Request to evaluate CDS rules for vital signs.

    @param patient_id: Patient UUID
    @param vitals: Vital sign values (e.g. heart_rate, systolic_bp, etc.)
    """

    patient_id: uuid.UUID
    vitals: dict[str, float | int | str | None] = Field(
        ..., description="Vital sign key-value pairs"
    )

    model_config = ConfigDict(from_attributes=True)


class CDSLabRequest(BaseModel):
    """
    Request to evaluate CDS rules for a lab result.

    @param patient_id: Patient UUID
    @param test_code: Lab test code (e.g. WBC, HGB, CREAT)
    @param result_numeric: Numeric result value, or None for qualitative results
    """

    patient_id: uuid.UUID
    test_code: str = Field(..., min_length=1, max_length=50)
    result_numeric: float | None = None

    model_config = ConfigDict(from_attributes=True)


class CDSAlertResponse(BaseModel):
    """
    A single CDS alert for API output.

    @param alert_id: Unique alert identifier
    @param severity: Alert severity level (critical, high, moderate, low, info)
    @param category: Alert classification
    @param action: Recommended clinician action (block, warn, suggest, inform)
    @param title: Short alert title
    @param message: Detailed alert description
    @param source_rule: Rule that triggered this alert
    @param affected_items: List of affected drug names, test codes, etc.
    @param evidence: Supporting data (thresholds, references)
    @param overridable: Whether the clinician can override this alert
    @param requires_reason: Whether override requires a documented reason
    @param created_at: When the alert was generated
    """

    alert_id: str
    severity: str
    category: str
    action: str
    title: str
    message: str
    source_rule: str
    affected_items: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    overridable: bool = True
    requires_reason: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CDSEvaluationApiResponse(BaseModel):
    """
    Response from CDS evaluation API endpoint.

    @param alerts: List of triggered alerts
    @param is_blocked: Whether the action should be blocked
    @param blocking_alerts: Subset of alerts that cause blocking
    @param evaluation_time_ms: Time taken for evaluation in milliseconds
    """

    alerts: list[CDSAlertResponse]
    is_blocked: bool = False
    blocking_alerts: list[CDSAlertResponse] = Field(default_factory=list)
    evaluation_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)
