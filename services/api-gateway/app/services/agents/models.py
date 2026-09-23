"""
Multi-agent workflow models.
Defines agent types, step results, and workflow execution state.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class AgentType(StrEnum):
    """Available clinical agent types."""
    DISCHARGE = "discharge"
    CLAIMS = "claims"
    SCREENING = "screening"
    REFERRAL = "referral"


class AgentStepStatus(StrEnum):
    """Status of a single agent step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class WorkflowStatus(StrEnum):
    """Overall workflow execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_CLINICIAN = "awaiting_clinician"


class AgentStep(BaseModel):
    """
    Single step in an agent workflow.

    @param step_name: Human-readable step name
    @param step_index: Order in the workflow
    @param status: Current step status
    @param input_data: Input data for this step
    @param output_data: Output from this step (populated on completion)
    @param error: Error message if failed
    @param duration_ms: Execution time in milliseconds
    """
    step_name: str
    step_index: int
    status: AgentStepStatus = AgentStepStatus.PENDING
    input_data: dict | None = None
    output_data: dict | None = None
    error: str | None = None
    duration_ms: int | None = None


class AgentWorkflow(BaseModel):
    """
    Complete agent workflow execution record.

    @param workflow_id: Unique workflow execution ID
    @param agent_type: Type of agent
    @param status: Overall workflow status
    @param patient_id: Associated patient UUID
    @param encounter_id: Associated encounter UUID (if applicable)
    @param facility_id: Facility UUID
    @param steps: List of workflow steps
    @param final_output: Combined workflow output
    @param requires_clinician_review: True if any step needs human review
    """
    workflow_id: str
    agent_type: AgentType
    status: WorkflowStatus
    patient_id: str
    encounter_id: str | None = None
    facility_id: str
    steps: list[AgentStep] = []
    final_output: dict | None = None
    requires_clinician_review: bool = True  # CRITICAL: per CLAUDE.md


class DischargeAgentInput(BaseModel):
    """
    Input for the discharge planning agent.

    @param patient_id: Patient UUID
    @param encounter_id: Encounter UUID
    @param admission_id: Admission UUID
    """
    patient_id: str
    encounter_id: str
    admission_id: str


class ClaimsAgentInput(BaseModel):
    """
    Input for the SHA claims automation agent.

    @param patient_id: Patient UUID
    @param encounter_id: Encounter UUID
    @param invoice_id: Invoice UUID
    @param insurance_scheme_id: Insurance scheme UUID
    """
    patient_id: str
    encounter_id: str
    invoice_id: str
    insurance_scheme_id: str


class ScreeningAgentInput(BaseModel):
    """
    Input for the clinical trial screening agent.

    @param patient_id: Patient UUID
    @param trial_id: Trial UUID to screen against (or "all" for all active trials)
    """
    patient_id: str
    trial_id: str = "all"
