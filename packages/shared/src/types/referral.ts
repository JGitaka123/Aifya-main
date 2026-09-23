/** Referral type */
export type ReferralType = "internal" | "external";

/** Referral direction */
export type ReferralDirection = "outgoing" | "incoming";

/** Referral urgency */
export type ReferralUrgency = "emergency" | "urgent" | "routine";

/** Referral status */
export type ReferralStatus = "draft" | "sent" | "received" | "accepted" | "declined" | "completed" | "cancelled";

/** Referral creation */
export interface ReferralCreate {
  patient_id: string;
  encounter_id?: string | null;
  emergency_visit_id?: string | null;
  referral_type?: ReferralType;
  direction?: ReferralDirection;
  /** Create straight as "sent" (dispatched) instead of the default "draft". */
  initial_status?: "draft" | "sent";
  referring_doctor_id?: string | null;
  referring_department_id?: string | null;
  referring_facility_name?: string | null;
  receiving_doctor_id?: string | null;
  receiving_department_id?: string | null;
  receiving_facility_id?: string | null;
  receiving_facility_name?: string | null;
  receiving_facility_mfl?: string | null;
  reason: string;
  clinical_notes?: string | null;
  diagnosis?: string | null;
  urgency?: ReferralUrgency;
  notes?: string | null;
}

/** Referral response */
export interface ReferralResponse {
  id: string;
  referral_number: string;
  patient_id: string;
  encounter_id: string | null;
  emergency_visit_id: string | null;
  referral_type: string;
  direction: string;
  referring_doctor_id: string | null;
  referring_department_id: string | null;
  referring_facility_name: string | null;
  receiving_doctor_id: string | null;
  receiving_department_id: string | null;
  receiving_facility_id: string | null;
  receiving_facility_name: string | null;
  receiving_facility_mfl: string | null;
  reason: string;
  clinical_notes: string | null;
  diagnosis: string | null;
  urgency: string;
  referral_date: string;
  status: string;
  response_date: string | null;
  response_notes: string | null;
  feedback: string | null;
  attachments: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

/** A facility in the register that a patient can be referred to. */
export interface FacilityLookupItem {
  id: string;
  name: string;
  mfl_code: string | null;
  facility_type: string;
  keph_level: string | null;
  county: string | null;
  sub_county: string | null;
}

/** Matches from the facility register for a referral destination. */
export interface FacilityLookupResponse {
  items: FacilityLookupItem[];
  total: number;
}

/** Referral list item */
export interface ReferralListItem {
  id: string;
  referral_number: string;
  patient_id: string;
  patient_name: string | null;
  emergency_visit_id?: string | null;
  referral_type: string;
  direction: string;
  reason: string;
  urgency: string;
  referring_facility_name: string | null;
  receiving_facility_name: string | null;
  referral_date: string;
  status: string;
}

/** Referral list response */
export interface ReferralListResponse {
  items: ReferralListItem[];
  total: number;
}

/** Referral status update */
export interface ReferralUpdateStatus {
  status: ReferralStatus;
  response_notes?: string | null;
  feedback?: string | null;
}

/** Referral summary */
export interface ReferralSummary {
  total_referrals: number;
  outgoing: number;
  incoming: number;
  pending: number;
  accepted: number;
  completed: number;
}
