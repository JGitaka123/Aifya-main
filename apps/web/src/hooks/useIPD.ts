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
  AdmissionOrderListResponse,
  AdmissionOrderResponse,
  AdmissionOrderCreate,
  AdmissionOrderAccept,
  AdmissionOrderDecision,
  AdmissionOrderAdmit,
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

// ── Admission Orders ────────────────────────────────────────────────────────
//
// The consultation -> IPD bridge. Raising an order never admits anyone; the
// admission desk accepts it and only a ward + bed assignment creates the
// inpatient record.

/**
 * Hook for the admission-order queue.
 *
 * @param statusFilter - Exact status, or "open" for everything still workable
 * @param encounterId - Optional encounter filter (the encounter page uses this)
 * @param patientId - Optional patient filter
 * @returns Query result with admission orders
 */
export function useAdmissionOrders(
  statusFilter?: string,
  encounterId?: string,
  patientId?: string
) {
  const params: Record<string, string> = {};
  if (statusFilter) params["status"] = statusFilter;
  if (encounterId) params["encounter_id"] = encounterId;
  if (patientId) params["patient_id"] = patientId;

  return useOfflineQuery<AdmissionOrderListResponse>({
    queryKey: [
      "ipd",
      "admission-orders",
      statusFilter ?? "",
      encounterId ?? "",
      patientId ?? "",
    ],
    queryFn: () =>
      apiClient.get<AdmissionOrderListResponse>(
        "/ipd/admission-orders",
        params
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for raising an admission order from a consultation.
 *
 * @returns Mutation for admission-order creation
 */
export function useCreateAdmissionOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<AdmissionOrderResponse, AdmissionOrderCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<AdmissionOrderResponse>(
          "/ipd/admission-orders",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd", "admission-orders"] });
      },
    },
    { url: "/api/v1/ipd/admission-orders", method: "POST" }
  );
}

/**
 * Hook for accepting an admission order at the admission desk.
 *
 * @returns Mutation for accepting an order
 */
export function useAcceptAdmissionOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    AdmissionOrderResponse,
    AdmissionOrderAccept & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<AdmissionOrderResponse>(
          `/ipd/admission-orders/${orderId}/accept`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd", "admission-orders"] });
      },
    },
    {
      url: ({ orderId }) => `/api/v1/ipd/admission-orders/${orderId}/accept`,
      method: "POST",
    }
  );
}

/**
 * Hook for declining an admission order.
 *
 * @returns Mutation for declining an order
 */
export function useDeclineAdmissionOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    AdmissionOrderResponse,
    AdmissionOrderDecision & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<AdmissionOrderResponse>(
          `/ipd/admission-orders/${orderId}/decline`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd", "admission-orders"] });
      },
    },
    {
      url: ({ orderId }) => `/api/v1/ipd/admission-orders/${orderId}/decline`,
      method: "POST",
    }
  );
}

/**
 * Hook for cancelling an admission order before it is fulfilled.
 *
 * @returns Mutation for cancelling an order
 */
export function useCancelAdmissionOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    AdmissionOrderResponse,
    AdmissionOrderDecision & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<AdmissionOrderResponse>(
          `/ipd/admission-orders/${orderId}/cancel`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd", "admission-orders"] });
      },
    },
    {
      url: ({ orderId }) => `/api/v1/ipd/admission-orders/${orderId}/cancel`,
      method: "POST",
    }
  );
}

/**
 * Hook for assigning a ward and bed to an accepted order, creating the IPD
 * admission.
 *
 * @returns Mutation for fulfilling an order
 */
export function useAdmitFromOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    AdmissionResponse,
    AdmissionOrderAdmit & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<AdmissionResponse>(
          `/ipd/admission-orders/${orderId}/admit`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["ipd"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    {
      url: ({ orderId }) => `/api/v1/ipd/admission-orders/${orderId}/admit`,
      method: "POST",
    }
  );
}
