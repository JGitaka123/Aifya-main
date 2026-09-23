"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  Encounter,
  EncounterCreate,
  EncounterUpdate,
  QueueResponse,
  VitalSign,
  VitalSignCreate,
  Diagnosis,
  DiagnosisCreate,
  Prescription,
  PrescriptionCreate,
  PrescriptionWithInteractions,
  LabOrder,
  LabOrderCreate,
  ConsultationFeeQuote,
  ConsultationFeeUpdate,
  ConsultationPaymentRequest,
  ConsultationPaymentResult,
  DepartmentOption,
  ClinicalScope,
  ClinicalWorklist,
} from "@aifya/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Encounter hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching the OPD queue with offline support.
 *
 * @param statusFilter - Optional status filter
 * @returns Query result with queue data
 */
export function useOPDQueue(statusFilter?: string) {
  const params: Record<string, string> = {};
  if (statusFilter) {
    params["status"] = statusFilter;
  }

  return useOfflineQuery<QueueResponse>({
    queryKey: ["encounters", "queue", statusFilter ?? ""],
    queryFn: () => apiClient.get<QueueResponse>("/encounters/queue", params),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single encounter by ID.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with encounter data
 */
export function useEncounter(encounterId: string) {
  return useOfflineQuery<Encounter>({
    queryKey: ["encounters", encounterId],
    queryFn: () => apiClient.get<Encounter>(`/encounters/${encounterId}`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a new encounter with offline queue support.
 *
 * @returns Mutation for creating an encounter
 */
export function useCreateEncounter() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, EncounterCreate>(
    {
      mutationFn: (data: EncounterCreate) =>
        apiClient.post<Encounter>("/encounters", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters`, method: "POST" }
  );
}

/**
 * Hook for updating an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for updating the encounter
 */
export function useUpdateEncounter(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, EncounterUpdate>(
    {
      mutationFn: (data: EncounterUpdate) =>
        apiClient.patch<Encounter>(
          `/encounters/${encounterId}`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}`, method: "PATCH" }
  );
}

/**
 * Hook for calling the next patient in the OPD queue.
 *
 * @returns Mutation for calling next patient
 */
export function useCallNext() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, void>(
    {
      mutationFn: () =>
        apiClient.post<Encounter>(
          "/encounters/queue/call-next",
          {},
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/queue/call-next`, method: "POST" }
  );
}

// -- Department directory ---------------------------------------------------

/**
 * Hook for listing the facility's departments for front-desk routing.
 *
 * Returns an empty list when the facility has not configured departments yet,
 * so the caller can fall back to display-only labels.
 *
 * @returns Query result with department options
 */
export function useDepartments() {
  return useOfflineQuery<DepartmentOption[]>({
    queryKey: ["departments", "options"],
    queryFn: () => apiClient.get<DepartmentOption[]>("/encounters/departments"),
    staleTime: 5 * 60_000,
  });
}

// ---- Consultation fee taken at the reception desk -------------------------

/**
 * Hook for the consultation fee an encounter owes at reception.
 *
 * @param encounterId - Encounter UUID
 * @param enabled - Skip the request until the encounter exists
 * @returns Query result with the fee quote and payment state
 */
export function useConsultationFee(encounterId: string, enabled = true) {
  return useOfflineQuery<ConsultationFeeQuote>({
    queryKey: ["encounters", encounterId, "consultation-fee"],
    queryFn: () =>
      apiClient.get<ConsultationFeeQuote>(
        `/encounters/${encounterId}/consultation-fee`
      ),
    enabled: !!encounterId && enabled,
  });
}

/**
 * Hook for taking the consultation fee at the reception desk.
 *
 * The API is idempotent per generated key, so a retry after a dropped
 * response cannot charge the patient twice.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation returning the settled invoice and its receipt URL
 */
export function useCollectConsultationFee(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    ConsultationPaymentResult,
    ConsultationPaymentRequest
  >(
    {
      mutationFn: (data: ConsultationPaymentRequest) =>
        apiClient.post<ConsultationPaymentResult>(
          `/encounters/${encounterId}/consultation-payment`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "consultation-fee"],
        });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/consultation-payment`,
      method: "POST",
    }
  );
}

/**
 * Hook for correcting the consultation fee charged for a visit.
 *
 * Editing the fee re-prices the encounter's consultation invoice, so the money
 * collected, the patient's bill and the printed receipt agree.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation returning the re-priced fee quote
 */
export function useUpdateConsultationFee(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<ConsultationFeeQuote, ConsultationFeeUpdate>(
    {
      mutationFn: (data: ConsultationFeeUpdate) =>
        apiClient.patch<ConsultationFeeQuote>(
          `/encounters/${encounterId}/consultation-fee`,
          data
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "consultation-fee"],
        });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/consultation-fee`,
      method: "PATCH",
    }
  );
}

/**
 * Hook for the signed-in clinician's workspace.
 *
 * Returns the patients reception has routed to the clinician's scope today,
 * with a count per status. The counts always cover the whole scoped day, so
 * filtering the list never hides how much work is behind the filter.
 *
 * @param scope - mine, department or facility; server default when omitted
 * @param status - Optional single status to narrow the list
 * @returns Query result with the clinician, counts and today's encounters
 */
export function useClinicalWorklist(scope?: ClinicalScope, status?: string) {
  const params: Record<string, string> = {};
  if (scope) {
    params["scope"] = scope;
  }
  if (status) {
    params["status"] = status;
  }

  return useOfflineQuery<ClinicalWorklist>({
    queryKey: ["encounters", "worklist", scope ?? "", status ?? ""],
    queryFn: () =>
      apiClient.get<ClinicalWorklist>("/encounters/worklist", params),
    refetchInterval: 15_000,
  });
}

// ── Vitals hooks ─────────────────────────────────────────────────────────

/**
 * Hook for fetching vitals for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with vitals
 */
export function useEncounterVitals(encounterId: string) {
  return useOfflineQuery<VitalSign[]>({
    queryKey: ["encounters", encounterId, "vitals"],
    queryFn: () =>
      apiClient.get<VitalSign[]>(`/encounters/${encounterId}/vitals`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for recording vital signs.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for recording vitals
 */
export function useRecordVitals(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<VitalSign, VitalSignCreate>(
    {
      mutationFn: (data: VitalSignCreate) =>
        apiClient.post<VitalSign>(
          `/encounters/${encounterId}/vitals`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "vitals"],
        });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/vitals`, method: "POST" }
  );
}

// ── Diagnosis hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching diagnoses for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with diagnoses
 */
export function useEncounterDiagnoses(encounterId: string) {
  return useOfflineQuery<Diagnosis[]>({
    queryKey: ["encounters", encounterId, "diagnoses"],
    queryFn: () =>
      apiClient.get<Diagnosis[]>(`/encounters/${encounterId}/diagnoses`),
    enabled: !!encounterId,
  });
}

export interface Icd10CodeItem {
  code: string;
  description: string;
}

interface Icd10SearchResponse {
  items: Icd10CodeItem[];
}

/**
 * Hook for ICD-10 diagnosis code type-ahead search (D5).
 *
 * @param query - Search string (code fragment or description); ignored if < 2 chars
 * @returns Query result with matching ICD-10 codes
 */
export function useIcd10Search(query: string) {
  const enabled = query.trim().length >= 2;
  return useOfflineQuery<Icd10SearchResponse>({
    queryKey: ["icd10", "search", query],
    queryFn: () =>
      apiClient.get<Icd10SearchResponse>("/icd10/search", {
        q: query,
        limit: "15",
      }),
    enabled,
  });
}

/**
 * Hook for adding a diagnosis.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for adding diagnosis
 */
export function useAddDiagnosis(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Diagnosis, DiagnosisCreate>(
    {
      mutationFn: (data: DiagnosisCreate) =>
        apiClient.post<Diagnosis>(
          `/encounters/${encounterId}/diagnoses`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "diagnoses"],
        });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/diagnoses`, method: "POST" }
  );
}

// ── Prescription hooks ───────────────────────────────────────────────────

/**
 * Hook for fetching prescriptions for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with prescriptions
 */
export function useEncounterPrescriptions(encounterId: string) {
  return useOfflineQuery<Prescription[]>({
    queryKey: ["encounters", encounterId, "prescriptions"],
    queryFn: () =>
      apiClient.get<Prescription[]>(
        `/encounters/${encounterId}/prescriptions`
      ),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a prescription with interaction checking.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for creating prescription
 */
export function useCreatePrescription(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<PrescriptionWithInteractions, PrescriptionCreate>(
    {
      mutationFn: (data: PrescriptionCreate) =>
        apiClient.post<PrescriptionWithInteractions>(
          `/encounters/${encounterId}/prescriptions`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "prescriptions"],
        });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/prescriptions`,
      method: "POST",
    }
  );
}

// ── Lab Order hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching lab orders for an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with lab orders
 */
export function useEncounterLabOrders(encounterId: string) {
  return useOfflineQuery<LabOrder[]>({
    queryKey: ["encounters", encounterId, "lab-orders"],
    queryFn: () =>
      apiClient.get<LabOrder[]>(`/encounters/${encounterId}/lab-orders`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for creating a lab order.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for creating lab order
 */
export function useCreateLabOrder(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabOrder, LabOrderCreate>(
    {
      mutationFn: (data: LabOrderCreate) =>
        apiClient.post<LabOrder>(
          `/encounters/${encounterId}/lab-orders`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "lab-orders"],
        });
      },
    },
    {
      url: `${API_URL}/encounters/${encounterId}/lab-orders`,
      method: "POST",
    }
  );
}
