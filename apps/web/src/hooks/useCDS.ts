"use client";

import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type {
  CDSEvaluationResponse,
  CDSPrescriptionRequest,
  CDSVitalsRequest,
  CDSLabRequest,
} from "@aifya/shared";

/**
 * Hook for evaluating CDS rules against a prescription.
 * Calls the CDS engine in real-time (not offline-queued) since clinical
 * decision support requires server-side rule evaluation.
 *
 * @returns TanStack Query mutation for prescription CDS evaluation
 */
export function useEvaluatePrescription() {
  return useMutation<CDSEvaluationResponse, Error, CDSPrescriptionRequest>({
    mutationFn: (data: CDSPrescriptionRequest) =>
      apiClient.post<CDSEvaluationResponse>(
        "/cds/evaluate/prescription",
        data
      ),
  });
}

/**
 * Hook for evaluating CDS rules against recorded vital signs.
 * Returns alerts for critical values, sepsis risk, age-adjusted thresholds, etc.
 *
 * @returns TanStack Query mutation for vitals CDS evaluation
 */
export function useEvaluateVitals() {
  return useMutation<CDSEvaluationResponse, Error, CDSVitalsRequest>({
    mutationFn: (data: CDSVitalsRequest) =>
      apiClient.post<CDSEvaluationResponse>("/cds/evaluate/vitals", data),
  });
}

/**
 * Hook for evaluating CDS rules against lab results.
 * Returns alerts for critical values, trending abnormalities, etc.
 *
 * @returns TanStack Query mutation for lab CDS evaluation
 */
export function useEvaluateLab() {
  return useMutation<CDSEvaluationResponse, Error, CDSLabRequest>({
    mutationFn: (data: CDSLabRequest) =>
      apiClient.post<CDSEvaluationResponse>("/cds/evaluate/lab", data),
  });
}
