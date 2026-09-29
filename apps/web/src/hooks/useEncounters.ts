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
  DepartmentWorkload,
  ClinicalScope,
  ClinicalWorklist,
  EncounterRoute,
  EncounterRouteRequest,
  EncounterRouteResult,
  PointOfCareTest,
  PointOfCareTestCreate,
} from "@aifya/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Encounter hooks ──────────────────────────────────────────────────────

/**
 * Hook for fetching the OPD queue with offline support.
 *
 * @param statusFilter - Optional status filter
 * @param departmentId - Optional department, so a unit reads its own queue
 * @param stage - assessment (still with OPD) or consultation (ready for a
 *   doctor); omit for both
 * @returns Query result with queue data
 */
export function useOPDQueue(
  statusFilter?: string,
  departmentId?: string,
  stage?: string
) {
  const params: Record<string, string> = {};
  if (statusFilter) {
    params["status"] = statusFilter;
  }
  if (departmentId) {
    params["department_id"] = departmentId;
  }
  if (stage) {
    params["stage"] = stage;
  }

  return useOfflineQuery<QueueResponse>({
    queryKey: [
      "encounters",
      "queue",
      statusFilter ?? "",
      departmentId ?? "",
      stage ?? "",
    ],
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

/**
 * Hook for bringing one chosen patient into the consultation room.
 *
 * "Call next" takes the queue in order; this is the doctor picking the patient
 * they mean off their own workspace. The server applies the same gates, so a
 * row that is not assessed or not paid is refused with a reason. The encounter
 * is the mutation variable, so one hook serves the whole list.
 *
 * @returns Mutation taking an encounter UUID and claiming that patient
 */
export function useCallInPatient() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, string>(
    {
      mutationFn: (encounterId: string) =>
        apiClient.post<Encounter>(
          `/encounters/${encounterId}/call-in`,
          {},
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    {
      url: (encounterId: string) => `${API_URL}/encounters/${encounterId}/call-in`,
      method: "POST",
    }
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

/**
 * Hook for today's patient load per department.
 *
 * The clinical workspace is organised by department, so this is the number a
 * clinician works against: how many patients their unit has today. A clinician
 * sees their own unit; an administrator sees every unit at once.
 *
 * @param enabled - Skip the request until the caller may read clinical work
 * @returns Query result with one row per visible department
 */
export function useDepartmentLoad(enabled = true) {
  return useOfflineQuery<DepartmentWorkload[]>({
    queryKey: ["encounters", "department-load"],
    queryFn: () =>
      apiClient.get<DepartmentWorkload[]>("/encounters/department-load"),
    refetchInterval: 30_000,
    enabled,
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
 * @param options.enabled - Skip the request when the user lacks clinical.view
 * @param options.triaged - true: only patients the nurse has assessed; false:
 *   only those still with OPD; omit for both
 * @param options.search - Patient name, MRN or queue number to narrow by
 * @param options.departmentId - Narrow the facility view to one unit
 * @returns Query result with the clinician, counts and today's encounters
 */
export function useClinicalWorklist(
  scope?: ClinicalScope,
  status?: string,
  options?: {
    enabled?: boolean;
    triaged?: boolean;
    search?: string;
    departmentId?: string;
  },
) {
  const params: Record<string, string> = {};
  if (scope) {
    params["scope"] = scope;
  }
  if (status) {
    params["status"] = status;
  }
  if (options?.triaged !== undefined) {
    params["triaged"] = String(options.triaged);
  }
  const search = options?.search?.trim();
  if (search) {
    params["q"] = search;
  }
  if (options?.departmentId) {
    params["department_id"] = options.departmentId;
  }

  return useOfflineQuery<ClinicalWorklist>({
    queryKey: [
      "encounters",
      "worklist",
      scope ?? "",
      status ?? "",
      options?.triaged ?? "",
      search ?? "",
      options?.departmentId ?? "",
    ],
    queryFn: () =>
      apiClient.get<ClinicalWorklist>("/encounters/worklist", params),
    refetchInterval: 15_000,
    enabled: options?.enabled ?? true,
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
        // Recording vitals completes the OPD assessment server-side, so the
        // queues and the encounter banner must re-read the new stage.
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/vitals`, method: "POST" }
  );
}

// ── Diagnosis hooks ──────────────────────────────────────────────────────

/**
 * Hook for finishing the OPD assessment and releasing the patient to a doctor.
 *
 * Recording vitals already completes the assessment on the server; this is the
 * explicit hand-off for a visit that needed no measurements taken.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for completing the assessment
 */
export function useCompleteAssessment(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<Encounter, void>(
    {
      mutationFn: () =>
        apiClient.post<Encounter>(
          `/encounters/${encounterId}/assessment`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/assessment`, method: "POST" }
  );
}

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


// -- Consultation room: routing a patient to another unit ------------------

/**
 * Hook for fetching the internal routing trail of an encounter.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with the routings, newest first
 */
export function useEncounterRoutes(encounterId: string) {
  return useOfflineQuery<EncounterRoute[]>({
    queryKey: ["encounters", encounterId, "routes"],
    queryFn: () =>
      apiClient.get<EncounterRoute[]>(`/encounters/${encounterId}/routes`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for sending a patient from the consultation room to another unit.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for routing the patient
 */
export function useRouteEncounter(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<EncounterRouteResult, EncounterRouteRequest>(
    {
      mutationFn: (data: EncounterRouteRequest) =>
        apiClient.post<EncounterRouteResult>(
          `/encounters/${encounterId}/route`,
          data,
          generateId()
        ),
      onSuccess: () => {
        // The encounter moved unit and was re-queued, so the list pages and
        // the routing trail both need to be re-read.
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/route`, method: "POST" }
  );
}

// -- Consultation room: general (point-of-care) testing ---------------------

/**
 * Hook for fetching the general tests recorded in the room.
 *
 * @param encounterId - Encounter UUID
 * @returns Query result with the tests, newest first
 */
export function useEncounterTests(encounterId: string) {
  return useOfflineQuery<PointOfCareTest[]>({
    queryKey: ["encounters", encounterId, "tests"],
    queryFn: () =>
      apiClient.get<PointOfCareTest[]>(`/encounters/${encounterId}/tests`),
    enabled: !!encounterId,
  });
}

/**
 * Hook for recording a general test performed in the room.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation for recording the test
 */
export function useRecordPointOfCareTest(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<PointOfCareTest, PointOfCareTestCreate>(
    {
      mutationFn: (data: PointOfCareTestCreate) =>
        apiClient.post<PointOfCareTest>(
          `/encounters/${encounterId}/tests`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["encounters", encounterId, "tests"],
        });
      },
    },
    { url: `${API_URL}/encounters/${encounterId}/tests`, method: "POST" }
  );
}
