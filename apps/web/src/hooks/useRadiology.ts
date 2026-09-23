"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  RadiologySummary,
  ImagingWorklistResponse,
  ImagingOrderDetail,
  ImagingOrderResponse,
  ImagingOrderCreate,
  ImagingScheduleRequest,
  ImagingPerformRequest,
  ImagingResultResponse,
  ImagingResultCreate,
  ImagingResultVerify,
  CriticalImagingNotifyRequest,
} from "@aifya/shared";

// ── Summary ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching radiology department summary.
 *
 * @returns Query result with radiology summary stats
 */
export function useRadiologySummary() {
  return useOfflineQuery<RadiologySummary>({
    queryKey: ["radiology", "summary"],
    queryFn: () => apiClient.get<RadiologySummary>("/radiology/summary"),
    refetchInterval: 30_000,
  });
}

// ── Worklist ───────────────────────────────────────────────────────────────

/**
 * Hook for fetching the radiology worklist.
 *
 * @param status - Optional status filter
 * @param modality - Optional modality filter
 * @returns Query result with imaging worklist
 */
export function useImagingWorklist(status?: string, modality?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (modality) params.set("modality", modality);
  const qs = params.toString();

  return useOfflineQuery<ImagingWorklistResponse>({
    queryKey: ["radiology", "worklist", status, modality],
    queryFn: () =>
      apiClient.get<ImagingWorklistResponse>(
        `/radiology/worklist${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

// ── Order Detail ───────────────────────────────────────────────────────────

/**
 * Hook for fetching a single imaging order with result.
 *
 * @param orderId - Imaging order UUID
 * @returns Query result with full order detail
 */
export function useImagingOrderDetail(orderId: string) {
  return useOfflineQuery<ImagingOrderDetail>({
    queryKey: ["radiology", "order", orderId],
    queryFn: () =>
      apiClient.get<ImagingOrderDetail>(`/radiology/orders/${orderId}`),
    enabled: !!orderId,
  });
}

// ── Create Order ───────────────────────────────────────────────────────────

/**
 * Hook for creating an imaging order.
 *
 * @returns Mutation for imaging order creation
 */
export function useCreateImagingOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<ImagingOrderResponse, ImagingOrderCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ImagingOrderResponse>(
          "/radiology/orders",
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    { url: "/api/v1/radiology/orders", method: "POST" }
  );
}

// ── Schedule Order ─────────────────────────────────────────────────────────

/**
 * Hook for scheduling an imaging study.
 *
 * @returns Mutation for scheduling
 */
export function useScheduleOrder() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImagingOrderResponse,
    ImagingScheduleRequest & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<ImagingOrderResponse>(
          `/radiology/orders/${orderId}/schedule`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    {
      url: ({ orderId }) =>
        `/api/v1/radiology/orders/${orderId}/schedule`,
      method: "POST",
      body: ({ orderId, ...data }) => {
        void orderId;
        return data;
      },
    }
  );
}

// ── Perform Study ──────────────────────────────────────────────────────────

/**
 * Hook for marking an imaging study as performed.
 *
 * @returns Mutation for performing study
 */
export function usePerformStudy() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImagingOrderResponse,
    ImagingPerformRequest & { orderId: string }
  >(
    {
      mutationFn: ({ orderId, ...data }) =>
        apiClient.post<ImagingOrderResponse>(
          `/radiology/orders/${orderId}/perform`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    {
      url: ({ orderId }) =>
        `/api/v1/radiology/orders/${orderId}/perform`,
      method: "POST",
      body: ({ orderId, ...data }) => {
        void orderId;
        return data;
      },
    }
  );
}

// ── Enter Report ───────────────────────────────────────────────────────────

/**
 * Hook for entering a radiology report.
 *
 * @returns Mutation for report entry
 */
export function useEnterReport() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImagingResultResponse,
    ImagingResultCreate & { resultId: string }
  >(
    {
      mutationFn: ({ resultId, ...data }) =>
        apiClient.post<ImagingResultResponse>(
          `/radiology/results/${resultId}/report`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    {
      url: ({ resultId }) =>
        `/api/v1/radiology/results/${resultId}/report`,
      method: "POST",
      body: ({ resultId, ...data }) => {
        void resultId;
        return data;
      },
    }
  );
}

// ── Verify Report ──────────────────────────────────────────────────────────

/**
 * Hook for verifying (finalising) a radiology report.
 *
 * @returns Mutation for report verification
 */
export function useVerifyReport() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImagingResultResponse,
    ImagingResultVerify & { resultId: string }
  >(
    {
      mutationFn: ({ resultId, ...data }) =>
        apiClient.post<ImagingResultResponse>(
          `/radiology/results/${resultId}/verify`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    {
      url: ({ resultId }) =>
        `/api/v1/radiology/results/${resultId}/verify`,
      method: "POST",
      body: ({ resultId, ...data }) => {
        void resultId;
        return data;
      },
    }
  );
}

// ── Critical Finding Notification ──────────────────────────────────────────

/**
 * Hook for recording critical imaging finding notification.
 *
 * @returns Mutation for critical notification
 */
export function useNotifyCriticalImaging() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    ImagingResultResponse,
    CriticalImagingNotifyRequest & { resultId: string }
  >(
    {
      mutationFn: ({ resultId, ...data }) =>
        apiClient.post<ImagingResultResponse>(
          `/radiology/results/${resultId}/notify-critical`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["radiology"] });
      },
    },
    {
      url: ({ resultId }) =>
        `/api/v1/radiology/results/${resultId}/notify-critical`,
      method: "POST",
      body: ({ resultId, ...data }) => {
        void resultId;
        return data;
      },
    }
  );
}
