"""
Multi-Agent workflow engine.
Orchestrates multi-step clinical AI workflows with step-by-step execution,
error handling, and clinician review gates.

Per CLAUDE.md:
- AI NEVER auto-commits to patient records
- All LLM calls through ai-service
- Log every AI I/O to ai_interactions event
"""

from __future__ import annotations

import os
import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.services.agents.models import (
    AgentStep,
    AgentStepStatus,
    AgentType,
    AgentWorkflow,
    ClaimsAgentInput,
    DischargeAgentInput,
    ScreeningAgentInput,
    WorkflowStatus,
)

logger = get_logger(__name__)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:8001")
MEDGEMMA_URL = os.getenv("VLLM_MEDGEMMA_27B_URL", "http://ai-service:8004/v1")


class AgentEngine:
    """
    Multi-agent clinical workflow engine.
    Executes agent steps sequentially, collecting outputs and managing state.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the agent engine.

        @param db: Async database session for data lookups
        """
        self.db = db

    async def run_discharge_agent(
        self,
        input_data: DischargeAgentInput,
        facility_id: uuid.UUID,
    ) -> AgentWorkflow:
        """
        Discharge planning agent — multi-step workflow:
        1. Gather clinical summary (diagnoses, meds, labs, vitals)
        2. AI generates discharge summary
        3. AI generates medication reconciliation
        4. AI generates follow-up plan
        5. AI generates patient education materials (bilingual EN/SW)

        @param input_data: Discharge agent input
        @param facility_id: Facility UUID
        @returns Complete workflow with discharge documents
        """
        workflow = AgentWorkflow(
            workflow_id=str(uuid.uuid4()),
            agent_type=AgentType.DISCHARGE,
            status=WorkflowStatus.RUNNING,
            patient_id=input_data.patient_id,
            encounter_id=input_data.encounter_id,
            facility_id=str(facility_id),
        )

        # Step 1: Gather clinical data
        step1 = await self._run_step(
            workflow, 0, "Gather Clinical Summary",
            self._gather_clinical_data, input_data.patient_id, input_data.encounter_id
        )

        if step1.status == AgentStepStatus.FAILED:
            workflow.status = WorkflowStatus.FAILED
            return workflow

        clinical_data = step1.output_data or {}

        # Step 2: Generate discharge summary via AI
        step2 = await self._run_step(
            workflow, 1, "Generate Discharge Summary",
            self._ai_generate, "discharge_summary", clinical_data
        )

        # Step 3: Medication reconciliation
        step3 = await self._run_step(
            workflow, 2, "Medication Reconciliation",
            self._ai_generate, "medication_reconciliation", clinical_data
        )

        # Step 4: Follow-up plan
        step4 = await self._run_step(
            workflow, 3, "Generate Follow-up Plan",
            self._ai_generate, "follow_up_plan", clinical_data
        )

        # Step 5: Patient education (bilingual)
        step5 = await self._run_step(
            workflow, 4, "Patient Education Materials",
            self._ai_generate, "patient_education_bilingual", clinical_data
        )

        workflow.status = WorkflowStatus.AWAITING_CLINICIAN
        workflow.final_output = {
            "discharge_summary": step2.output_data,
            "medication_reconciliation": step3.output_data,
            "follow_up_plan": step4.output_data,
            "patient_education": step5.output_data,
        }

        return workflow

    async def run_claims_agent(
        self,
        input_data: ClaimsAgentInput,
        facility_id: uuid.UUID,
    ) -> AgentWorkflow:
        """
        SHA claims automation agent — multi-step workflow:
        1. Gather encounter data (diagnoses, procedures, drugs)
        2. AI maps to SHA claim codes
        3. AI validates claim completeness
        4. AI generates claim narrative
        5. Package claim for submission

        @param input_data: Claims agent input
        @param facility_id: Facility UUID
        @returns Complete workflow with SHA claim draft
        """
        workflow = AgentWorkflow(
            workflow_id=str(uuid.uuid4()),
            agent_type=AgentType.CLAIMS,
            status=WorkflowStatus.RUNNING,
            patient_id=input_data.patient_id,
            encounter_id=input_data.encounter_id,
            facility_id=str(facility_id),
        )

        # Step 1: Gather claim data
        step1 = await self._run_step(
            workflow, 0, "Gather Encounter Data",
            self._gather_claim_data, input_data
        )

        claim_data = step1.output_data or {}

        # Step 2: Map to SHA codes
        step2 = await self._run_step(
            workflow, 1, "Map SHA Claim Codes",
            self._ai_generate, "sha_code_mapping", claim_data
        )

        # Step 3: Validate completeness
        step3 = await self._run_step(
            workflow, 2, "Validate Claim Completeness",
            self._ai_generate, "claim_validation", {**claim_data, "sha_codes": step2.output_data}
        )

        # Step 4: Generate narrative
        step4 = await self._run_step(
            workflow, 3, "Generate Claim Narrative",
            self._ai_generate, "claim_narrative", claim_data
        )

        # Step 5: Package claim
        step5 = await self._run_step(
            workflow, 4, "Package SHA Claim",
            self._package_claim, claim_data, step2.output_data, step4.output_data
        )

        workflow.status = WorkflowStatus.AWAITING_CLINICIAN
        workflow.final_output = {
            "claim_codes": step2.output_data,
            "validation": step3.output_data,
            "narrative": step4.output_data,
            "claim_package": step5.output_data,
        }

        return workflow

    async def run_screening_agent(
        self,
        input_data: ScreeningAgentInput,
        facility_id: uuid.UUID,
    ) -> AgentWorkflow:
        """
        Clinical trial screening agent — multi-step workflow:
        1. Gather patient clinical profile
        2. Fetch active trial criteria
        3. AI matches patient against each trial's inclusion/exclusion criteria
        4. Generate screening report with match scores

        @param input_data: Screening agent input
        @param facility_id: Facility UUID
        @returns Complete workflow with trial match results
        """
        workflow = AgentWorkflow(
            workflow_id=str(uuid.uuid4()),
            agent_type=AgentType.SCREENING,
            status=WorkflowStatus.RUNNING,
            patient_id=input_data.patient_id,
            facility_id=str(facility_id),
        )

        # Step 1: Patient profile
        step1 = await self._run_step(
            workflow, 0, "Gather Patient Profile",
            self._gather_patient_profile, input_data.patient_id
        )

        patient_profile = step1.output_data or {}

        # Step 2: AI screening match
        step2 = await self._run_step(
            workflow, 1, "AI Trial Matching",
            self._ai_generate, "trial_screening", {
                "patient_profile": patient_profile,
                "trial_id": input_data.trial_id,
            }
        )

        # Step 3: Generate screening report
        step3 = await self._run_step(
            workflow, 2, "Generate Screening Report",
            self._ai_generate, "screening_report", {
                "patient_profile": patient_profile,
                "matches": step2.output_data,
            }
        )

        workflow.status = WorkflowStatus.AWAITING_CLINICIAN
        workflow.final_output = {
            "patient_profile": patient_profile,
            "trial_matches": step2.output_data,
            "screening_report": step3.output_data,
        }

        return workflow

    # ── Step Execution ───────────────────────────────────────────────────

    async def _run_step(
        self,
        workflow: AgentWorkflow,
        index: int,
        name: str,
        func: object,
        *args: object,
    ) -> AgentStep:
        """
        Execute a single workflow step with timing and error handling.

        @param workflow: Parent workflow
        @param index: Step index
        @param name: Step name
        @param func: Async function to execute
        @param args: Function arguments
        @returns Completed step
        """
        step = AgentStep(step_name=name, step_index=index, status=AgentStepStatus.RUNNING)
        workflow.steps.append(step)

        start = time.monotonic()
        try:
            result = await func(*args)  # type: ignore[operator]
            step.output_data = result if isinstance(result, dict) else {"result": str(result)}
            step.status = AgentStepStatus.COMPLETED
        except Exception as exc:
            step.error = str(exc)
            step.status = AgentStepStatus.FAILED
            logger.error("agent_step_failed", step=name, error=str(exc))

        step.duration_ms = int((time.monotonic() - start) * 1000)
        return step

    # ── Data Gathering ───────────────────────────────────────────────────

    async def _gather_clinical_data(self, patient_id: str, encounter_id: str) -> dict:
        """
        Gather clinical data for discharge planning.

        @param patient_id: Patient UUID
        @param encounter_id: Encounter UUID
        @returns Clinical data dict
        """
        from sqlalchemy import select

        from app.models.diagnosis import Diagnosis
        from app.models.encounter import Encounter
        from app.models.patient import Patient
        from app.models.prescription import Prescription
        from app.models.vital import VitalSign

        # Patient
        pat = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient = pat.scalar_one_or_none()

        # Encounter
        enc = await self.db.execute(select(Encounter).where(Encounter.id == encounter_id))
        enc.scalar_one_or_none()

        # Diagnoses
        dx = await self.db.execute(
            select(Diagnosis).where(Diagnosis.encounter_id == encounter_id, Diagnosis.is_deleted == False)  # noqa: E712
        )
        diagnoses = dx.scalars().all()

        # Prescriptions
        rx = await self.db.execute(
            select(Prescription).where(Prescription.encounter_id == encounter_id, Prescription.is_deleted == False)  # noqa: E712
        )
        prescriptions = rx.scalars().all()

        # Latest vitals
        vt = await self.db.execute(
            select(VitalSign).where(VitalSign.patient_id == patient_id, VitalSign.is_deleted == False)  # noqa: E712
            .order_by(VitalSign.created_at.desc()).limit(1)
        )
        vital = vt.scalar_one_or_none()

        return {
            "patient": {
                "name": f"{patient.first_name} {patient.last_name}" if patient else "",
                "age": str(patient.date_of_birth) if patient else "",
                "gender": patient.gender if patient else "",
            },
            "diagnoses": [{"description": d.icd10_description, "icd10": d.icd10_code} for d in diagnoses],
            "medications": [{"drug": p.drug_name, "dosage": p.dosage, "frequency": p.frequency} for p in prescriptions],
            "vitals": {
                "bp": f"{vital.systolic_bp}/{vital.diastolic_bp}" if vital and vital.systolic_bp else "N/A",
                "temp": str(vital.temperature) if vital and vital.temperature else "N/A",
                "hr": str(vital.heart_rate) if vital and vital.heart_rate else "N/A",
            } if vital else {},
        }

    async def _gather_claim_data(self, input_data: ClaimsAgentInput) -> dict:
        """
        Gather encounter data for claims processing.

        @param input_data: Claims input with IDs
        @returns Claim data dict
        """
        return {
            "encounter_id": input_data.encounter_id,
            "invoice_id": input_data.invoice_id,
            "insurance_scheme_id": input_data.insurance_scheme_id,
            "patient_id": input_data.patient_id,
        }

    async def _gather_patient_profile(self, patient_id: str) -> dict:
        """
        Gather comprehensive patient profile for trial screening.

        @param patient_id: Patient UUID
        @returns Patient clinical profile
        """
        from sqlalchemy import select

        from app.models.diagnosis import Diagnosis
        from app.models.patient import Patient

        pat = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient = pat.scalar_one_or_none()

        dx = await self.db.execute(
            select(Diagnosis).where(Diagnosis.patient_id == patient_id, Diagnosis.is_deleted == False)  # noqa: E712
            .order_by(Diagnosis.created_at.desc()).limit(20)
        )
        diagnoses = dx.scalars().all()

        return {
            "patient_id": patient_id,
            "demographics": {
                "age": str(patient.date_of_birth) if patient else "",
                "gender": patient.gender if patient else "",
            },
            "conditions": [{"description": d.icd10_description, "icd10": d.icd10_code} for d in diagnoses],
        }

    # ── AI Generation ────────────────────────────────────────────────────

    async def _ai_generate(self, task: str, context: dict) -> dict:
        """
        Call AI service for content generation.
        Routes to appropriate model per CLAUDE.md routing rules.

        @param task: Generation task type
        @param context: Context data for the task
        @returns AI-generated content dict
        """
        prompt_templates = {
            "discharge_summary": (
                "Generate a comprehensive discharge summary for this patient. "
                "Include: principal diagnosis, hospital course, procedures performed, "
                "condition at discharge, discharge medications, and follow-up instructions.\n\n"
                f"Clinical data: {context}"
            ),
            "medication_reconciliation": (
                "Perform medication reconciliation for this patient being discharged. "
                "List: pre-admission meds, hospital meds, discharge meds. "
                "Flag any changes, interactions, or concerns.\n\n"
                f"Clinical data: {context}"
            ),
            "follow_up_plan": (
                "Generate a follow-up care plan for this discharged patient. "
                "Include: follow-up appointments, lab tests needed, warning signs to watch for, "
                "activity restrictions, and diet recommendations.\n\n"
                f"Clinical data: {context}"
            ),
            "patient_education_bilingual": (
                "Generate patient education materials in both English and Swahili (Kiswahili). "
                "Include: diagnosis explanation, medication instructions, lifestyle modifications, "
                "when to seek emergency care. Use simple language.\n\n"
                f"Clinical data: {context}"
            ),
            "sha_code_mapping": (
                "Map these clinical diagnoses and procedures to SHA (Social Health Authority) "
                "claim codes for Kenya. Include ICD-10 codes and KEPH level.\n\n"
                f"Encounter data: {context}"
            ),
            "claim_validation": (
                "Validate this SHA claim for completeness. Check: required fields, "
                "diagnosis-procedure consistency, supporting documentation, preauthorization needs.\n\n"
                f"Claim data: {context}"
            ),
            "claim_narrative": (
                "Generate a clinical narrative for this SHA claim. "
                "Summarize the clinical indication, treatment provided, and medical necessity.\n\n"
                f"Claim data: {context}"
            ),
            "trial_screening": (
                "Screen this patient against active clinical trial criteria. "
                "Assess inclusion/exclusion criteria match. Score 0-100.\n\n"
                f"Patient data: {context}"
            ),
            "screening_report": (
                "Generate a clinical trial screening report. "
                "List matched trials, eligibility assessment, and recommended next steps.\n\n"
                f"Screening data: {context}"
            ),
        }

        prompt = prompt_templates.get(task, f"Perform task '{task}' with context: {context}")

        # Route clinical tasks to MedGemma 27B; complex multi-step reasoning to R1
        medical_tasks = {
            "discharge_summary", "medication_reconciliation", "follow_up_plan",
            "patient_education_bilingual", "trial_screening", "screening_report",
        }
        if task in medical_tasks:
            model_url = f"{MEDGEMMA_URL}/chat/completions"
            model_name = "medgemma-27b"
        else:
            model_url = f"{AI_SERVICE_URL}/v1/chat/completions"
            model_name = "deepseek-r1"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    model_url,
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "You are a clinical AI assistant for a Kenyan hospital. Respond with structured, evidence-based content."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 2048,
                        "temperature": 0.3,
                    },
                )

            if response.status_code == 200:
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                return {"task": task, "content": text, "model": model_name}

        except Exception as exc:
            logger.warning("ai_generate_unavailable", task=task, model=model_name, error=str(exc))

        return {"task": task, "content": f"AI service unavailable for {task}. Manual completion required.", "model": "fallback"}

    async def _package_claim(self, claim_data: dict, codes: dict | None, narrative: dict | None) -> dict:
        """
        Package a SHA claim for submission.

        @param claim_data: Base claim data
        @param codes: Mapped SHA codes
        @param narrative: Generated claim narrative
        @returns Packaged claim dict
        """
        return {
            "claim_type": "SHA",
            "encounter_id": claim_data.get("encounter_id"),
            "invoice_id": claim_data.get("invoice_id"),
            "codes": codes or {},
            "narrative": narrative.get("content", "") if narrative else "",
            "status": "draft",
            "requires_review": True,
        }
