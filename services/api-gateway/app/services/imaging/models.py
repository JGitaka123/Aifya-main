"""
AI Medical Imaging analysis models.
Pydantic schemas for imaging analysis requests, results, and findings.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ImagingAnalysisType(StrEnum):
    """Supported AI imaging analysis types."""
    CHEST_XRAY_TB = "chest_xray_tb"
    RETINAL_SCAN = "retinal_scan"
    CHEST_XRAY_GENERAL = "chest_xray_general"


class FindingSeverity(StrEnum):
    """Severity of an imaging finding."""
    NORMAL = "normal"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class ImagingFinding(BaseModel):
    """
    Single finding from AI image analysis.

    @param label: Finding label (e.g. "pulmonary_tuberculosis")
    @param description: Human-readable description
    @param confidence: Model confidence (0.0-1.0)
    @param severity: Finding severity
    @param location: Anatomical location if applicable
    @param icd10_code: Suggested ICD-10 code
    """
    label: str
    description: str
    confidence: float
    severity: FindingSeverity
    location: str | None = None
    icd10_code: str | None = None


class ImagingAnalysisRequest(BaseModel):
    """
    Request for AI imaging analysis.

    @param imaging_order_id: Radiology order UUID
    @param analysis_type: Type of analysis to perform
    @param image_url: MinIO presigned URL or path to the image
    @param patient_age: Patient age for age-adjusted analysis
    @param patient_sex: Patient sex for sex-adjusted analysis
    """
    imaging_order_id: str
    analysis_type: ImagingAnalysisType
    image_url: str
    patient_age: int | None = None
    patient_sex: str | None = None


class ImagingAnalysisResult(BaseModel):
    """
    Complete AI imaging analysis result.

    @param imaging_order_id: Associated radiology order
    @param analysis_type: Analysis performed
    @param findings: List of detected findings
    @param overall_impression: Summary text
    @param recommendation: Clinical recommendation
    @param confidence_score: Overall analysis confidence
    @param model_version: AI model version used
    @param requires_clinician_review: Always True per CLAUDE.md — AI never auto-commits
    """
    imaging_order_id: str
    analysis_type: ImagingAnalysisType
    findings: list[ImagingFinding]
    overall_impression: str
    recommendation: str
    confidence_score: float
    model_version: str = "1.0.0"
    requires_clinician_review: bool = True  # CRITICAL: AI never auto-commits


class ChestXrayTBResult(BaseModel):
    """
    Chest X-ray TB screening specific result.

    @param tb_probability: Probability of active TB (0.0-1.0)
    @param classification: normal/suspicious/probable_tb
    @param affected_zones: Lung zones with findings
    @param cavitation_detected: Whether cavitation is present
    @param recommendation: Follow-up recommendation
    """
    tb_probability: float
    classification: str
    affected_zones: list[str]
    cavitation_detected: bool
    recommendation: str


class RetinalScanResult(BaseModel):
    """
    Retinal scan analysis specific result.

    @param diabetic_retinopathy_grade: DR grade (0-4)
    @param diabetic_retinopathy_label: Human-readable DR classification
    @param macular_edema_detected: Whether macular edema present
    @param glaucoma_risk: Glaucoma risk score (0.0-1.0)
    @param findings: List of retinal findings
    @param recommendation: Ophthalmology referral recommendation
    """
    diabetic_retinopathy_grade: int
    diabetic_retinopathy_label: str
    macular_edema_detected: bool
    glaucoma_risk: float
    findings: list[str]
    recommendation: str
