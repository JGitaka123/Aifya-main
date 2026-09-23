/** Emergency arrival mode */
export type ArrivalMode = "walk_in" | "ambulance" | "referral" | "police" | "other";

/** SATS triage category (emergency-specific; see encounter.ts for general TriageCategory) */
export type EmergencyTriageCategory = "emergency" | "urgent" | "standard" | "non_urgent" | "dead";

/** SATS triage color */
export type TriageColor = "red" | "orange" | "yellow" | "green" | "blue";

/** Emergency treatment area */
export type TreatmentArea = "resus" | "acute" | "sub_acute" | "fast_track" | "observation" | "paediatric";

/** Emergency visit status */
export type EmergencyVisitStatus =
  | "arrived"
  | "triaged"
  | "in_treatment"
  | "observation"
  | "admitted"
  | "discharged"
  | "transferred"
  | "deceased"
  | "left_against_advice";

/** Disposition type */
export type DispositionType = "discharge" | "admit" | "transfer" | "deceased" | "left_ama";

/** Emergency visit creation request */
export interface EmergencyVisitCreate {
  patient_id: string;
  arrival_mode?: ArrivalMode;
  brought_by?: string | null;
  chief_complaint: string;
  is_trauma?: boolean;
  allergies_noted?: string | null;
  notes?: string | null;
  /** Link an existing referral, or let the API raise one from the fields below. */
  referral_id?: string | null;
  referred_from_facility_name?: string | null;
  referred_from_facility_mfl?: string | null;
  referral_reason?: string | null;
  referral_urgency?: "emergency" | "urgent" | "routine";
}

/** Emergency visit response */
export interface EmergencyVisitResponse {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  referral_id: string | null;
  visit_number: string;
  arrival_time: string;
  arrival_mode: string;
  brought_by: string | null;
  chief_complaint: string;
  triage_category: string;
  triage_color: string;
  triage_score: number | null;
  triage_time: string | null;
  triage_vitals: Record<string, unknown> | null;
  assigned_doctor_id: string | null;
  treatment_area: string | null;
  treatment_started_at: string | null;
  status: string;
  disposition: string | null;
  disposition_time: string | null;
  disposition_notes: string | null;
  is_trauma: boolean;
  is_resuscitation: boolean;
  allergies_noted: string | null;
  interventions: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

/** Emergency queue list item */
export interface EmergencyListItem {
  id: string;
  visit_number: string;
  patient_id: string;
  patient_name: string | null;
  referral_id?: string | null;
  patient_mrn: string | null;
  arrival_time: string;
  arrival_mode: string;
  chief_complaint: string;
  triage_category: string;
  triage_color: string;
  triage_score: number | null;
  treatment_area: string | null;
  assigned_doctor_name: string | null;
  status: string;
  is_trauma: boolean;
  is_resuscitation: boolean;
}

/** Emergency queue response */
export interface EmergencyListResponse {
  items: EmergencyListItem[];
  total: number;
}

/** Triage request */
export interface TriageRequest {
  triage_category: EmergencyTriageCategory;
  triage_score?: number | null;
  triage_vitals?: Record<string, unknown> | null;
  treatment_area?: TreatmentArea | null;
  notes?: string | null;
}

/** Assign doctor request */
export interface AssignDoctorRequest {
  doctor_id: string;
}

/** Disposition request */
export interface DispositionRequest {
  disposition: DispositionType;
  disposition_notes?: string | null;
  admitted_to_ward_id?: string | null;
  bed_id?: string | null;
  admission_reason?: string | null;
  admission_diagnosis?: string | null;
  accommodation_type?: string | null;
  /** Where the patient is being sent when disposition is "transfer". */
  receiving_facility_id?: string | null;
  receiving_facility_name?: string | null;
  receiving_facility_mfl?: string | null;
  transfer_reason?: string | null;
  transfer_urgency?: "emergency" | "urgent" | "routine";
}

/** Emergency department summary */
export interface EmergencySummary {
  total_today: number;
  awaiting_triage: number;
  in_treatment: number;
  in_observation: number;
  critical_red: number;
  urgent_orange: number;
  discharged_today: number;
  admitted_today: number;
  trauma_cases: number;
}

/** Doctor on the duty roster for a day (active shift assignment). */
export interface DoctorOnDuty {
  id: string;
  first_name: string;
  last_name: string;
  title?: string | null;
  specialization?: string | null;
  department_name?: string | null;
  shift_id?: string | null;
  shift_name?: string | null;
  shift_code?: string | null;
  shift_start_time?: string | null;
  shift_end_time?: string | null;
  is_night_shift?: boolean;
}
