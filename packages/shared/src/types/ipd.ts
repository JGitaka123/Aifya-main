/** Ward type options. */
export type WardType =
  | "general"
  | "icu"
  | "hdu"
  | "maternity"
  | "paediatric"
  | "nicu"
  | "psychiatric"
  | "isolation"
  | "surgical"
  | "burns";

/** Bed status options. */
export type BedStatus =
  | "available"
  | "occupied"
  | "reserved"
  | "maintenance"
  | "cleaning";

/** Admission status lifecycle. */
export type AdmissionStatus =
  | "admitted"
  | "on_leave"
  | "transferred"
  | "discharged"
  | "deceased";

/** Discharge type options. */
export type DischargeType =
  | "improved"
  | "recovered"
  | "dama"
  | "absconded"
  | "deceased"
  | "transferred"
  | "referred";

/** Nursing note type. */
export type NursingNoteType =
  | "observation"
  | "medication"
  | "procedure"
  | "shift_handover"
  | "intake_output"
  | "pain_assessment"
  | "wound_care";

// ── Ward ─────────────────────────────────────────────────────────────────────

/** Ward response from the API. */
export interface WardResponse {
  id: string;
  name: string;
  code: string;
  ward_type: WardType;
  department_id: string | null;
  floor: string | null;
  total_beds: number;
  gender_restriction: string | null;
  charge_per_day_cents: number;
  is_active: boolean;
  notes: string | null;
  available_beds: number;
  occupied_beds: number;
}

/** Payload for creating a ward. */
export interface WardCreate {
  name: string;
  code: string;
  ward_type: WardType;
  department_id?: string | null;
  floor?: string | null;
  total_beds?: number;
  gender_restriction?: string | null;
  charge_per_day_cents?: number;
  notes?: string | null;
}

// ── Bed ──────────────────────────────────────────────────────────────────────

/** Bed response from the API. */
export interface BedResponse {
  id: string;
  ward_id: string;
  bed_number: string;
  bed_type: string;
  status: BedStatus;
  current_patient_id: string | null;
  current_admission_id: string | null;
  notes: string | null;
  ward_name: string | null;
  patient_name: string | null;
}

/** Payload for creating a bed. */
export interface BedCreate {
  ward_id: string;
  bed_number: string;
  bed_type?: string;
  notes?: string | null;
}

// ── Admission ────────────────────────────────────────────────────────────────

/** Admission response from the API. */
export interface AdmissionResponse {
  id: string;
  encounter_id: string;
  patient_id: string;
  ward_id: string;
  bed_id: string;
  admission_number: string;
  attending_doctor_id: string | null;
  primary_nurse_id: string | null;
  status: AdmissionStatus;
  admission_reason: string | null;
  admission_diagnosis: string | null;
  admitted_from: string | null;
  accommodation_type: string | null;
  admitted_at: string;
  discharged_at: string | null;
  discharge_type: DischargeType | null;
  discharge_diagnosis: string | null;
  length_of_stay_days: number | null;
  created_at: string;
}

/** Admission list item with patient/ward info. */
export interface AdmissionListItem {
  id: string;
  admission_number: string;
  encounter_id: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  ward_name: string | null;
  bed_number: string | null;
  status: AdmissionStatus;
  admission_diagnosis: string | null;
  admitted_from: string | null;
  admitted_at: string;
  length_of_stay_days: number | null;
}

/** Admission list response. */
export interface AdmissionListResponse {
  items: AdmissionListItem[];
  total: number;
}

/** Payload for admitting a patient. */
export interface AdmissionCreate {
  encounter_id: string;
  patient_id: string;
  ward_id: string;
  bed_id: string;
  attending_doctor_id?: string | null;
  primary_nurse_id?: string | null;
  admission_reason?: string | null;
  admission_diagnosis?: string | null;
  admitted_from?: string | null;
  accommodation_type?: string | null;
}

/** Payload for discharging a patient. */
export interface DischargeRequest {
  discharge_type: DischargeType;
  discharge_diagnosis?: string | null;
  discharge_summary?: string | null;
  follow_up_plan?: string | null;
  discharge_medications?: string | null;
}

/** Payload for transferring an inpatient to the Emergency Department. */
export interface TransferToEmergencyRequest {
  /** Clinical reason for the worsening condition (becomes the ER chief complaint). */
  reason: string;
  notes?: string | null;
}

// ── Nursing Note ─────────────────────────────────────────────────────────────

/** Nursing note response. */
export interface NursingNoteResponse {
  id: string;
  admission_id: string;
  patient_id: string;
  author_id: string;
  note_type: NursingNoteType;
  content: string;
  shift: string | null;
  severity: string | null;
  created_at: string;
}

/** Payload for creating a nursing note. */
export interface NursingNoteCreate {
  note_type: NursingNoteType;
  content: string;
  shift?: string | null;
  severity?: string | null;
}

// ── Dashboard ────────────────────────────────────────────────────────────────

/** Ward board summary for IPD dashboard. */
export interface WardBoardSummary {
  total_wards: number;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  active_admissions: number;
  occupancy_rate: number;
}
