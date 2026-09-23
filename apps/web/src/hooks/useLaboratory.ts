"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  LabWorklistResponse,
  LabOrderWithResults,
  LabOrderDetail,
  LabResultDetail,
  LabResultEntry,
  LabResultVerify,
  CriticalNotifyRequest,
  SpecimenCollectRequest,
} from "@aifya/shared";

// ── Worklist ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching the lab worklist with offline support.
 * Auto-refreshes every 15 seconds for real-time updates.
 *
 * @param statusFilter - Optional status filter
 * @returns Query result with worklist data
 */
export function useLabWorklist(statusFilter?: string) {
  const params: Record<string, string> = {};
  if (statusFilter) {
    params["status"] = statusFilter;
  }

  return useOfflineQuery<LabWorklistResponse>({
    queryKey: ["laboratory", "worklist", statusFilter ?? ""],
    queryFn: () =>
      apiClient.get<LabWorklistResponse>("/laboratory/worklist", params),
    refetchInterval: 15_000,
  });
}

// ── Test Catalog (D6) ───────────────────────────────────────────────────────

export interface LabCatalogItem {
  id: string;
  test_code: string;
  test_name: string;
  specimen_type: string | null;
  panel_name: string | null;
  price_cents: number;
  reference_range: string | null;
}

interface LabCatalogResponse {
  items: LabCatalogItem[];
  total: number;
}

/**
 * Hook for lab test catalog type-ahead search (D6). Ordering pulls the
 * canonical code, name, and managed price from the catalog instead of
 * hand-keying them.
 *
 * @param query - Search string (test code or name); ignored if < 2 chars
 * @returns Query result with matching catalog tests
 */
export function useLabCatalogSearch(query: string) {
  const enabled = query.trim().length >= 2;
  const params: Record<string, string> = enabled ? { q: query } : {};
  return useOfflineQuery<LabCatalogResponse>({
    queryKey: ["laboratory", "catalog", query],
    queryFn: () =>
      apiClient.get<LabCatalogResponse>("/laboratory/catalog", params),
    enabled,
  });
}

// ── Order Detail ────────────────────────────────────────────────────────────

/**
 * Hook for fetching a lab order with all results.
 *
 * @param orderId - LabOrder UUID
 * @returns Query result with order detail
 */
export function useLabOrderDetail(orderId: string) {
  return useOfflineQuery<LabOrderWithResults>({
    queryKey: ["laboratory", "orders", orderId],
    queryFn: () =>
      apiClient.get<LabOrderWithResults>(`/laboratory/orders/${orderId}`),
    enabled: !!orderId,
  });
}

// ── Specimen Collection ─────────────────────────────────────────────────────

/**
 * Hook for recording specimen collection.
 *
 * @returns Mutation for specimen collection
 */
export function useCollectSpecimen() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabOrderDetail, SpecimenCollectRequest & { order_id: string }>(
    {
      mutationFn: ({ order_id, ...data }) =>
        apiClient.post<LabOrderDetail>(
          `/laboratory/orders/${order_id}/collect`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    {
      url: ({ order_id }) =>
        `/api/v1/laboratory/orders/${order_id}/collect`,
      method: "POST",
      body: ({ order_id, ...data }) => {
        void order_id;
        return data;
      },
    }
  );
}

// ── Result Entry ────────────────────────────────────────────────────────────

/**
 * Hook for entering a lab result.
 *
 * @returns Mutation for result entry
 */
export function useEnterResult() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, LabResultEntry & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/enter`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    {
      url: ({ result_id }) =>
        `/api/v1/laboratory/results/${result_id}/enter`,
      method: "POST",
      body: ({ result_id, ...data }) => {
        void result_id;
        return data;
      },
    }
  );
}

// ── Result Verification ─────────────────────────────────────────────────────

/**
 * Hook for verifying (approving) a lab result.
 *
 * @returns Mutation for result verification
 */
export function useVerifyResult() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, LabResultVerify & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/verify`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    {
      url: ({ result_id }) =>
        `/api/v1/laboratory/results/${result_id}/verify`,
      method: "POST",
      body: ({ result_id, ...data }) => {
        void result_id;
        return data;
      },
    }
  );
}

// ── Critical Notification ───────────────────────────────────────────────────

/**
 * Hook for recording critical value notification.
 *
 * @returns Mutation for critical notification
 */
export function useNotifyCritical() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, CriticalNotifyRequest & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/notify-critical`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    {
      url: ({ result_id }) =>
        `/api/v1/laboratory/results/${result_id}/notify-critical`,
      method: "POST",
      body: ({ result_id, ...data }) => {
        void result_id;
        return data;
      },
    }
  );
}
