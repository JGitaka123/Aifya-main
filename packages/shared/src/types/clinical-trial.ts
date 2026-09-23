/**
 * Clinical Trials types.
 * ICH-GCP compliant trial management, participant tracking, adverse events,
 * AI screening, REDCap integration, visit scheduling.
 */

// ── Enums ───────────────────────────────────────────────────────────────────

/** Trial phase */
export type TrialPhase = "I" | "II" | "III" | "IV" | "observational" | "registry";

/** Trial study type */
export type TrialStudyType =
  | "interventional"
  | "observational"
  | "registry"
  | "diagnostic"
  | "pragmatic"
  | "adaptive";

/** Trial status */
export type TrialStatus =
  | "setup"
  | "recruiting"
  | "active"
  | "follow_up"
  | "completed"
  | "suspended"
  | "terminated"
  | "withdrawn";

/** Participant status */
export type ParticipantStatus =
  | "pre_screened"
  | "screened"
  | "screen_failed"
  | "enrolled"
  | "active"
  | "on_hold"
  | "completed"
  | "withdrawn"
  | "lost_to_followup"
  | "deceased";

/** Visit status */
export type VisitStatus =
  | "scheduled"
  | "completed"
  | "missed"
  | "cancelled"
  | "out_of_window"
  | "unscheduled";

/** AE severity */
export type AESeverity = "mild" | "moderate" | "severe";

/** AE relatedness */
export type AERelatedness = "unrelated" | "unlikely" | "possible" | "probable" | "definite";

/** AI screening investigator decision */
export type ScreeningDecision = "proceed_to_screen" | "not_eligible" | "defer" | "already_screened";

/** REDCap sync mode */
export type RedcapSyncMode = "push_only" | "pull_only" | "bidirectional";

// ── Trial ───────────────────────────────────────────────────────────────────

/** Trial creation */
export interface TrialCreate {
  title: string;
  short_title?: string | null;
  phase?: TrialPhase | null;
  study_type: TrialStudyType;
  therapeutic_area?: string | null;
  sponsor: string;
  principal_investigator_id?: string | null;
  co_investigators?: Record<string, unknown> | null;
  irb_approval_number?: string | null;
  irb_approval_date?: string | null;
  irb_expiry_date?: string | null;
  ethics_committee?: string | null;
  nacosti_permit?: string | null;
  protocol_version: string;
  protocol_date: string;
  protocol_document_url?: string | null;
  inclusion_criteria: Record<string, unknown>;
  exclusion_criteria: Record<string, unknown>;
  target_enrollment?: number | null;
  nct_number?: string | null;
  pactr_number?: string | null;
  redcap_project_id?: number | null;
  redcap_api_url?: string | null;
  redcap_api_token_vault_key?: string | null;
  redcap_field_mapping?: Record<string, unknown> | null;
  redcap_sync_enabled?: boolean;
  redcap_sync_mode?: RedcapSyncMode;
  start_date?: string | null;
  end_date?: string | null;
}

/** Trial update */
export interface TrialUpdate {
  title?: string;
  short_title?: string | null;
  phase?: TrialPhase | null;
  therapeutic_area?: string | null;
  principal_investigator_id?: string | null;
  co_investigators?: Record<string, unknown> | null;
  irb_approval_number?: string | null;
  irb_approval_date?: string | null;
  irb_expiry_date?: string | null;
  ethics_committee?: string | null;
  nacosti_permit?: string | null;
  protocol_version?: string;
  protocol_date?: string;
  protocol_document_url?: string | null;
  amendments?: Record<string, unknown> | null;
  inclusion_criteria?: Record<string, unknown>;
  exclusion_criteria?: Record<string, unknown>;
  target_enrollment?: number | null;
  nct_number?: string | null;
  pactr_number?: string | null;
  redcap_project_id?: number | null;
  redcap_api_url?: string | null;
  redcap_api_token_vault_key?: string | null;
  redcap_field_mapping?: Record<string, unknown> | null;
  redcap_sync_enabled?: boolean;
  redcap_sync_mode?: RedcapSyncMode;
  start_date?: string | null;
  end_date?: string | null;
}

/** Trial status update */
export interface TrialStatusUpdate {
  status: TrialStatus;
}

