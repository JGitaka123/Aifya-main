"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import type {
  AnonymizedFacilityReport,
  DiseaseSurveillanceEntry,
  OutbreakAlert,
} from "@aifya/shared";

// ── Facility Report ─────────────────────────────────────────────────────────

/**
 * Hook for fetching anonymized facility report.
 *
 * @param dateFrom - Period start (YYYY-MM-DD)
 * @param dateTo - Period end (YYYY-MM-DD)
 * @param enabled - Whether to fetch
 * @returns Query result with anonymized facility data
 */
export function useFacilityReport(dateFrom: string, dateTo: string, enabled: boolean = true) {
  return useOfflineQuery<AnonymizedFacilityReport>({
    queryKey: ["federated", "facility-report", dateFrom, dateTo],
    queryFn: () =>
      apiClient.get<AnonymizedFacilityReport>(
        `/federated/facility-report?date_from=${dateFrom}&date_to=${dateTo}`,
      ),
    enabled,
    refetchInterval: 120_000,
  });
}

// ── Disease Surveillance ────────────────────────────────────────────────────

/**
 * Hook for fetching disease surveillance data.
 *
 * @param dateFrom - Optional period start
 * @param dateTo - Optional period end
 * @returns Query result with surveillance entries
 */
export function useDiseaseSurveillance(dateFrom?: string, dateTo?: string) {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();

  return useOfflineQuery<DiseaseSurveillanceEntry[]>({
    queryKey: ["federated", "surveillance", dateFrom, dateTo],
    queryFn: () =>
      apiClient.get<DiseaseSurveillanceEntry[]>(
        `/federated/surveillance${qs ? `?${qs}` : ""}`,
      ),
    refetchInterval: 60_000,
  });
}

// ── Outbreak Alerts ─────────────────────────────────────────────────────────

/**
 * Hook for fetching outbreak detection alerts.
 *
 * @param windowDays - Surveillance window in days (default 7)
 * @returns Query result with outbreak alerts
 */
export function useOutbreakAlerts(windowDays: number = 7) {
  return useOfflineQuery<OutbreakAlert[]>({
    queryKey: ["federated", "outbreaks", windowDays],
    queryFn: () =>
      apiClient.get<OutbreakAlert[]>(
        `/federated/outbreaks?window_days=${windowDays}`,
      ),
    refetchInterval: 60_000,
  });
}
