"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { generateId } from "@/lib/utils";
import type {
  ImagingAnalysisRequest,
  ImagingAnalysisResult,
  ImagingAnalysisTypeInfo,
} from "@aifya/shared";

// ── Analyze Image ───────────────────────────────────────────────────────────

/**
 * Hook for submitting a medical image for AI analysis.
 *
 * @returns Mutation for imaging analysis
 */
export function useImagingAnalysis() {
  return useOfflineMutation<ImagingAnalysisResult, ImagingAnalysisRequest>(
    {
      mutationFn: (data: ImagingAnalysisRequest) =>
        apiClient.post<ImagingAnalysisResult>(
          "/imaging/analyze",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/imaging/analyze", method: "POST" },
  );
}

// ── Analysis Types ──────────────────────────────────────────────────────────

/**
 * Hook for fetching available AI analysis types.
 *
 * @returns Query result with analysis type metadata
 */
export function useImagingAnalysisTypes() {
  return useOfflineQuery<ImagingAnalysisTypeInfo[]>({
    queryKey: ["imaging", "analysis-types"],
    queryFn: () =>
      apiClient.get<ImagingAnalysisTypeInfo[]>("/imaging/analysis-types"),
    refetchInterval: 300_000,
  });
}
