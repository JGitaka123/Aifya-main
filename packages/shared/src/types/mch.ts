/** ANC profile status. */
export type ANCStatus = "active" | "delivered" | "postnatal" | "closed" | "transferred";

/** Pregnancy risk level. */
export type RiskLevel = "low" | "moderate" | "high";

/** Pregnancy outcome. */
export type PregnancyOutcome = "live_birth" | "stillbirth" | "miscarriage" | "abortion" | "ectopic";

/** Mode of delivery. */
export type ModeOfDelivery = "svd" | "assisted_vaginal" | "elective_cs" | "emergency_cs" | "breech";

/** Baby outcome at delivery. */
export type BabyOutcome = "live_birth" | "fresh_stillbirth" | "macerated_stillbirth";

/** Fetal presentation. */
export type FetalPresentation = "cephalic" | "breech" | "transverse" | "oblique";

/** Child record status. */
export type ChildStatus = "active" | "transferred" | "deceased" | "closed";

/** Feeding method. */
export type FeedingMethod = "exclusive_breastfeeding" | "mixed" | "replacement";

/** ANC profile response from API. */
export interface ANCProfileResponse {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  anc_number: string;
  gravida: number;
  parity: number;
  living_children: number;
  lmp_date: string | null;
  expected_delivery_date: string | null;
  first_visit_date: string | null;
  gestation_at_first_visit: number | null;
  risk_level: RiskLevel;
  risk_factors: string[] | null;
  blood_group: string | null;
  hiv_status: string | null;
  on_art: boolean;
  vdrl_status: string | null;
  hepatitis_b: string | null;
  rhesus: string | null;
  pmtct_enrolled: boolean;
  partner_hiv_status: string | null;
  status: ANCStatus;
  pregnancy_outcome: PregnancyOutcome | null;
  notes: string | null;
  created_at: string;
}

/** ANC profile list item with patient info. */
export interface ANCProfileListItem {
  id: string;
  anc_number: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  gravida: number;
  parity: number;
  expected_delivery_date: string | null;
  gestation_weeks: number | null;
  risk_level: RiskLevel;
  status: ANCStatus;
  visit_count: number;
  created_at: string;
}

/** Paginated ANC profile list. */
export interface ANCProfileListResponse {
  items: ANCProfileListItem[];
  total: number;
}

/** Create ANC profile request. */
export interface ANCProfileCreate {
  patient_id: string;
  encounter_id?: string | null;
  gravida: number;
  parity: number;
  living_children?: number;
  lmp_date?: string | null;
  expected_delivery_date?: string | null;
  blood_group?: string | null;
  hiv_status?: string | null;
  on_art?: boolean;
  risk_level?: RiskLevel;
  risk_factors?: string[] | null;
  notes?: string | null;
}

/** ANC visit response. */
export interface ANCVisitResponse {
  id: string;
  anc_profile_id: string;
  patient_id: string;
  provider_id: string;
  visit_number: number;
  visit_date: string;
  gestation_weeks: number | null;
  weight_kg: number | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  pulse_rate: number | null;
  temperature: number | null;
  urine_protein: string | null;
  urine_glucose: string | null;
  fundal_height_cm: number | null;
  fetal_heart_rate: number | null;
  fetal_presentation: FetalPresentation | null;
  fetal_movement: string | null;
  oedema: string | null;
  hb_level: number | null;
  iron_folate_given: boolean;
  tetanus_dose: string | null;
  ipt_malaria_dose: string | null;
  deworming_given: boolean;
  llins_given: boolean;
  birth_plan_discussed: boolean;
  danger_signs_counselled: boolean;
  breastfeeding_counselled: boolean;
  next_visit_date: string | null;
  clinical_notes: string | null;
  complications: string | null;
  referred: boolean;
  referral_reason: string | null;
  created_at: string;
}

/** Create ANC visit request. */
export interface ANCVisitCreate {
  anc_profile_id: string;
  encounter_id?: string | null;
  visit_date: string;
  gestation_weeks?: number | null;
  weight_kg?: number | null;
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  pulse_rate?: number | null;
  temperature?: number | null;
  urine_protein?: string | null;
  urine_glucose?: string | null;
  fundal_height_cm?: number | null;
  fetal_heart_rate?: number | null;
  fetal_presentation?: FetalPresentation | null;
  fetal_movement?: string | null;
  oedema?: string | null;
  hb_level?: number | null;
  iron_folate_given?: boolean;
  tetanus_dose?: string | null;
  ipt_malaria_dose?: string | null;
  deworming_given?: boolean;
  llins_given?: boolean;
  birth_plan_discussed?: boolean;
  danger_signs_counselled?: boolean;
  breastfeeding_counselled?: boolean;
  next_visit_date?: string | null;
  clinical_notes?: string | null;
  complications?: string | null;
  referred?: boolean;
  referral_reason?: string | null;
}

