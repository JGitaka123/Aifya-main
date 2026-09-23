"""
Clinical Decision Support data models.
Defines alert severity, categories, and the CDS alert structure.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertSeverity(StrEnum):
    """CDS alert severity levels — determines UI treatment and blocking behavior."""

    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFO = "info"


class AlertCategory(StrEnum):
    """Classification of CDS alerts for routing and display."""

    DRUG_INTERACTION = "drug_interaction"
    DRUG_ALLERGY = "drug_allergy"
    DRUG_CONDITION = "drug_condition"
    DRUG_AGE = "drug_age"
    DRUG_PREGNANCY = "drug_pregnancy"
    DRUG_DUPLICATE = "drug_duplicate"
    DRUG_DOSE = "drug_dose"
    VITAL_CRITICAL = "vital_critical"
    VITAL_TREND = "vital_trend"
    LAB_CRITICAL = "lab_critical"
    LAB_TREND = "lab_trend"
    LAB_ORGAN_DYSFUNCTION = "lab_organ_dysfunction"
    SEPSIS_RISK = "sepsis_risk"
    DIAGNOSIS_GUIDELINE = "diagnosis_guideline"
    DUPLICATE_ORDER = "duplicate_order"
    READMISSION_RISK = "readmission_risk"
    CLINICAL_PATHWAY = "clinical_pathway"
    FORMULARY_CHECK = "formulary_check"


class AlertAction(StrEnum):
    """Recommended action for the clinician."""

    BLOCK = "block"
    WARN = "warn"
    SUGGEST = "suggest"
    INFORM = "inform"


class CDSAlert(BaseModel):
    """
    A clinical decision support alert.

    @param alert_id: Unique alert identifier
    @param severity: Alert severity level
    @param category: Alert classification
    @param action: Recommended clinician action
    @param title: Short alert title
    @param message: Detailed alert description
    @param source_rule: Rule that triggered this alert
    @param affected_items: List of affected drug names, test codes, etc.
    @param evidence: Supporting data (thresholds, references)
    @param overridable: Whether the clinician can override this alert
    @param requires_reason: Whether override requires a documented reason
    """

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: AlertSeverity
    category: AlertCategory
    action: AlertAction
    title: str
    message: str
    source_rule: str
    affected_items: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    overridable: bool = True
    requires_reason: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class CDSEvaluationRequest(BaseModel):
    """
    Request to evaluate CDS rules for a clinical context.

    @param patient_id: Patient UUID
    @param encounter_id: Current encounter UUID
    @param facility_id: Facility UUID
    @param trigger: What triggered the evaluation
    @param context: Additional context data
    """

    patient_id: uuid.UUID
    encounter_id: uuid.UUID
    facility_id: uuid.UUID
    trigger: str = Field(
        ..., examples=["prescription_create", "vitals_record", "lab_result"]
    )
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CDSEvaluationResponse(BaseModel):
    """
    Response from CDS evaluation.

    @param alerts: List of triggered alerts
    @param is_blocked: Whether the action should be blocked
    @param blocking_alerts: Subset of alerts that cause blocking
    @param evaluation_time_ms: Time taken for evaluation
    """

    alerts: list[CDSAlert]
    is_blocked: bool = False
    blocking_alerts: list[CDSAlert] = Field(default_factory=list)
    evaluation_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class SepsisScore(BaseModel):
    """
    Sepsis risk assessment using qSOFA + SIRS criteria.

    @param qsofa_score: Quick SOFA score (0-3)
    @param sirs_criteria_met: Number of SIRS criteria met (0-4)
    @param risk_level: Overall risk assessment
    @param components: Individual criteria results
    """

    qsofa_score: int = Field(ge=0, le=3)
    sirs_criteria_met: int = Field(ge=0, le=4)
    risk_level: str = Field(..., examples=["low", "moderate", "high", "critical"])
    components: dict[str, bool] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
