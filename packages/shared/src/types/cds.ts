/**
 * Clinical Decision Support (CDS) types.
 * Used by the CDS evaluation engine to return alerts for prescriptions,
 * vitals, and lab orders.
 */

/** Severity level for a CDS alert. */
export type AlertSeverity = "critical" | "high" | "moderate" | "low" | "info";

/** Category describing the type of clinical decision support rule. */
export type AlertCategory =
  | "drug_interaction"
  | "drug_allergy"
  | "drug_condition"
  | "drug_age"
  | "drug_pregnancy"
  | "drug_duplicate"
  | "drug_dose"
  | "vital_critical"
  | "vital_trend"
  | "lab_critical"
  | "lab_trend"
  | "lab_organ_dysfunction"
  | "sepsis_risk"
  | "diagnosis_guideline"
  | "duplicate_order"
  | "readmission_risk"
  | "clinical_pathway"
  | "formulary_check";

/** Action the CDS system recommends for the alert. */
export type AlertAction = "block" | "warn" | "suggest" | "inform";

/** A single CDS alert returned by the evaluation engine. */
export interface CDSAlert {
  alert_id: string;
  severity: AlertSeverity;
  category: AlertCategory;
  action: AlertAction;
  title: string;
  message: string;
  source_rule: string;
  affected_items: string[];
  evidence: Record<string, unknown>;
  overridable: boolean;
  requires_reason: boolean;
}

/** Response from the CDS evaluation endpoint. */
export interface CDSEvaluationResponse {
  alerts: CDSAlert[];
  is_blocked: boolean;
  blocking_alerts: CDSAlert[];
  evaluation_time_ms: number;
}

/** Request payload for evaluating prescription CDS rules. */
export interface CDSPrescriptionRequest {
  patient_id: string;
  drug_name: string;
  encounter_id?: string | null;
}

/** Request payload for evaluating vitals CDS rules. */
export interface CDSVitalsRequest {
  patient_id: string;
  vitals: Record<string, number | string | null>;
}

/** Request payload for evaluating lab result CDS rules. */
export interface CDSLabRequest {
  patient_id: string;
  test_code: string;
  result_numeric: number | null;
}
