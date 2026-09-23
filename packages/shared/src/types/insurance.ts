/** Insurance scheme type */
export type SchemeType = "sha" | "private" | "corporate" | "nhif_legacy";

/** Claim status */
export type ClaimStatus = "draft" | "submitted" | "processing" | "approved" | "partially_approved" | "rejected" | "paid";

/** Scheme creation */
export interface InsuranceSchemeCreate {
  name: string;
  scheme_type?: SchemeType;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  contract_start?: string | null;
  contract_end?: string | null;
  coverage_details?: Record<string, unknown> | null;
  rebate_percentage?: number | null;
  notes?: string | null;
}

/** Scheme response */
export interface InsuranceSchemeResponse {
  id: string;
  name: string;
  scheme_code: string;
  scheme_type: string;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  contract_start: string | null;
  contract_end: string | null;
  coverage_details: Record<string, unknown> | null;
  rebate_percentage: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

/** Scheme list response */
export interface InsuranceSchemeListResponse {
  items: InsuranceSchemeResponse[];
  total: number;
}

/** Claim creation */
export interface ClaimCreate {
  patient_id: string;
  scheme_id: string;
  invoice_id?: string | null;
  encounter_id?: string | null;
  member_number: string;
  claim_amount: number;
  claim_items?: Record<string, unknown> | null;
  diagnosis_codes?: Record<string, unknown> | null;
  notes?: string | null;
}

/** Claim response */
export interface ClaimResponse {
  id: string;
  claim_number: string;
  patient_id: string;
  scheme_id: string;
  invoice_id: string | null;
  encounter_id: string | null;
  member_number: string;
  claim_amount: number;
  approved_amount: number;
  paid_amount: number;
  status: string;
  claim_date: string;
  submitted_date: string | null;
  processed_date: string | null;
  paid_date: string | null;
  claim_items: Record<string, unknown> | null;
  diagnosis_codes: Record<string, unknown> | null;
  rejection_reason: string | null;
  sha_reference: string | null;
  notes: string | null;
  created_at: string;
}

/** Claim list item */
export interface ClaimListItem {
  id: string;
  claim_number: string;
  patient_id: string;
  patient_name: string | null;
  scheme_name: string | null;
  member_number: string;
  claim_amount: number;
  approved_amount: number;
  status: string;
  claim_date: string;
}

/** Claim list response */
export interface ClaimListResponse {
  items: ClaimListItem[];
  total: number;
}

/** Claim status update */
export interface ClaimStatusUpdate {
  status: ClaimStatus;
  approved_amount?: number | null;
  paid_amount?: number | null;
  rejection_reason?: string | null;
  sha_reference?: string | null;
}

/** Insurance summary */
export interface InsuranceSummary {
  total_claims: number;
  pending_claims: number;
  submitted_claims: number;
  approved_claims: number;
  rejected_claims: number;
  total_claim_value: number;
  active_schemes: number;
  preauth_pending: number;
}
