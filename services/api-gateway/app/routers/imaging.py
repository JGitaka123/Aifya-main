"""
AI Medical Imaging Analysis router.
Endpoints for AI-assisted chest X-ray TB screening, retinal scans, and general radiology.
Per CLAUDE.md: AI NEVER auto-commits to patient records — clinician sign-off required.
"""


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.services.imaging.analyzer import ImagingAnalyzer
from app.services.imaging.models import (
    ImagingAnalysisRequest,
    ImagingAnalysisResult,
    ImagingAnalysisType,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("radiology"))])


@router.post("/analyze", response_model=ImagingAnalysisResult)
async def analyze_image(
    request: ImagingAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ImagingAnalysisResult:
    """
    Submit a medical image for AI analysis.
    Returns structured findings that REQUIRE clinician review before recording.

    @param request: Analysis request with image URL and type
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AI analysis result (requires_clinician_review=True always)
    """
    analyzer = ImagingAnalyzer()
    result = await analyzer.analyze(request)

    logger.info(
        "imaging_analysis_complete",
        order_id=request.imaging_order_id,
        type=request.analysis_type,
        findings_count=len(result.findings),
        confidence=result.confidence_score,
        facility_id=str(current_user.facility_id),
    )

    return result


@router.get("/analysis-types")
async def list_analysis_types(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """
    List available AI imaging analysis types.

    @param current_user: Authenticated user from JWT
    @returns Available analysis types with descriptions
    """
    return [
        {
            "type": ImagingAnalysisType.CHEST_XRAY_TB,
            "name": "Chest X-ray TB Screening",
            "description": "AI-assisted tuberculosis screening from chest radiographs",
            "modality": "XR",
        },
        {
            "type": ImagingAnalysisType.RETINAL_SCAN,
            "name": "Retinal Scan Analysis",
            "description": "Diabetic retinopathy grading and glaucoma risk assessment",
            "modality": "fundoscopy",
        },
        {
            "type": ImagingAnalysisType.CHEST_XRAY_GENERAL,
            "name": "General Chest X-ray",
            "description": "AI-assisted general chest radiograph interpretation",
            "modality": "XR",
        },
    ]
