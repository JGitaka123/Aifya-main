"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  WardBoardSummary,
  WardResponse,
  WardCreate,
  BedResponse,
  BedCreate,
  AdmissionListResponse,
  AdmissionResponse,
  AdmissionCreate,
  DischargeRequest,
  EmergencyVisitResponse,
  TransferToEmergencyRequest,
  NursingNoteResponse,
  NursingNoteCreate,
} from "@aifya/shared";

// ── Ward Board Summary ──────────────────────────────────────────────────────

/**
 * Hook for fetching IPD ward board summary.
 *
 * @returns Query result with ward board summary
 */
export function useWardBoardSummary() {
  return useOfflineQuery<WardBoardSummary>({
    queryKey: ["ipd", "summary"],
    queryFn: () => apiClient.get<WardBoardSummary>("/ipd/summary"),
    refetchInterval: 30_000,
  });
}

// ── Wards ───────────────────────────────────────────────────────────────────

/**
 * Hook for fetching all wards with bed occupancy.
 *
 * @returns Query result with ward list
 */
export function useWards() {
  return useOfflineQuery<WardResponse[]>({
    queryKey: ["ipd", "wards"],
    queryFn: () => apiClient.get<WardResponse[]>("/ipd/wards"),
    refetchInterval: 30_000,
  });
}

/**
 * Hook for creating a ward.
 *
 * @returns Mutation for ward creation
 */
export function useCreateWard() {
  const queryClient = useQueryClient();
  return useOfflineMutation<WardResponse, WardCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<WardResponse>("/ipd/wards", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
      },
    },
    { url: "/api/v1/ipd/wards", method: "POST" }
  );
}

// ── Beds ────────────────────────────────────────────────────────────────────

/**
 * Hook for fetching beds with optional filters.
 *
 * @param wardId - Optional ward filter
 * @param statusFilter - Optional status filter
 * @returns Query result with bed list
 */
export function useBeds(wardId?: string, statusFilter?: string) {
  const params: Record<string, string> = {};
  if (wardId) params["ward_id"] = wardId;
  if (statusFilter) params["status"] = statusFilter;

  return useOfflineQuery<BedResponse[]>({
    queryKey: ["ipd", "beds", wardId ?? "", statusFilter ?? ""],
    queryFn: () => apiClient.get<BedResponse[]>("/ipd/beds", params),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for creating a bed.
 *
 * @returns Mutation for bed creation
 */
export function useCreateBed() {
  const queryClient = useQueryClient();
  return useOfflineMutation<BedResponse, BedCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<BedResponse>("/ipd/beds", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
      },
    },
    { url: "/api/v1/ipd/beds", method: "POST" }
  );
}

// ── Admissions ──────────────────────────────────────────────────────────────

/**
 * Hook for fetching active admissions.
 *
 * @param statusFilter - Optional status filter
 * @param wardId - Optional ward filter
 * @returns Query result with admission list
 */
export function useAdmissions(statusFilter?: string, wardId?: string) {
  const params: Record<string, string> = {};
  if (statusFilter) params["status"] = statusFilter;
  if (wardId) params["ward_id"] = wardId;

  return useOfflineQuery<AdmissionListResponse>({
    queryKey: ["ipd", "admissions", statusFilter ?? "", wardId ?? ""],
    queryFn: () =>
      apiClient.get<AdmissionListResponse>("/ipd/admissions", params),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single admission.
 *
 * @param admissionId - Admission UUID
 * @returns Query result with admission detail
 */
export function useAdmissionDetail(admissionId: string) {
  return useOfflineQuery<AdmissionResponse>({
    queryKey: ["ipd", "admissions", admissionId],
    queryFn: () =>
      apiClient.get<AdmissionResponse>(`/ipd/admissions/${admissionId}`),
    enabled: !!admissionId,
  });
}

/**
 * Hook for admitting a patient.
 *
 * @returns Mutation for admission
 */
export function useAdmitPatient() {
  const queryClient = useQueryClient();
  return useOfflineMutation<AdmissionResponse, AdmissionCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<AdmissionResponse>(
          "/ipd/admissions",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: "/api/v1/ipd/admissions", method: "POST" }
  );
}

/**
 * Hook for discharging a patient.
 *
 * @returns Mutation for discharge
 */
export function useDischargePatient() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    AdmissionResponse,
    DischargeRequest & { admission_id: string }
  >(
    {
      mutationFn: ({ admission_id, ...data }) =>
        apiClient.post<AdmissionResponse>(
          `/ipd/admissions/${admission_id}/discharge`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    {
      url: ({ admission_id }) =>
        `/api/v1/ipd/admissions/${admission_id}/discharge`,
      method: "POST",
      body: ({ admission_id, ...data }) => {
        void admission_id;
        return data;
      },
    }
  );
}


/**
 * Hook for transferring an inpatient to the Emergency Room when their
 * condition worsens. Creates an ER visit and closes the IPD admission.
 *
 * @returns Mutation for the IPD to Emergency transfer
 */
export function useTransferToEmergency() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    EmergencyVisitResponse,
    TransferToEmergencyRequest & { admission_id: string }
  >(
    {
      mutationFn: ({ admission_id, ...data }) =>
        apiClient.post<EmergencyVisitResponse>(
          `/ipd/admissions/${admission_id}/transfer-to-emergency`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
        queryClient.invalidateQueries({ queryKey: ["emergency"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    {
      url: ({ admission_id }) =>
        `/api/v1/ipd/admissions/${admission_id}/transfer-to-emergency`,
      method: "POST",
      body: ({ admission_id, ...data }) => {
        void admission_id;
        return data;
      },
    }
  );
}

// ── Nursing Notes ───────────────────────────────────────────────────────────

/**
 * Hook for fetching nursing notes for an admission.
 *
 * @param admissionId - Admission UUID
 * @returns Query result with nursing notes
 */
export function useNursingNotes(admissionId: string) {
  return useOfflineQuery<NursingNoteResponse[]>({
    queryKey: ["ipd", "admissions", admissionId, "notes"],
    queryFn: () =>
      apiClient.get<NursingNoteResponse[]>(
        `/ipd/admissions/${admissionId}/notes`
      ),
    enabled: !!admissionId,
  });
}

/**
 * Hook for adding a nursing note.
 *
 * @returns Mutation for nursing note creation
 */
export function useAddNursingNote() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    NursingNoteResponse,
    NursingNoteCreate & { admission_id: string }
  >(
    {
      mutationFn: ({ admission_id, ...data }) =>
        apiClient.post<NursingNoteResponse>(
          `/ipd/admissions/${admission_id}/notes`,
          data,
          generateId()
        ),
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({
          queryKey: ["ipd", "admissions", variables.admission_id, "notes"],
        });
      },
    },
    {
      url: ({ admission_id }) =>
        `/api/v1/ipd/admissions/${admission_id}/notes`,
      method: "POST",
      body: ({ admission_id, ...data }) => {
        void admission_id;
        return data;
      },
    }
  );
}
