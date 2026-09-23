"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  MCHSummary,
  ANCProfileListResponse,
  ANCProfileDetail,
  ANCProfileResponse,
  ANCProfileCreate,
  ANCVisitResponse,
  ANCVisitCreate,
  DeliveryRecordResponse,
  DeliveryRecordCreate,
  ChildRecordListResponse,
  ChildRecordResponse,
  ChildRecordCreate,
  ImmunizationResponse,
  ImmunizationCreate,
  ImmunizationScheduleItem,
  ImmunizationUpdate,
} from "@aifya/shared";

// ── Summary ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching MCH department summary.
 *
 * @returns Query result with MCH summary stats
 */
export function useMCHSummary() {
  return useOfflineQuery<MCHSummary>({
    queryKey: ["mch", "summary"],
    queryFn: () => apiClient.get<MCHSummary>("/mch/summary"),
    refetchInterval: 30_000,
  });
}

// ── ANC Profiles ───────────────────────────────────────────────────────────

/**
 * Hook for fetching ANC profiles.
 *
 * @param status - Optional status filter
 * @returns Query result with ANC profile list
 */
export function useANCProfiles(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<ANCProfileListResponse>({
    queryKey: ["mch", "anc", status],
    queryFn: () =>
      apiClient.get<ANCProfileListResponse>(`/mch/anc${params}`),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single ANC profile with visits and delivery.
 *
 * @param profileId - ANC profile UUID
 * @returns Query result with full ANC profile detail
 */
export function useANCProfileDetail(profileId: string) {
  return useOfflineQuery<ANCProfileDetail>({
    queryKey: ["mch", "anc", profileId],
    queryFn: () =>
      apiClient.get<ANCProfileDetail>(`/mch/anc/${profileId}`),
    enabled: !!profileId,
  });
}

/**
 * Hook for creating an ANC profile.
 *
 * @returns Mutation for ANC profile creation
 */
export function useCreateANCProfile() {
  const queryClient = useQueryClient();
  return useOfflineMutation<ANCProfileResponse, ANCProfileCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ANCProfileResponse>("/mch/anc", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    { url: "/api/v1/mch/anc", method: "POST" }
  );
}

// ── ANC Visits ─────────────────────────────────────────────────────────────

/**
 * Hook for adding an ANC visit.
 *
 * @returns Mutation for ANC visit creation
 */
export function useAddANCVisit() {
  const queryClient = useQueryClient();
  return useOfflineMutation<ANCVisitResponse, ANCVisitCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ANCVisitResponse>(
          "/mch/anc/visits",
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    { url: "/api/v1/mch/anc/visits", method: "POST" }
  );
}

// ── Delivery ───────────────────────────────────────────────────────────────

/**
 * Hook for recording a delivery.
 *
 * @returns Mutation for delivery record creation
 */
export function useRecordDelivery() {
  const queryClient = useQueryClient();
  return useOfflineMutation<DeliveryRecordResponse, DeliveryRecordCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<DeliveryRecordResponse>(
          "/mch/delivery",
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    { url: "/api/v1/mch/delivery", method: "POST" }
  );
}

// ── Child Records ──────────────────────────────────────────────────────────

/**
 * Hook for fetching child health records.
 *
 * @returns Query result with child record list
 */
export function useChildRecords() {
  return useOfflineQuery<ChildRecordListResponse>({
    queryKey: ["mch", "children"],
    queryFn: () =>
      apiClient.get<ChildRecordListResponse>("/mch/children"),
    refetchInterval: 30_000,
  });
}

/**
 * Hook for creating a child health record.
 *
 * @returns Mutation for child record creation
 */
export function useCreateChildRecord() {
  const queryClient = useQueryClient();
  return useOfflineMutation<ChildRecordResponse, ChildRecordCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ChildRecordResponse>(
          "/mch/children",
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    { url: "/api/v1/mch/children", method: "POST" }
  );
}

// ── Immunizations ──────────────────────────────────────────────────────────

/**
 * Hook for fetching immunizations for a child.
 *
 * @param childId - Child record UUID
 * @returns Query result with immunization list
 */
export function useImmunizations(childId: string) {
  return useOfflineQuery<ImmunizationResponse[]>({
    queryKey: ["mch", "immunizations", childId],
    queryFn: () =>
      apiClient.get<ImmunizationResponse[]>(
        `/mch/children/${childId}/immunizations`
      ),
    enabled: !!childId,
  });
}

/**
 * Hook for fetching the national EPI routine immunization schedule.
 * The schedule is static, so it is cached indefinitely.
 *
 * @returns Query result with scheduled vaccine doses
 */
export function useImmunizationSchedule() {
  return useOfflineQuery<ImmunizationScheduleItem[]>({
    queryKey: ["mch", "immunization-schedule"],
    queryFn: () =>
      apiClient.get<ImmunizationScheduleItem[]>("/mch/immunization-schedule"),
    staleTime: Infinity,
  });
}

/**
 * Hook for recording an immunization.
 *
 * @returns Mutation for immunization recording
 */
export function useRecordImmunization() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImmunizationResponse,
    ImmunizationCreate & { childId: string }
  >(
    {
      mutationFn: ({ childId, ...data }) =>
        apiClient.post<ImmunizationResponse>(
          `/mch/children/${childId}/immunizations`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    {
      url: ({ childId }) =>
        `/api/v1/mch/children/${childId}/immunizations`,
      method: "POST",
      body: ({ childId, ...data }) => {
        void childId;
        return data;
      },
    }
  );
}

/**
 * Hook for correcting a dose that was recorded wrong.
 *
 * @returns Mutation for updating an immunization record
 */
export function useUpdateImmunization() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImmunizationResponse,
    ImmunizationUpdate & { immunizationId: string }
  >(
    {
      mutationFn: ({ immunizationId, ...data }) =>
        apiClient.patch<ImmunizationResponse>(
          `/mch/immunizations/${immunizationId}`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    {
      url: ({ immunizationId }) => `/api/v1/mch/immunizations/${immunizationId}`,
      method: "PATCH",
      body: ({ immunizationId, ...data }) => {
        void immunizationId;
        return data;
      },
    }
  );
}

/**
 * Hook for removing a dose recorded in error (soft delete on the API).
 *
 * @returns Mutation for deleting an immunization record
 */
export function useDeleteImmunization() {
  const queryClient = useQueryClient();
  return useOfflineMutation<void, { immunizationId: string }>(
    {
      mutationFn: ({ immunizationId }) =>
        apiClient.delete<void>(`/mch/immunizations/${immunizationId}`),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["mch"] });
      },
    },
    {
      url: ({ immunizationId }) => `/api/v1/mch/immunizations/${immunizationId}`,
      method: "DELETE",
      body: () => ({}),
    }
  );
}
