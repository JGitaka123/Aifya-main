/** Encounter record as returned by the API. */
export interface Encounter {
  id: string;
  facility_id: string;
  patient_id: string;
  encounter_type: EncounterType;
  encounter_date: string;
  department_id: string | null;
  attending_doctor_id: string | null;
  nurse_id: string | null;
  queue_number: number | null;
  triage_category: TriageCategory | null;
  priority: number;
  status: EncounterStatus;
  chief_complaint: string | null;
  disposition: string | null;
  billing_status: string;
  trial_participant_id: string | null;
  created_at: string;
  updated_at: string;
  patient_name: string | null;
  patient_mrn: string | null;
}

/** Who the signed-in clinician is, for the workspace header. */
export interface ClinicianProfile {
  staff_id: string | null;
  name: string;
  profession: string;
  specialty: string | null;
  department_id: string | null;
  department_name: string | null;
}

/** How wide a worklist is read: my own work, my unit, or the facility. */
export type ClinicalScope = "mine" | "department" | "facility";

/** Today's scoped workload, counted by encounter status. */
export interface ClinicalWorklistCounts {
  waiting: number;
  in_consultation: number;
  completed: number;
  total: number;
}

/** One encounter in a clinician's worklist, with its routing labels. */
export interface ClinicalWorklistItem extends Encounter {
  department_name: string | null;
  attending_doctor_name: string | null;
}

/** A clinician's workspace: who they are, and whose care they owe today. */
export interface ClinicalWorklist {
  scope: ClinicalScope;
  facility_wide: boolean;
  clinician: ClinicianProfile;
  counts: ClinicalWorklistCounts;
  items: ClinicalWorklistItem[];
}

export type EncounterType =
  | "opd"
  | "ipd"
  | "emergency"
  | "mch"
  | "dental"
  | "surgical"
  | "follow_up";

export type TriageCategory =
  | "emergency"
  | "urgent"
  | "standard"
  | "non_urgent"
  | "dead";

export type EncounterStatus =
  | "waiting"
  | "in_consultation"
  | "completed"
  | "admitted"
  | "discharged"
  | "cancelled";

/** Payload for creating a new encounter. */
export interface EncounterCreate {
  patient_id: string;
  encounter_type: EncounterType;
  department_id?: string | null;
  /** Doctor the receptionist is directing the patient to. */
  attending_doctor_id?: string | null;
  chief_complaint?: string | null;
  triage_category?: TriageCategory | null;
  priority?: number;
}

/** Payload for updating an encounter. */
export interface EncounterUpdate {
  status?: EncounterStatus;
  attending_doctor_id?: string | null;
  nurse_id?: string | null;
  chief_complaint?: string | null;
  triage_category?: TriageCategory | null;
  priority?: number;
  disposition?: string | null;
  discharge_summary?: string | null;
}

/** OPD queue response. */
export interface QueueResponse {
  items: Encounter[];
  total: number;
}

/** Vital signs record. */
export interface VitalSign {
  id: string;
  encounter_id: string;
  patient_id: string;
  recorded_by: string;
  recorded_at: string;
  systolic_bp: number | null;
  diastolic_bp: number | null;
  heart_rate: number | null;
  temperature: number | null;
  temperature_site: string | null;
  respiratory_rate: number | null;
  oxygen_saturation: number | null;
  on_supplemental_o2: boolean;
  o2_flow_rate: number | null;
  weight_kg: number | null;
  height_cm: number | null;
  bmi: number | null;
  head_circumference_cm: number | null;
  muac_cm: number | null;
  pain_score: number | null;
  blood_glucose: number | null;
  glucose_timing: string | null;
  gcs_eye: number | null;
  gcs_verbal: number | null;
  gcs_motor: number | null;
  is_critical: boolean;
  critical_alerts: string | null;
  created_at: string;
}

/** Payload for recording vital signs. */
export interface VitalSignCreate {
  encounter_id: string;
  patient_id: string;
  systolic_bp?: number | null;
  diastolic_bp?: number | null;
  heart_rate?: number | null;
  temperature?: number | null;
  temperature_site?: string | null;
  respiratory_rate?: number | null;
  oxygen_saturation?: number | null;
  on_supplemental_o2?: boolean;
  o2_flow_rate?: number | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  head_circumference_cm?: number | null;
  muac_cm?: number | null;
  pain_score?: number | null;
  blood_glucose?: number | null;
  glucose_timing?: string | null;
  gcs_eye?: number | null;
  gcs_verbal?: number | null;
  gcs_motor?: number | null;
}

/** Diagnosis record. */
export interface Diagnosis {
  id: string;
  encounter_id: string;
  patient_id: string;
  diagnosed_by: string;
  icd10_code: string;
  icd10_description: string;
  diagnosis_type: "primary" | "secondary" | "differential" | "ruled_out";
  clinical_status: string;
  certainty: string;
  onset_date: string | null;
  resolved_date: string | null;
  notes: string | null;
  is_chronic: boolean;
  created_at: string;
}

