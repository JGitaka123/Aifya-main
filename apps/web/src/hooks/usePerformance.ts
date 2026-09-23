"use client";

import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { apiFetch } from "@/lib/api";

/**
 * Facility KPIs returned by GET /api/v1/performance/kpis.
 */
export interface FacilityKpis {
  period_start: string;
  period_end: string;
  patient_volume: number;
  bed_occupancy_rate: number;
  average_length_of_stay: number;
  readmission_rate: number;
  revenue_per_patient: number;
  claim_rejection_rate: number;
  lab_turnaround_time: number;
  emergency_response_time: number;
  staff_attendance_rate: number;
  patient_satisfaction: number;
  total_encounters: number;
  total_admissions: number;
  total_revenue: number;
}

/**
 * Trend point returned by GET /api/v1/performance/trends.
 */
export interface KpiTrendPoint {
  bucket: string;
  value: number;
}

/**
 * Trend response returned by GET /api/v1/performance/trends.
 */
export interface KpiTrendResponse {
  metric: string;
  bucket: string;
  points: KpiTrendPoint[];
}

/**
 * Period-over-period comparison.
 */
export interface PeriodComparison {
  current: FacilityKpis;
  prior: FacilityKpis;
  delta_pct: Record<string, number>;
  compare_to: string;
}

/** Period preset accepted by useFacilityKPIs. */
export type PerformancePeriod =
  | "last_7_days"
  | "last_30_days"
  | "last_quarter"
  | "last_year";

/**
 * Convert a period preset to (start, end) date strings.
 *
 * @param period - Period preset
 * @returns ISO date strings { start, end }
 */
function rangeFor(period: PerformancePeriod): { start: string; end: string } {
  const today = new Date();
  const end = today.toISOString().slice(0, 10);
  const days =
    period === "last_7_days"
      ? 6
      : period === "last_quarter"
      ? 89
      : period === "last_year"
      ? 364
      : 29;
  const startDate = new Date(today.getTime() - days * 86400000);
  return { start: startDate.toISOString().slice(0, 10), end };
}

/**
 * Facility KPIs hook.
 *
 * @param period - Period preset (defaults to last 30 days)
 * @returns Query result with facility KPIs
 */
export function useFacilityKPIs(period: PerformancePeriod = "last_30_days") {
  const { start, end } = rangeFor(period);
  return useOfflineQuery<FacilityKpis>({
    queryKey: ["performance", "kpis", period],
    queryFn: () =>
      apiFetch(`/api/v1/performance/kpis?start=${start}&end=${end}`),
    staleTime: 60_000,
  });
}

/**
 * Single-metric trend hook.
 *
 * @param metric - Metric name
 * @param period - Period preset
 * @param bucket - Bucket size (day or month)
 * @returns Query result with trend points
 */
export function useMetricTrend(
  metric: string,
  period: PerformancePeriod = "last_30_days",
  bucket: "day" | "month" = "day",
) {
  return useOfflineQuery<KpiTrendResponse>({
    queryKey: ["performance", "trend", metric, period, bucket],
    queryFn: () =>
      apiFetch(
        `/api/v1/performance/trends?metric=${metric}&period=${period}&bucket=${bucket}`,
      ),
    staleTime: 60_000,
  });
}

/**
 * Period-over-period comparison hook.
 *
 * @param compareTo - "last_month" or "last_year"
 * @returns Query result with current/prior KPIs and deltas
 */
export function usePeriodComparison(
  compareTo: "last_month" | "last_year" = "last_month",
) {
  return useOfflineQuery<PeriodComparison>({
    queryKey: ["performance", "comparison", compareTo],
    queryFn: () =>
      apiFetch(`/api/v1/performance/comparison?compare_to=${compareTo}`),
    staleTime: 60_000,
  });
}
