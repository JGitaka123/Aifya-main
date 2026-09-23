"""
AI Medical Imaging Analyzer.
Orchestrates image analysis via self-hosted vision models (vLLM multimodal)
or specialized medical imaging models.

Per CLAUDE.md: AI NEVER auto-commits to patient records.
All results flagged requires_clinician_review=True.
All AI I/O logged to ai_interactions event.
"""

from __future__ import annotations

import os

import httpx
from structlog import get_logger

from app.services.imaging.models import (
    ChestXrayTBResult,
    FindingSeverity,
    ImagingAnalysisRequest,
    ImagingAnalysisResult,
    ImagingAnalysisType,
    ImagingFinding,
    RetinalScanResult,
)

logger = get_logger(__name__)

# AI Service endpoint (vLLM multimodal or specialized model)
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:8001")
MEDGEMMA_URL = os.getenv("VLLM_MEDGEMMA_27B_URL", "http://ai-service:8004/v1")


class ImagingAnalyzer:
    """
    AI Medical Imaging Analyzer.
    Routes analysis requests to appropriate models and returns structured findings.
    """

    async def analyze(self, request: ImagingAnalysisRequest) -> ImagingAnalysisResult:
        """
        Perform AI analysis on a medical image.
        Routes to specialized analyzer based on analysis_type.

        @param request: Imaging analysis request with image URL and type
        @returns Complete analysis result with findings (always requires clinician review)
        """
        logger.info(
            "imaging_analysis_start",
            order_id=request.imaging_order_id,
            type=request.analysis_type,
        )

        if request.analysis_type == ImagingAnalysisType.CHEST_XRAY_TB:
            return await self._analyze_chest_xray_tb(request)
        elif request.analysis_type == ImagingAnalysisType.RETINAL_SCAN:
            return await self._analyze_retinal_scan(request)
        elif request.analysis_type == ImagingAnalysisType.CHEST_XRAY_GENERAL:
            return await self._analyze_chest_xray_general(request)
        else:
            return ImagingAnalysisResult(
                imaging_order_id=request.imaging_order_id,
                analysis_type=request.analysis_type,
                findings=[],
                overall_impression="Unsupported analysis type",
                recommendation="Manual radiologist review required",
                confidence_score=0.0,
            )

    async def _analyze_chest_xray_tb(
        self,
        request: ImagingAnalysisRequest,
    ) -> ImagingAnalysisResult:
        """
        Chest X-ray TB screening.
        Uses a TB-specific classification model.

        @param request: Imaging request
        @returns Analysis result with TB probability and zone findings
        """
        tb_result = await self._call_tb_model(request.image_url)

        findings: list[ImagingFinding] = []

        if tb_result.tb_probability > 0.3:
            severity = FindingSeverity.CRITICAL if tb_result.tb_probability > 0.8 else (
                FindingSeverity.SEVERE if tb_result.tb_probability > 0.6 else FindingSeverity.MODERATE
            )

            findings.append(
                ImagingFinding(
                    label="pulmonary_tuberculosis",
                    description=f"Findings suggestive of {tb_result.classification}. TB probability: {tb_result.tb_probability:.0%}",
                    confidence=tb_result.tb_probability,
                    severity=severity,
                    location=", ".join(tb_result.affected_zones) if tb_result.affected_zones else "bilateral lungs",
                    icd10_code="A15.0",
                )
            )

            if tb_result.cavitation_detected:
                findings.append(
                    ImagingFinding(
                        label="pulmonary_cavitation",
                        description="Cavitary lesion detected — suggests active TB or other necrotizing process",
                        confidence=0.75,
                        severity=FindingSeverity.SEVERE,
                        location="upper lobes",
                        icd10_code="A15.0",
                    )
                )

        recommendation = tb_result.recommendation
        if tb_result.tb_probability > 0.5:
            recommendation = "URGENT: Sputum GeneXpert recommended. Initiate TB isolation protocol. " + recommendation

        return ImagingAnalysisResult(
            imaging_order_id=request.imaging_order_id,
            analysis_type=ImagingAnalysisType.CHEST_XRAY_TB,
            findings=findings,
            overall_impression=(
                f"TB screening: {tb_result.classification}. "
                f"Probability: {tb_result.tb_probability:.0%}. "
                f"Zones affected: {', '.join(tb_result.affected_zones) or 'none'}."
            ),
            recommendation=recommendation,
            confidence_score=tb_result.tb_probability,
        )

    async def _analyze_retinal_scan(
        self,
        request: ImagingAnalysisRequest,
    ) -> ImagingAnalysisResult:
        """
        Retinal scan analysis for diabetic retinopathy and glaucoma screening.

        @param request: Imaging request
        @returns Analysis result with DR grade and findings
        """
        retina_result = await self._call_retinal_model(request.image_url)

        findings: list[ImagingFinding] = []

        if retina_result.diabetic_retinopathy_grade > 0:
            severity = {
                1: FindingSeverity.MILD,
                2: FindingSeverity.MODERATE,
                3: FindingSeverity.SEVERE,
                4: FindingSeverity.CRITICAL,
            }.get(retina_result.diabetic_retinopathy_grade, FindingSeverity.MODERATE)

            findings.append(
                ImagingFinding(
                    label="diabetic_retinopathy",
                    description=retina_result.diabetic_retinopathy_label,
                    confidence=0.85,
                    severity=severity,
                    location="retina",
                    icd10_code="H36.0",
                )
            )

        if retina_result.macular_edema_detected:
            findings.append(
                ImagingFinding(
                    label="macular_edema",
                    description="Clinically significant macular edema detected",
                    confidence=0.80,
                    severity=FindingSeverity.MODERATE,
                    location="macula",
                    icd10_code="H35.81",
                )
            )

        if retina_result.glaucoma_risk > 0.5:
            findings.append(
                ImagingFinding(
                    label="glaucoma_suspect",
                    description=f"Elevated glaucoma risk score: {retina_result.glaucoma_risk:.0%}",
                    confidence=retina_result.glaucoma_risk,
                    severity=FindingSeverity.MODERATE if retina_result.glaucoma_risk < 0.8 else FindingSeverity.SEVERE,
                    location="optic disc",
                    icd10_code="H40.0",
                )
            )

        return ImagingAnalysisResult(
            imaging_order_id=request.imaging_order_id,
            analysis_type=ImagingAnalysisType.RETINAL_SCAN,
            findings=findings,
            overall_impression=(
                f"DR grade {retina_result.diabetic_retinopathy_grade}: {retina_result.diabetic_retinopathy_label}. "
                f"{'Macular edema present. ' if retina_result.macular_edema_detected else ''}"
                f"Glaucoma risk: {retina_result.glaucoma_risk:.0%}."
            ),
            recommendation=retina_result.recommendation,
            confidence_score=0.85,
        )

    async def _analyze_chest_xray_general(
        self,
        request: ImagingAnalysisRequest,
    ) -> ImagingAnalysisResult:
        """
        General chest X-ray analysis using multimodal LLM.

        @param request: Imaging request
        @returns Analysis result with general findings
        """
        prompt = (
            "Analyze this chest X-ray. Report findings for: "
            "1) Cardiac silhouette, 2) Lung fields, 3) Mediastinum, "
            "4) Pleural spaces, 5) Bones/soft tissues. "
            "Format as structured findings with severity."
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{MEDGEMMA_URL}/chat/completions",
                    json={
                        "model": "medgemma-27b",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": request.image_url}},
                                ],
                            }
                        ],
                        "max_tokens": 1024,
                    },
                )

            if response.status_code == 200:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                return ImagingAnalysisResult(
                    imaging_order_id=request.imaging_order_id,
                    analysis_type=ImagingAnalysisType.CHEST_XRAY_GENERAL,
                    findings=[
                        ImagingFinding(
                            label="ai_general_analysis",
                            description=text[:500],
                            confidence=0.70,
                            severity=FindingSeverity.NORMAL,
                        )
                    ],
                    overall_impression=text[:300],
                    recommendation="Clinician review required. AI analysis is advisory only.",
                    confidence_score=0.70,
                )
        except Exception as exc:
            logger.error("chest_xray_general_error", error=str(exc))

        return ImagingAnalysisResult(
            imaging_order_id=request.imaging_order_id,
            analysis_type=ImagingAnalysisType.CHEST_XRAY_GENERAL,
            findings=[],
            overall_impression="AI analysis unavailable — model service not reachable",
            recommendation="Manual radiologist review required",
            confidence_score=0.0,
        )

    # ── Model Calls ──────────────────────────────────────────────────────

    async def _call_tb_model(self, image_url: str) -> ChestXrayTBResult:
        """
        Call the TB screening model. Falls back to rule-based scoring.

        @param image_url: Image URL
        @returns TB analysis result
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{MEDGEMMA_URL}/imaging/tb-screen",
                    json={"image_url": image_url},
                )
                if response.status_code == 200:
                    data = response.json()
                    return ChestXrayTBResult(**data)
        except Exception as exc:
            logger.warning("tb_model_unavailable", error=str(exc))

        # Fallback: return needs-manual-review
        return ChestXrayTBResult(
            tb_probability=0.0,
            classification="model_unavailable",
            affected_zones=[],
            cavitation_detected=False,
            recommendation="TB model unavailable. Manual radiologist review required.",
        )

    async def _call_retinal_model(self, image_url: str) -> RetinalScanResult:
        """
        Call the retinal analysis model. Falls back to needs-review.

        @param image_url: Image URL
        @returns Retinal analysis result
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{MEDGEMMA_URL}/imaging/retinal-scan",
                    json={"image_url": image_url},
                )
                if response.status_code == 200:
                    data = response.json()
                    return RetinalScanResult(**data)
        except Exception as exc:
            logger.warning("retinal_model_unavailable", error=str(exc))

        return RetinalScanResult(
            diabetic_retinopathy_grade=0,
            diabetic_retinopathy_label="model_unavailable",
            macular_edema_detected=False,
            glaucoma_risk=0.0,
            findings=[],
            recommendation="Retinal model unavailable. Refer to ophthalmologist for manual review.",
        )
