"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  ReportsSummary,
  FacilityDashboard,
  DashboardTrends,
  TopDiagnosis,
  ReportTemplateListItem,
  ReportTemplateResponse,
  ReportTemplateCreate,
  GeneratedReportListResponse,
  GeneratedReportResponse,
  ReportGenerateRequest,
} from "@aifya/shared";

// ── Summary ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching reports module summary.
 *
 * @returns Query result with reports summary stats
 */
export function useReportsSummary() {
  return useOfflineQuery<ReportsSummary>({
    queryKey: ["reports", "summary"],
    queryFn: () => apiClient.get<ReportsSummary>("/reports/summary"),
    refetchInterval: 30_000,
  });
}

// ── Facility Dashboard ─────────────────────────────────────────────────────

/**
 * Hook for fetching facility-wide dashboard analytics.
 *
 * @returns Query result with facility dashboard
 */
export function useFacilityDashboard() {
  return useOfflineQuery<FacilityDashboard>({
    queryKey: ["reports", "dashboard"],
    queryFn: () => apiClient.get<FacilityDashboard>("/reports/dashboard"),
    refetchInterval: 30_000,
  });
}

/**
 * Hook for fetching dashboard trend data.
 *
 * @param days - Number of days to look back
 * @returns Query result with trend data
 */
export function useDashboardTrends(days: number = 14) {
  return useOfflineQuery<DashboardTrends>({
    queryKey: ["reports", "trends", days],
    queryFn: () =>
      apiClient.get<DashboardTrends>(`/reports/dashboard/trends?days=${days}`),
    refetchInterval: 60_000,
  });
}

/**
 * Hook for fetching top diagnoses.
 *
 * @param dateFrom - Optional start date
 * @param dateTo - Optional end date
 * @param limit - Max results
 * @returns Query result with top diagnoses
 */
export function useTopDiagnoses(
  dateFrom?: string,
  dateTo?: string,
  limit: number = 10
) {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  params.set("limit", String(limit));
  const qs = params.toString();

  return useOfflineQuery<TopDiagnosis[]>({
    queryKey: ["reports", "top-diagnoses", dateFrom, dateTo, limit],
    queryFn: () =>
      apiClient.get<TopDiagnosis[]>(
        `/reports/dashboard/top-diagnoses?${qs}`
      ),
    refetchInterval: 60_000,
  });
}

// ── Report Templates ───────────────────────────────────────────────────────

/**
 * Hook for fetching report templates.
 *
 * @param category - Optional category filter
 * @param department - Optional department filter
 * @returns Query result with templates
 */
export function useReportTemplates(category?: string, department?: string) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (department) params.set("department", department);
  const qs = params.toString();

  return useOfflineQuery<ReportTemplateListItem[]>({
    queryKey: ["reports", "templates", category, department],
    queryFn: () =>
      apiClient.get<ReportTemplateListItem[]>(
        `/reports/templates${qs ? `?${qs}` : ""}`
      ),
  });
}

/**
 * Hook for fetching a single report template.
 *
 * @param templateId - Template UUID
 * @returns Query result with template detail
 */
export function useReportTemplate(templateId?: string) {
  return useOfflineQuery<ReportTemplateResponse>({
    queryKey: ["reports", "template", templateId],
    queryFn: () =>
      apiClient.get<ReportTemplateResponse>(
        `/reports/templates/${templateId}`
      ),
    enabled: !!templateId,
  });
}

/**
 * Hook for creating a report template.
 *
 * @returns Mutation for creating a template
 */
export function useCreateReportTemplate() {
  const qc = useQueryClient();
  return useOfflineMutation<ReportTemplateResponse, ReportTemplateCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<ReportTemplateResponse>(
          "/reports/templates",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["reports", "templates"] });
      },
    },
    { url: "/api/v1/reports/templates", method: "POST" },
  );
}

// ── Report Generation ──────────────────────────────────────────────────────

/**
 * Hook for generating a report.
 *
 * @returns Mutation for generating a report
 */
export function useGenerateReport() {
  const qc = useQueryClient();
  return useOfflineMutation<GeneratedReportResponse, ReportGenerateRequest>(
    {
      mutationFn: (data) =>
        apiClient.post<GeneratedReportResponse>(
          "/reports/generate",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["reports", "generated"] });
      },
    },
    { url: "/api/v1/reports/generate", method: "POST" },
  );
}

/**
 * Hook for fetching generated reports list.
 *
 * @param templateId - Optional template filter
 * @returns Query result with generated reports
 */
export function useGeneratedReports(templateId?: string) {
  const params = new URLSearchParams();
  if (templateId) params.set("template_id", templateId);
  const qs = params.toString();

  return useOfflineQuery<GeneratedReportListResponse>({
    queryKey: ["reports", "generated", templateId],
    queryFn: () =>
      apiClient.get<GeneratedReportListResponse>(
        `/reports/generated${qs ? `?${qs}` : ""}`
      ),
    refetchInterval: 15_000,
  });
}

/**
 * Hook for fetching a single generated report.
 *
 * @param reportId - Report UUID
 * @returns Query result with generated report data
 */
export function useGeneratedReport(reportId?: string) {
  return useOfflineQuery<GeneratedReportResponse>({
    queryKey: ["reports", "generated", "detail", reportId],
    queryFn: () =>
      apiClient.get<GeneratedReportResponse>(`/reports/generated/${reportId}`),
    enabled: !!reportId,
  });
}
