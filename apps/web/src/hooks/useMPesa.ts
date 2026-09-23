"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  STKPushApiRequest,
  STKPushResponse,
  STKRequestStatus,
  MPesaTransactionStatus,
  MPesaStatus,
} from "@aifya/shared";

// ── STK Push ────────────────────────────────────────────────────────────────

/**
 * Hook for initiating an M-Pesa STK Push payment.
 *
 * @returns Mutation for STK Push initiation
 */
export function useSTKPush() {
  return useOfflineMutation<STKPushResponse, STKPushApiRequest>(
    {
      mutationFn: (data: STKPushApiRequest) =>
        apiClient.post<STKPushResponse>(
          "/mpesa/stk-push",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/mpesa/stk-push", method: "POST" },
  );
}

// ── STK Status ──────────────────────────────────────────────────────────────

/**
 * Hook for querying STK Push transaction status.
 *
 * @param checkoutRequestId - Checkout request ID from STK Push
 * @param enabled - Whether to poll (set true after STK push)
 * @returns Query result with transaction status
 */
export function useSTKStatus(checkoutRequestId: string | null, enabled: boolean = false) {
  return useOfflineQuery<MPesaTransactionStatus>({
    queryKey: ["mpesa", "stk-status", checkoutRequestId],
    queryFn: () =>
      apiClient.get<MPesaTransactionStatus>(
        `/mpesa/stk-status/${checkoutRequestId}`,
      ),
    enabled: enabled && !!checkoutRequestId,
    refetchInterval: 5_000, // Poll every 5s while waiting
  });
}

// ── M-Pesa Status ───────────────────────────────────────────────────────────

/**
 * Hook for reading the local state of an STK Push the till started.
 *
 * This is the record that matters at the desk: it answers "has the money
 * reached the patient's bill?" rather than "what does Safaricom think?".
 * Polls every few seconds while the prompt is outstanding, then stops.
 *
 * @param checkoutRequestId - Checkout request ID from the STK Push response
 * @param enabled - Whether to poll (set true once a prompt has been sent)
 * @returns Query result with the local STK Push state
 */
export function useSTKRequestStatus(
  checkoutRequestId: string | null,
  enabled: boolean = false,
) {
  return useOfflineQuery<STKRequestStatus>({
    queryKey: ["mpesa", "stk-request", checkoutRequestId],
    queryFn: () =>
      apiClient.get<STKRequestStatus>(
        `/mpesa/stk-requests/${checkoutRequestId}`,
      ),
    enabled: enabled && !!checkoutRequestId,
    refetchInterval: (query) =>
      !query.state.data || query.state.data.status === "pending"
        ? 4_000
        : false,
  });
}

/**
 * Hook for asking Safaricom what happened and posting the money if it was
 * received. Covers a callback that was delayed or lost on a flaky link.
 *
 * @returns Mutation returning the reconciled local STK Push state
 */
export function useReconcileSTKPush() {
  return useOfflineMutation<
    STKRequestStatus,
    { checkout_request_id: string }
  >(
    {
      mutationFn: ({ checkout_request_id }) =>
        apiClient.post<STKRequestStatus>(
          `/mpesa/stk-requests/${checkout_request_id}/reconcile`,
          {},
          generateId(),
        ),
    },
    {
      url: ({ checkout_request_id }) =>
        `/api/v1/mpesa/stk-requests/${checkout_request_id}/reconcile`,
      method: "POST",
    },
  );
}

/**
 * Hook for checking M-Pesa configuration status.
 *
 * @returns Query result with M-Pesa config status
 */
export function useMPesaStatus() {
  return useOfflineQuery<MPesaStatus>({
    queryKey: ["mpesa", "status"],
    queryFn: () => apiClient.get<MPesaStatus>("/mpesa/status"),
    refetchInterval: 60_000,
  });
}
