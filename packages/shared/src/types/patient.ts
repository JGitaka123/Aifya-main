/** Patient record as returned by the API. */
export interface Patient {
  id: string;
  mrn: string;
  facility_id: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  date_of_birth: string;
  gender: "male" | "female" | "other";
  national_id: string | null;
  passport_number: string | null;
  phone_number: string;
  alternate_phone: string | null;
  email: string | null;
  county: string | null;
  sub_county: string | null;
  ward: string | null;
  village: string | null;
  postal_address: string | null;
  occupation: string | null;
  marital_status: "single" | "married" | "divorced" | "widowed" | null;
  next_of_kin_name: string | null;
  next_of_kin_phone: string | null;
  next_of_kin_relationship: string | null;
  insurance_provider: string | null;
  insurance_member_number: string | null;
  sha_number: string | null;
  blood_group: string | null;
  allergies: string[] | null;
  chronic_conditions: string[] | null;
  photo_url: string | null;
  created_at: string;
  updated_at: string;
}

/** Payload for creating a new patient. */
export interface PatientCreate {
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  date_of_birth: string;
  gender: "male" | "female" | "other";
  national_id?: string | null;
  passport_number?: string | null;
  phone_number: string;
  alternate_phone?: string | null;
  email?: string | null;
  county?: string | null;
  sub_county?: string | null;
  ward?: string | null;
  village?: string | null;
  postal_address?: string | null;
  occupation?: string | null;
  marital_status?: "single" | "married" | "divorced" | "widowed" | null;
  next_of_kin_name?: string | null;
  next_of_kin_phone?: string | null;
  next_of_kin_relationship?: string | null;
  insurance_provider?: string | null;
  insurance_member_number?: string | null;
  sha_number?: string | null;
  blood_group?: string | null;
  allergies?: string[] | null;
  chronic_conditions?: string[] | null;
}

/** Payload for updating an existing patient. All fields optional. */
export type PatientUpdate = Partial<PatientCreate>;

/** Paginated patient list response. */
export interface PatientListResponse {
  items: Patient[];
  total: number;
  page: number;
  page_size: number;
}
