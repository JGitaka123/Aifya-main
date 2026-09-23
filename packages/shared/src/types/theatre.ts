/** Theatre type */
export type TheatreType = "general" | "orthopaedic" | "cardiac" | "neuro" | "ophthalmic" | "obstetric" | "ent" | "dental" | "minor";

/** Theatre status */
export type TheatreStatus = "available" | "in_use" | "cleaning" | "maintenance" | "closed";

/** Surgical priority */
export type SurgicalPriority = "emergency" | "urgent" | "elective";

/** Anaesthesia type */
export type AnaesthesiaType = "general" | "spinal" | "epidural" | "regional" | "local" | "sedation";

/** Surgical case status */
export type SurgicalCaseStatus = "scheduled" | "preop" | "in_progress" | "in_recovery" | "completed" | "cancelled" | "postponed";

/** Theatre creation */
export interface TheatreCreate {
  name: string;
  theatre_type?: TheatreType;
  floor?: string | null;
  equipment?: Record<string, unknown> | null;
  notes?: string | null;
}

/** Theatre response */
export interface TheatreResponse {
  id: string;
  name: string;
  code: string;
  theatre_type: string;
  status: string;
  floor: string | null;
  equipment: Record<string, unknown> | null;
  is_active: boolean;
  notes: string | null;
}

/** Surgical case creation */
export interface SurgicalCaseCreate {
  patient_id: string;
  encounter_id?: string | null;
  theatre_id?: string | null;
  scheduled_date: string;
  estimated_duration_min?: number;
  priority?: SurgicalPriority;
  procedure_name: string;
  procedure_code?: string | null;
  laterality?: string | null;
  diagnosis?: string | null;
  anaesthesia_type?: AnaesthesiaType | null;
  anaesthetist_id?: string | null;
  lead_surgeon_id: string;
  assistant_surgeon_id?: string | null;
  scrub_nurse_id?: string | null;
  circulating_nurse_id?: string | null;
  notes?: string | null;
}

/** Surgical case response */
export interface SurgicalCaseResponse {
  id: string;
  case_number: string;
  patient_id: string;
  encounter_id: string | null;
  theatre_id: string | null;
  scheduled_date: string;
  estimated_duration_min: number;
  priority: string;
  procedure_name: string;
  procedure_code: string | null;
  laterality: string | null;
  diagnosis: string | null;
  anaesthesia_type: string | null;
  anaesthetist_id: string | null;
  lead_surgeon_id: string;
  assistant_surgeon_id: string | null;
  scrub_nurse_id: string | null;
  circulating_nurse_id: string | null;
  status: string;
  preop_start: string | null;
  surgery_start: string | null;
  surgery_end: string | null;
  recovery_start: string | null;
  recovery_end: string | null;
  operative_findings: string | null;
  operative_notes: string | null;
  specimens: Record<string, unknown> | null;
  implants: Record<string, unknown> | null;
  complications: string | null;
  blood_loss_ml: number | null;
  postop_instructions: string | null;
  preop_checklist: Record<string, unknown> | null;
  timeout_checklist: Record<string, unknown> | null;
  signout_checklist: Record<string, unknown> | null;
  cancellation_reason: string | null;
  notes: string | null;
  created_at: string;
}

/** Surgical case list item */
export interface SurgicalCaseListItem {
  id: string;
  case_number: string;
  patient_id: string;
  patient_name: string | null;
  theatre_name: string | null;
  scheduled_date: string;
  procedure_name: string;
  priority: string;
  lead_surgeon_name: string | null;
  status: string;
}

/** Surgical case list response */
export interface SurgicalCaseListResponse {
  items: SurgicalCaseListItem[];
  total: number;
}

/** Operative notes request */
export interface OperativeNotesRequest {
  operative_findings?: string | null;
  operative_notes?: string | null;
  specimens?: Record<string, unknown> | null;
  implants?: Record<string, unknown> | null;
  complications?: string | null;
  blood_loss_ml?: number | null;
  postop_instructions?: string | null;
}

/** Theatre summary */
export interface TheatreSummary {
  total_theatres: number;
  available_theatres: number;
  in_use_theatres: number;
  scheduled_today: number;
  completed_today: number;
  emergency_cases: number;
  cancelled_today: number;
}
