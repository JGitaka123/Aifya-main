/** Lab order priority levels. */
export type LabPriority = "stat" | "urgent" | "routine";

/** Lab order status lifecycle. */
export type LabOrderStatus =
  | "ordered"
  | "collected"
  | "processing"
  | "completed"
  | "cancelled";

/** Lab result status lifecycle. */
export type LabResultStatus = "pending" | "preliminary" | "final" | "cancelled";

/** Interpretation of a lab result. */
export type LabInterpretation =
  | "normal"
  | "abnormal"
  | "critical"
  | "inconclusive";

// ── Lab Worklist ─────────────────────────────────────────────────────────────

/** Lab worklist item (order with patient info and result counts). */
export interface LabWorklistItem {
  id: string;
  order_number: string;
  encounter_id: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  ordered_by: string;
  priority: LabPriority;
  status: LabOrderStatus;
  specimen_type: string | null;
  clinical_info: string | null;
  fasting: boolean;
  test_count: number;
  pending_count: number;
  critical_count: number;
  created_at: string;
}

/** Lab worklist response. */
export interface LabWorklistResponse {
  items: LabWorklistItem[];
  total: number;
}

// ── Lab Order Detail ─────────────────────────────────────────────────────────

/** Lab order response from the API. */
export interface LabOrderDetail {
  id: string;
  encounter_id: string;
  patient_id: string;
  ordered_by: string;
  order_number: string;
  priority: LabPriority;
  status: LabOrderStatus;
  specimen_type: string | null;
  specimen_collected_at: string | null;
  clinical_info: string | null;
  fasting: boolean;
  total_cost_cents: number | null;
  created_at: string;
}

/** Full lab order with results and patient info. */
export interface LabOrderWithResults {
  order: LabOrderDetail;
  results: LabResultDetail[];
  patient_name: string | null;
  patient_mrn: string | null;
}

// ── Lab Results ──────────────────────────────────────────────────────────────

/** Full lab result record. */
export interface LabResultDetail {
  id: string;
  order_id: string;
  patient_id: string;
  performed_by: string | null;
  verified_by: string | null;
  test_code: string;
  test_name: string;
  loinc_code: string | null;
  panel_name: string | null;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  reference_range: string | null;
  interpretation: LabInterpretation | null;
  is_critical: boolean;
  is_abnormal: boolean;
  critical_notified: boolean;
  critical_notified_to: string | null;
  critical_notified_at: string | null;
  status: LabResultStatus;
  resulted_at: string | null;
  verified_at: string | null;
  notes: string | null;
  method: string | null;
  created_at: string;
}

/** Payload for entering a lab result. */
export interface LabResultEntry {
  result_value?: string | null;
  result_numeric?: number | null;
  result_unit?: string | null;
  reference_range?: string | null;
  interpretation?: LabInterpretation | null;
  is_abnormal?: boolean;
  notes?: string | null;
  method?: string | null;
}

/** Payload for verifying a lab result. */
export interface LabResultVerify {
  notes?: string | null;
}

/** Payload for recording critical value notification. */
export interface CriticalNotifyRequest {
  notified_to: string;
}

/** Specimen collection request. */
export interface SpecimenCollectRequest {
  specimen_id?: string | null;
}
