/** Dental visit status */
export type DentalVisitStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

/** Treatment plan status */
export type TreatmentPlanStatus = "draft" | "approved" | "in_progress" | "completed" | "cancelled";

/** Dental chart response */
export interface DentalChartResponse {
  id: string;
  patient_id: string;
  teeth: Record<string, { status: string; notes?: string }>;
  periodontal_status: string | null;
  occlusion_notes: string | null;
  last_xray_date: string | null;
  notes: string | null;
}

/** Dental chart update */
export interface DentalChartUpdate {
  teeth: Record<string, { status: string; notes?: string }>;
  periodontal_status?: string | null;
  occlusion_notes?: string | null;
  last_xray_date?: string | null;
  notes?: string | null;
}

/** Dental visit creation */
export interface DentalVisitCreate {
  patient_id: string;
  encounter_id?: string | null;
  dentist_id: string;
  visit_date?: string | null;
  chief_complaint?: string | null;
  examination_findings?: string | null;
  procedures?: Record<string, unknown> | null;
  diagnosis?: string | null;
  notes?: string | null;
}

/** Dental visit response */
export interface DentalVisitResponse {
  id: string;
  visit_number: string;
  patient_id: string;
  encounter_id: string | null;
  dentist_id: string;
  visit_date: string;
  chief_complaint: string | null;
  examination_findings: string | null;
  procedures: Record<string, unknown> | null;
  diagnosis: string | null;
  status: string;
  notes: string | null;
  created_at: string;
}

/** Dental visit list item */
export interface DentalVisitListItem {
  id: string;
  visit_number: string;
  patient_id: string;
  patient_name: string | null;
  dentist_name: string | null;
  visit_date: string;
  chief_complaint: string | null;
  status: string;
}

/** Dental visit list response */
export interface DentalVisitListResponse {
  items: DentalVisitListItem[];
  total: number;
}

/** A single line item inside a dental treatment plan */
export interface DentalTreatmentPlanItem {
  tooth?: string | null;
  procedure_type?: string | null;
  priority?: string | null;
  estimated_cost?: number | null;
  status?: string | null;
  notes?: string | null;
}

/** Treatment plan creation */
export interface DentalTreatmentPlanCreate {
  patient_id: string;
  dentist_id: string;
  diagnosis?: string | null;
  plan_items?: DentalTreatmentPlanItem[];
  total_estimated_cost?: number;
  notes?: string | null;
}

/** Treatment plan response */
export interface DentalTreatmentPlanResponse {
  id: string;
  plan_number: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  dentist_id: string;
  dentist_name: string | null;
  diagnosis: string | null;
  plan_items: DentalTreatmentPlanItem[];
  total_estimated_cost: number;
  status: string;
  notes: string | null;
  created_at: string;
}

/** Treatment plan status change request */
export interface DentalTreatmentPlanStatusUpdate {
  status: TreatmentPlanStatus;
}

/** Treatment plan list response */
export interface DentalTreatmentPlanListResponse {
  items: DentalTreatmentPlanResponse[];
  total: number;
}

/** Dental summary */
export interface DentalSummary {
  total_patients: number;
  today_visits: number;
  pending_treatments: number;
  completed_today: number;
}
