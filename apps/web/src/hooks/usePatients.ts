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
 * @returns Query result with patient list
 */
export function usePatientSearch(
  query?: string,
  page: number = 1,
  pageSize: number = 20
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
