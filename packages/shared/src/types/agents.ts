/**
 * Multi-Agent Clinical Workflow types.
 * Discharge agent, claims agent, trial screening agent.
 */

/** Available agent types. */
export type AgentType = "discharge" | "claims" | "screening" | "referral";

/** Agent step status. */
export type AgentStepStatus = "pending" | "running" | "completed" | "failed" | "needs_review";

/** Overall workflow status. */
export type WorkflowStatus = "queued" | "running" | "completed" | "failed" | "awaiting_clinician";

/** Single step in an agent workflow. */
export interface AgentStep {
  step_name: string;
  step_index: number;
  status: AgentStepStatus;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
  duration_ms: number | null;
}

/** Complete agent workflow result. */
export interface AgentWorkflow {
  workflow_id: string;
  agent_type: AgentType;
  status: WorkflowStatus;
  patient_id: string;
  encounter_id: string | null;
  facility_id: string;
  steps: AgentStep[];
  final_output: Record<string, unknown> | null;
  requires_clinician_review: boolean;
}

/** Discharge agent input. */
export interface DischargeAgentInput {
  patient_id: string;
  encounter_id: string;
  admission_id: string;
}

/** Claims agent input. */
export interface ClaimsAgentInput {
  patient_id: string;
  encounter_id: string;
  invoice_id: string;
  insurance_scheme_id: string;
}

/** Screening agent input. */
export interface ScreeningAgentInput {
  patient_id: string;
  trial_id?: string;
}

/** Agent type metadata. */
export interface AgentTypeInfo {
  type: AgentType;
  name: string;
  description: string;
  steps: number;
}