/** Delivery record response. */
export interface DeliveryRecordResponse {
  id: string;
  anc_profile_id: string;
  patient_id: string;
  delivered_by: string;
  delivery_date: string;
  gestation_weeks: number | null;
  mode_of_delivery: ModeOfDelivery;
  duration_of_labour_hours: number | null;
  place_of_delivery: string;
  maternal_outcome: string;
  maternal_complications: string | null;
  blood_loss_ml: number | null;
  episiotomy: boolean;
  tears: string | null;
  baby_outcome: BabyOutcome;
  baby_sex: string | null;
  birth_weight_grams: number | null;
  apgar_1min: number | null;
  apgar_5min: number | null;
  apgar_10min: number | null;
  resuscitation_needed: boolean;
  skin_to_skin: boolean;
  breastfed_within_1hr: boolean;
  vitamin_k_given: boolean;
  eye_prophylaxis: boolean;
  bcg_given: boolean;
  opv_0_given: boolean;
  arv_prophylaxis_baby: boolean;
  notes: string | null;
  created_at: string;
}

/** Create delivery record request. */
export interface DeliveryRecordCreate {
  anc_profile_id: string;
  encounter_id?: string | null;
  delivery_date: string;
  gestation_weeks?: number | null;
  mode_of_delivery: ModeOfDelivery;
  duration_of_labour_hours?: number | null;
  place_of_delivery?: string;
  maternal_outcome?: string;
  maternal_complications?: string | null;
  blood_loss_ml?: number | null;
  episiotomy?: boolean;
  tears?: string | null;
  baby_outcome: BabyOutcome;
  baby_sex?: string | null;
  birth_weight_grams?: number | null;
  apgar_1min?: number | null;
  apgar_5min?: number | null;
  apgar_10min?: number | null;
  resuscitation_needed?: boolean;
  skin_to_skin?: boolean;
  breastfed_within_1hr?: boolean;
  vitamin_k_given?: boolean;
  eye_prophylaxis?: boolean;
  bcg_given?: boolean;
  opv_0_given?: boolean;
  arv_prophylaxis_baby?: boolean;
  notes?: string | null;
}

/** Child health record response. */
export interface ChildRecordResponse {
  id: string;
  patient_id: string;
  mother_patient_id: string | null;
  delivery_record_id: string | null;
  child_number: string;
  date_of_birth: string;
  birth_weight_grams: number | null;
  sex: string;
  place_of_birth: string | null;
  birth_notification_number: string | null;
  hiv_exposed: boolean;
  pcr_test_date: string | null;
  pcr_result: string | null;
  feeding_method: FeedingMethod | null;
  status: ChildStatus;
  notes: string | null;
  created_at: string;
}

/** Child record list item. */
export interface ChildRecordListItem {
  id: string;
  child_number: string;
  patient_id: string;
  patient_name: string | null;
  date_of_birth: string;
  sex: string;
  age_months: number | null;
  hiv_exposed: boolean;
  immunization_count: number;
  next_immunization: string | null;
  status: ChildStatus;
  created_at: string;
}

/** Paginated child record list. */
export interface ChildRecordListResponse {
  items: ChildRecordListItem[];
  total: number;
}

/** Create child record request. */
export interface ChildRecordCreate {
  patient_id: string;
  mother_patient_id?: string | null;
  delivery_record_id?: string | null;
  date_of_birth: string;
  birth_weight_grams?: number | null;
  sex: string;
  place_of_birth?: string | null;
  birth_notification_number?: string | null;
  hiv_exposed?: boolean;
  feeding_method?: FeedingMethod | null;
  notes?: string | null;
}

/** Immunization response. */
export interface ImmunizationResponse {
  id: string;
  child_record_id: string;
  patient_id: string;
  administered_by: string;
  vaccine_code: string;
  vaccine_name: string;
  dose_number: number;
  date_given: string;
  age_at_dose_weeks: number | null;
  batch_number: string | null;
  site: string | null;
  route: string | null;
  scheduled_date: string | null;
  is_overdue: boolean;
  adverse_event: boolean;
  adverse_event_description: string | null;
  notes: string | null;
  created_at: string;
}

/** Create immunization request. */
export interface ImmunizationCreate {
  child_record_id: string;
  vaccine_code: string;
  vaccine_name: string;
  dose_number: number;
  date_given: string;
  age_at_dose_weeks?: number | null;
  batch_number?: string | null;
  site?: string | null;
  route?: string | null;
  adverse_event?: boolean;
  adverse_event_description?: string | null;
  notes?: string | null;
}

/** Update immunization request — only the fields being corrected. */
export interface ImmunizationUpdate {
  vaccine_code?: string;
  vaccine_name?: string;
  dose_number?: number;
  date_given?: string;
  batch_number?: string | null;
  site?: string | null;
  route?: string | null;
  adverse_event?: boolean;
  adverse_event_description?: string | null;
  notes?: string | null;
}

/** One routine dose on the national EPI schedule. */
export interface ImmunizationScheduleItem {
  vaccine_code: string;
  vaccine_name: string;
  due_age_weeks: number;
  route: string | null;
  site: string | null;
}

/** Full ANC profile detail with visits and delivery. */
export interface ANCProfileDetail {
  profile: ANCProfileResponse;
  visits: ANCVisitResponse[];
  delivery: DeliveryRecordResponse | null;
  patient_name: string | null;
  patient_mrn: string | null;
}

/** MCH department summary stats. */
export interface MCHSummary {
  active_anc_profiles: number;
  high_risk_pregnancies: number;
  deliveries_this_month: number;
  live_births_this_month: number;
  active_children: number;
  overdue_immunizations: number;
}
