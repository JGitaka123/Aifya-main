"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import type {
  ReadmissionRisk,
  BedDemandForecast,
  StockoutPrediction,
  RevenueForecast,
  NoShowPrediction,
  AnalyticsDashboard,
} from "@aifya/shared";

// ── Readmission Risk ────────────────────────────────────────────────────────

/**
 * Hook for fetching AI-predicted readmission risk for a patient.
 *
 * @param patientId - Patient UUID
 * @returns Query result with readmission risk data
 */
export function useReadmissionRisk(patientId: string | undefined) {
  return useOfflineQuery<ReadmissionRisk>({
    queryKey: ["analytics", "readmission-risk", patientId],
    queryFn: () =>
      apiClient.get<ReadmissionRisk>(
        `/analytics/readmission-risk/${patientId}`
      ),
    enabled: !!patientId,
    refetchInterval: 60_000,
  });
}

// ── Bed Demand Forecast ─────────────────────────────────────────────────────

/**
 * Hook for fetching AI-predicted bed occupancy forecasts.
 *
 * @param department - Optional department filter
 * @param daysAhead - Number of days to forecast (default 7)
 * @returns Query result with bed demand forecast array
 */
export function useBedForecast(department?: string, daysAhead: number = 7) {
  const params = new URLSearchParams();
  if (department) params.set("department", department);
  params.set("days_ahead", String(daysAhead));
  const qs = params.toString();

  return useOfflineQuery<BedDemandForecast[]>({
    queryKey: ["analytics", "bed-forecast", department, daysAhead],
    queryFn: () =>
      apiClient.get<BedDemandForecast[]>(`/analytics/bed-forecast?${qs}`),
    refetchInterval: 60_000,
  });
}

// ── Stockout Predictions ────────────────────────────────────────────────────

/**
 * Hook for fetching AI-predicted inventory stockout alerts.
 *
 * @returns Query result with stockout prediction array
 */
export function useStockoutPredictions() {
  return useOfflineQuery<StockoutPrediction[]>({
    queryKey: ["analytics", "stockout-predictions"],
    queryFn: () =>
      apiClient.get<StockoutPrediction[]>("/analytics/stockout-predictions"),
    refetchInterval: 60_000,
  });
}

// ── Revenue Forecast ────────────────────────────────────────────────────────

/**
 * Hook for fetching AI-predicted revenue forecasts.
 *
 * @param monthsAhead - Number of months to forecast (default 3)
 * @returns Query result with revenue forecast array
 */
export function useRevenueForecast(monthsAhead: number = 3) {
  const params = new URLSearchParams();
  params.set("months_ahead", String(monthsAhead));
  const qs = params.toString();

  return useOfflineQuery<RevenueForecast[]>({
    queryKey: ["analytics", "revenue-forecast", monthsAhead],
    queryFn: () =>
      apiClient.get<RevenueForecast[]>(`/analytics/revenue-forecast?${qs}`),
    refetchInterval: 120_000,
  });
}

// ── Analytics Dashboard ─────────────────────────────────────────────────────

/**
 * Hook for fetching the full predictive analytics dashboard.
 *
 * @returns Query result with aggregated analytics dashboard data
 */
/** Raw shape returned by the backend /analytics/dashboard endpoint. */
interface AnalyticsDashboardPayload {
  top_readmission_risks: ReadmissionRisk[] | null;
  bed_forecast_7d: BedDemandForecast[] | null;
  critical_stockouts: StockoutPrediction[] | null;
  revenue_forecast_3m: RevenueForecast[] | null;
  upcoming_no_shows: NoShowPrediction[] | null;
  generated_at: string;
}

export function useAnalyticsDashboard() {
  return useOfflineQuery<AnalyticsDashboard>({
    queryKey: ["analytics", "dashboard"],
    queryFn: async () => {
      const raw =
        await apiClient.get<AnalyticsDashboardPayload>(
          "/analytics/dashboard"
        );
      return {
        readmission_risks: raw.top_readmission_risks ?? [],
        bed_forecasts: raw.bed_forecast_7d ?? [],
        stockout_predictions: raw.critical_stockouts ?? [],
        revenue_forecasts: raw.revenue_forecast_3m ?? [],
        no_show_predictions: raw.upcoming_no_shows ?? [],
        generated_at: raw.generated_at,
      };
    },
    refetchInterval: 60_000,
  });
}