/** Trial response */
export interface TrialResponse {
  id: string;
  trial_code: string;
  nct_number: string | null;
  pactr_number: string | null;
  title: string;
  short_title: string | null;
  phase: string | null;
  study_type: string;
  therapeutic_area: string | null;
  sponsor: string;
  principal_investigator_id: string | null;
  co_investigators: Record<string, unknown> | null;
  irb_approval_number: string | null;
  irb_approval_date: string | null;
  irb_expiry_date: string | null;
  ethics_committee: string | null;
  nacosti_permit: string | null;
  protocol_version: string;
  protocol_date: string;
  protocol_document_url: string | null;
  amendments: Record<string, unknown> | null;
  inclusion_criteria: Record<string, unknown>;
  exclusion_criteria: Record<string, unknown>;
  target_enrollment: number | null;
  redcap_project_id: number | null;
  redcap_api_url: string | null;
  redcap_field_mapping: Record<string, unknown> | null;
  redcap_sync_enabled: boolean;
  redcap_sync_mode: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

/** Trial list item */
export interface TrialListItem {
  id: string;
  trial_code: string;
  title: string;
  short_title: string | null;
  phase: string | null;
  study_type: string;
  therapeutic_area: string | null;
  sponsor: string;
  status: string;
  target_enrollment: number | null;
  enrolled_count: number;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

/** Trial list response */
export interface TrialListResponse {
  items: TrialListItem[];
  total: number;
}

// ── Participant ─────────────────────────────────────────────────────────────

/** Participant enrollment */
export interface ParticipantEnroll {
  patient_id: string;
  randomization_arm?: string | null;
  consent_version?: string | null;
  consent_date?: string | null;
  consent_document_url?: string | null;
  consent_witness?: string | null;
}

/** Participant status update */
export interface ParticipantStatusUpdate {
  status: ParticipantStatus;
  screen_fail_reason?: string | null;
  withdrawal_reason?: string | null;
  completion_status?: string | null;
}

/** Participant response */
export interface ParticipantResponse {
  id: string;
  trial_id: string;
  patient_id: string;
  participant_number: string;
  randomization_arm: string | null;
  randomization_date: string | null;
  status: string;
  screening_date: string | null;
  screened_by: string | null;
  screen_fail_reason: string | null;
  eligibility_check: Record<string, unknown> | null;
  ai_eligibility_score: number | null;
  consent_version: string | null;
  consent_date: string | null;
  consent_document_url: string | null;
  consent_witness: string | null;
  consent_withdrawn: boolean;
  consent_withdrawn_date: string | null;
  consent_withdrawn_reason: string | null;
  enrollment_date: string | null;
  enrolled_by: string | null;
  completion_date: string | null;
  completion_status: string | null;
  withdrawal_reason: string | null;
  redcap_record_id: string | null;
  redcap_sync_status: string;
  last_redcap_sync: string | null;
  created_at: string;
}

/** Participant list item */
export interface ParticipantListItem {
  id: string;
  trial_id: string;
  patient_id: string;
  patient_name: string | null;
  participant_number: string;
  randomization_arm: string | null;
  status: string;
  screening_date: string | null;
  enrollment_date: string | null;
  ai_eligibility_score: number | null;
  consent_date: string | null;
  created_at: string;
}

/** Participant list response */
export interface ParticipantListResponse {
  items: ParticipantListItem[];
  total: number;
}

// ── Visit Schedule ──────────────────────────────────────────────────────────

/** Visit schedule creation */
export interface VisitScheduleCreate {
  visit_code: string;
  visit_name: string;
  day_from_enrollment: number;
  window_before_days?: number;
  window_after_days?: number;
  required_assessments?: Record<string, unknown>[];
  is_mandatory?: boolean;
  sort_order?: number;
}

/** Visit schedule response */
export interface VisitScheduleResponse {
  id: string;
  trial_id: string;
  visit_code: string;
  visit_name: string;
  day_from_enrollment: number;
  window_before_days: number;
  window_after_days: number;
  required_assessments: Record<string, unknown>[];
  is_mandatory: boolean;
  sort_order: number;
  created_at: string;
}

// ── Participant Visit ───────────────────────────────────────────────────────

/** Participant visit creation */
export interface ParticipantVisitCreate {
  schedule_id: string;
  encounter_id?: string | null;
  scheduled_date: string;
  actual_date?: string | null;
  status?: VisitStatus;
  assessments_completed?: Record<string, unknown> | null;
  protocol_deviations?: Record<string, unknown> | null;
}

/** Participant visit update */
export interface ParticipantVisitUpdate {
  encounter_id?: string | null;
  actual_date?: string | null;
  status?: VisitStatus;
  assessments_completed?: Record<string, unknown> | null;
  protocol_deviations?: Record<string, unknown> | null;
}

/** Participant visit response */
export interface ParticipantVisitResponse {
  id: string;
  participant_id: string;
  schedule_id: string;
  encounter_id: string | null;
  scheduled_date: string;
  actual_date: string | null;
  status: string;
  assessments_completed: Record<string, unknown> | null;
  protocol_deviations: Record<string, unknown> | null;
  ai_window_alert: boolean;
  ai_missing_assessments: Record<string, unknown> | null;
  redcap_synced: boolean;
  redcap_sync_at: string | null;
  created_at: string;
}

// ── Adverse Event ───────────────────────────────────────────────────────────

/** Adverse event creation */
export interface AdverseEventCreate {
  participant_id: string;
  ae_term: string;
  meddra_code?: string | null;
  meddra_pt?: string | null;
  meddra_soc?: string | null;
  ctcae_grade?: number | null;
  severity: AESeverity;
  is_serious?: boolean;
  seriousness_criteria?: Record<string, unknown> | null;
  relatedness?: AERelatedness | null;
  onset_date: string;
  resolution_date?: string | null;
  outcome?: string | null;
  action_taken?: string | null;
}

/** Adverse event response */
export interface AdverseEventResponse {
  id: string;
  participant_id: string;
  trial_id: string;
  ae_term: string;
  meddra_code: string | null;
  meddra_pt: string | null;
  meddra_soc: string | null;
  ctcae_grade: number | null;
  severity: string;
  is_serious: boolean;
  seriousness_criteria: Record<string, unknown> | null;
  relatedness: string | null;
  onset_date: string;
  resolution_date: string | null;
  outcome: string | null;
  action_taken: string | null;
  reported_by: string;
  reported_date: string;
  sae_aware_date: string | null;
  sae_reported_to_sponsor: string | null;
  sae_reported_to_irb: string | null;
  sae_report_document_url: string | null;
  redcap_synced: boolean;
  created_at: string;
}

/** Adverse event list item */
export interface AdverseEventListItem {
  id: string;
  participant_id: string;
  participant_number: string | null;
  ae_term: string;
  severity: string;
  is_serious: boolean;
  ctcae_grade: number | null;
  relatedness: string | null;
  onset_date: string;
  resolution_date: string | null;
  outcome: string | null;
  reported_date: string;
}

/** Adverse event list response */
export interface AdverseEventListResponse {
  items: AdverseEventListItem[];
  total: number;
}

/** SAE report submission */
export interface SAEReportSubmit {
  sae_aware_date: string;
  sae_report_document_url?: string | null;
  reported_to_sponsor?: boolean;
  reported_to_irb?: boolean;
}

// ── AI Screening ────────────────────────────────────────────────────────────

/** AI screening response */
export interface AIScreeningResponse {
  id: string;
  facility_id: string;
  patient_id: string;
  patient_name: string | null;
  trial_id: string;
  encounter_id: string | null;
  eligibility_score: number;
  criteria_met: Record<string, unknown>;
  criteria_not_met: Record<string, unknown> | null;
  criteria_unknown: Record<string, unknown> | null;
  ai_reasoning: string | null;
  model_version: string | null;
  investigator_reviewed: boolean;
  investigator_id: string | null;
  investigator_decision: string | null;
  review_notes: string | null;
  created_at: string;
}

/** AI screening list response */
export interface AIScreeningListResponse {
  items: AIScreeningResponse[];
  total: number;
}

/** AI screening request */
export interface AIScreeningCreate {
  patient_id: string;
  encounter_id?: string | null;
}

/** AI screening review */
export interface AIScreeningReview {
  decision: ScreeningDecision;
  review_notes?: string | null;
}

// ── Summary ─────────────────────────────────────────────────────────────────

/** Clinical trials summary */
export interface TrialsSummary {
  total_trials: number;
  recruiting_trials: number;
  active_trials: number;
  completed_trials: number;
  total_participants: number;
  enrolled_participants: number;
  screen_failures: number;
  total_adverse_events: number;
  serious_adverse_events: number;
  pending_ai_screenings: number;
}
