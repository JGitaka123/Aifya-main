"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type { Patient, PatientListResponse, PatientCreate } from "@aifya/shared";
import { generateId } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export interface DuplicateCheckRequest {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone_number?: string | null;
  national_id?: string | null;
  passport_number?: string | null;
}

export interface DuplicateMatch {
  patient: Patient;
  match_reasons: string[];
}

export interface DuplicateCheckResponse {
  has_duplicates: boolean;
  matches: DuplicateMatch[];
}

/**
 * Hook to check for likely-duplicate patients before registering (D7).
 * Online-only (needs a live server look-up); if the request fails — e.g.
 * offline — the caller should fall through to registration rather than block.
 *
 * @returns Mutation returning possible duplicates
 */
export function useCheckDuplicates() {
  return useMutation<DuplicateCheckResponse, Error, DuplicateCheckRequest>({
    mutationFn: (data: DuplicateCheckRequest) =>
      apiClient.post<DuplicateCheckResponse>("/patients/check-duplicates", data),
  });
}

/**
 * Hook for searching and listing patients with offline support.
 *
 * @param query - Search string
 * @param page - Page number
 * @param pageSize - Results per page
 * @param options - Optional query controls, e.g. run only once a term is typed
 * @returns Query result with patient list
 */
export function usePatientSearch(
  query?: string,
  page: number = 1,
  pageSize: number = 20,
  options?: { enabled?: boolean }
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (query) {
    params["q"] = query;
  }

  return useOfflineQuery<PatientListResponse>({
    queryKey: ["patients", "search", query ?? "", page, pageSize],
    queryFn: () => apiClient.get<PatientListResponse>("/patients", params),
    enabled: options?.enabled ?? true,
  });
}

/**
 * Hook for fetching a single patient by ID with offline support.
 *
 * @param patientId - Patient UUID
 * @returns Query result with patient data
 */
export function usePatient(patientId: string) {
  return useOfflineQuery<Patient>({
    queryKey: ["patients", patientId],
    queryFn: () => apiClient.get<Patient>(`/patients/${patientId}`),
    enabled: !!patientId,
  });
}

export interface PatientHistoryDiagnosis {
  icd10_code: string;
  icd10_description: string;
  diagnosis_type: string;
  clinical_status: string;
  is_chronic: boolean;
}

export interface PatientHistoryPrescription {
  drug_name: string;
  dosage: string;
  frequency: string;
  status: string;
}

export interface PatientHistoryVisit {
  encounter_id: string;
  encounter_date: string;
  encounter_type: string;
  status: string;
  department_name: string | null;
  attending_doctor_name: string | null;
  chief_complaint: string | null;
  disposition: string | null;
  diagnoses: PatientHistoryDiagnosis[];
  prescriptions: PatientHistoryPrescription[];
}

export interface PatientHistory {
  patient_id: string;
  mrn: string;
  full_name: string;
  date_of_birth: string;
  gender: string;
  age_years: number | null;
  blood_group: string | null;
  allergies: string[];
  chronic_conditions: string[];
  visit_count: number;
  last_visit_date: string | null;
  visits: PatientHistoryVisit[];
}

/**
 * Hook for a patient's clinical history at the point of care.
 *
 * Returns the safety-critical patient-level fields (allergies, chronic
 * conditions, blood group) plus previous visits with their diagnoses and
 * prescriptions, so a clinician who has just been handed a redirected
 * patient can see prior care without leaving the consultation screen.
 *
 * @param patientId - Patient UUID
 * @param excludeEncounterId - Encounter to omit (the visit being worked on)
 * @returns Query result with the patient's clinical history
 */
export function usePatientHistory(
  patientId: string,
  excludeEncounterId?: string
) {
  const params: Record<string, string> = { limit: "10" };
  if (excludeEncounterId) {
    params["exclude_encounter_id"] = excludeEncounterId;
  }

  return useOfflineQuery<PatientHistory>({
    queryKey: ["patients", patientId, "history", excludeEncounterId ?? ""],
    queryFn: () =>
      apiClient.get<PatientHistory>(`/patients/${patientId}/history`, params),
    enabled: !!patientId,
  });
}

/**
 * Hook for registering a new patient with offline queue support.
 *
 * @returns Mutation for creating a patient
 */
export function useRegisterPatient() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Patient, PatientCreate>(
    {
      mutationFn: (data: PatientCreate) =>
        apiClient.post<Patient>("/patients", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["patients"] });
      },
    },
    { url: `${API_URL}/patients`, method: "POST" }
  );
}
