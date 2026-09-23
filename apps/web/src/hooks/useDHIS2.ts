"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  MOHFormInfo,
  MOHReport,
  MOHReportRequest,
  MOHAllReportsResponse,
  DHIS2ConnectionStatus,
} from "@aifya/shared";

// ── MOH Forms List ──────────────────────────────────────────────────────────

/**
 * Hook for fetching available MOH form types.
 *
 * @returns Query result with MOH form metadata list
 */
export function useMOHForms() {
  return useOfflineQuery<MOHFormInfo[]>({
    queryKey: ["dhis2", "moh-forms"],
    queryFn: () => apiClient.get<MOHFormInfo[]>("/dhis2/moh/forms"),
    refetchInterval: 300_000,
  });
}

// ── Generate Single MOH Report ──────────────────────────────────────────────

/**
 * Hook for generating a specific MOH report.
 *
 * @returns Mutation for MOH report generation
 */
export function useGenerateMOHReport() {
  return useOfflineMutation<MOHReport, MOHReportRequest>(
    {
      mutationFn: (data: MOHReportRequest) =>
        apiClient.post<MOHReport>(
          "/dhis2/moh/generate",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/dhis2/moh/generate", method: "POST" },
  );
}

// ── Generate All MOH Reports ────────────────────────────────────────────────

/**
 * Hook for generating all MOH reports for a period.
 *
 * @param dateFrom - Report period start (YYYY-MM-DD)
 * @param dateTo - Report period end (YYYY-MM-DD)
 * @param enabled - Whether to auto-fetch
 * @returns Query result with all MOH reports
 */
export function useAllMOHReports(dateFrom: string, dateTo: string, enabled: boolean = false) {
  return useOfflineQuery<MOHAllReportsResponse>({
    queryKey: ["dhis2", "moh-all", dateFrom, dateTo],
    queryFn: () =>
      apiClient.get<MOHAllReportsResponse>(
        `/dhis2/moh/generate-all?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
    enabled,
  });
}

// ── DHIS2 Connection Status ─────────────────────────────────────────────────

/**
 * Hook for checking DHIS2 connection status.
 *
 * @returns Query result with DHIS2 connection status
 */
export function useDHIS2Status() {
  return useOfflineQuery<DHIS2ConnectionStatus>({
    queryKey: ["dhis2", "status"],
    queryFn: () =>
      apiClient.get<DHIS2ConnectionStatus>("/dhis2/dhis2/status"),
    refetchInterval: 60_000,
  });
}