/** Payload for creating a diagnosis. */
export interface DiagnosisCreate {
  encounter_id: string;
  patient_id: string;
  icd10_code: string;
  icd10_description: string;
  diagnosis_type: "primary" | "secondary" | "differential" | "ruled_out";
  clinical_status?: string;
  certainty?: string;
  onset_date?: string | null;
  notes?: string | null;
  is_chronic?: boolean;
}

/** Prescription record. */
export interface Prescription {
  id: string;
  encounter_id: string;
  patient_id: string;
  prescriber_id: string;
  drug_name: string;
  drug_code: string | null;
  generic_name: string | null;
  is_keml: boolean;
  atc_code: string | null;
  dosage: string;
  dosage_value: number | null;
  dosage_unit: string | null;
  route: string;
  frequency: string;
  duration_days: number | null;
  quantity: number | null;
  instructions: string | null;
  interaction_checked: boolean;
  interactions: Record<string, unknown> | null;
  status: string;
  dispensed_by: string | null;
  dispensed_at: string | null;
  dispensed_quantity: number | null;
  refills_allowed: number;
  refills_used: number;
  unit_cost_cents: number | null;
  total_cost_cents: number | null;
  created_at: string;
}

/** Payload for creating a prescription. */
export interface PrescriptionCreate {
  encounter_id: string;
  patient_id: string;
  drug_name: string;
  drug_code?: string | null;
  generic_name?: string | null;
  is_keml?: boolean;
  atc_code?: string | null;
  dosage: string;
  dosage_value?: number | null;
  dosage_unit?: string | null;
  route: string;
  frequency: string;
  duration_days?: number | null;
  quantity?: number | null;
  instructions?: string | null;
  refills_allowed?: number;
}

/** Prescription with interaction check results. */
export interface PrescriptionWithInteractions {
  /** Null when blocked — a blocked prescription is never saved. */
  prescription: Prescription | null;
  interactions: DrugInteractionAlert[];
  blocked: boolean;
}

/** Drug interaction alert. */
export interface DrugInteractionAlert {
  severity: "critical" | "major" | "moderate" | "minor";
  interacting_drug: string;
  description: string;
}

/** Lab order record. */
export interface LabOrder {
  id: string;
  encounter_id: string;
  patient_id: string;
  ordered_by: string;
  order_number: string;
  priority: "stat" | "urgent" | "routine";
  status: string;
  specimen_type: string | null;
  specimen_collected_at: string | null;
  clinical_info: string | null;
  fasting: boolean;
  total_cost_cents: number | null;
  created_at: string;
}

/** Individual test within a lab order. */
export interface LabTestRequest {
  test_code: string;
  test_name: string;
  loinc_code?: string | null;
  panel_name?: string | null;
}

/** Payload for creating a lab order. */
export interface LabOrderCreate {
  encounter_id: string;
  patient_id: string;
  priority?: "stat" | "urgent" | "routine";
  specimen_type?: string | null;
  clinical_info?: string | null;
  fasting?: boolean;
  tests: LabTestRequest[];
}

/** Consultation fee the patient owes at reception before seeing a doctor. */
export interface ConsultationFeeQuote {
  encounter_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  department_id: string | null;
  attending_doctor_id: string | null;
  fee_cents: number;
  paid: boolean;
  invoice_id: string | null;
  invoice_number: string | null;
  paid_cents: number;
  balance_cents: number;
  receipt_url: string | null;
}

/** Payment method accepted at the reception desk. */
export type ConsultationPaymentMethod =
  | "cash"
  | "mpesa"
  | "insurance"
  | "exemption";

/** Receptionist settling a consultation fee. */
export interface ConsultationPaymentRequest {
  payment_method: ConsultationPaymentMethod;
  /** Defaults to the full outstanding balance when omitted. */
  amount_cents?: number | null;
  reference_number?: string | null;
  mpesa_transaction_id?: string | null;
  notes?: string | null;
}

/** Front-desk correction to the fee charged for a visit. */
export interface ConsultationFeeUpdate {
  /** New fee in KES cents; must be greater than zero. */
  amount_cents: number;
}

/** Result of collecting a consultation fee, carrying the receipt to print. */
export interface ConsultationPaymentResult {
  encounter_id: string;
  invoice_id: string;
  invoice_number: string;
  fee_cents: number;
  paid_cents: number;
  balance_cents: number;
  status: string;
  payment_id: string | null;
  payment_method: string | null;
  reference_number: string | null;
  received_by: string | null;
  paid_at: string | null;
  receipt_url: string;
}

/** Department option for front-desk routing. */
export interface DepartmentOption {
  id: string;
  code: string;
  name: string;
  department_type: string;
  is_active: boolean;
}
