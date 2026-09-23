"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  DentalChartResponse,
  DentalChartUpdate,
  DentalVisitListResponse,
  DentalVisitResponse,
  DentalVisitCreate,
  DentalTreatmentPlanListResponse,
  DentalTreatmentPlanResponse,
  DentalTreatmentPlanCreate,
  DentalTreatmentPlanStatusUpdate,
  DentalSummary,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const DENTAL_KEYS = {
  all: ["dental"] as const,
  summary: () => [...DENTAL_KEYS.all, "summary"] as const,
  chart: (patientId: string) => [...DENTAL_KEYS.all, "chart", patientId] as const,
  visits: (patientId?: string) => [...DENTAL_KEYS.all, "visits", patientId] as const,
  visit: (id: string) => [...DENTAL_KEYS.all, "visit", id] as const,
  plans: (patientId?: string) => [...DENTAL_KEYS.all, "plans", patientId] as const,
};

export function useDentalSummary() {
  return useOfflineQuery<DentalSummary>({
    queryKey: DENTAL_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/dental/summary"),
    staleTime: 30_000,
  });
}

export function useDentalChart(patientId: string) {
  return useOfflineQuery<DentalChartResponse>({
    queryKey: DENTAL_KEYS.chart(patientId),
    queryFn: () => apiFetch(`/api/v1/dental/charts/${patientId}`),
    enabled: !!patientId,
  });
}

export function useUpdateDentalChart(patientId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<DentalChartResponse, DentalChartUpdate>(
    {
      mutationFn: (data) => idempotentApiFetch(`/api/v1/dental/charts/${patientId}`, { method: "PUT", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: DENTAL_KEYS.chart(patientId) }),
    },
    { url: `${API_URL}/dental/charts/${patientId}`, method: "PUT" }
  );
}

export function useDentalVisits(patientId?: string) {
  const params = patientId ? `?patient_id=${patientId}` : "";
  return useOfflineQuery<DentalVisitListResponse>({
    queryKey: DENTAL_KEYS.visits(patientId),
    queryFn: () => apiFetch(`/api/v1/dental/visits${params}`),
    staleTime: 30_000,
  });
}

export function useDentalVisit(visitId: string) {
  return useOfflineQuery<DentalVisitResponse>({
    queryKey: DENTAL_KEYS.visit(visitId),
    queryFn: () => apiFetch(`/api/v1/dental/visits/${visitId}`),
    enabled: !!visitId,
  });
}

export function useCreateDentalVisit() {
  const qc = useQueryClient();
  return useOfflineMutation<DentalVisitResponse, DentalVisitCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/dental/visits", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: DENTAL_KEYS.all }),
    },
    { url: `${API_URL}/dental/visits`, method: "POST" }
  );
}

export function useDentalTreatmentPlans(patientId?: string) {
  const params = patientId ? `?patient_id=${patientId}` : "";
  return useOfflineQuery<DentalTreatmentPlanListResponse>({
    queryKey: DENTAL_KEYS.plans(patientId),
    queryFn: () => apiFetch(`/api/v1/dental/treatment-plans${params}`),
    staleTime: 30_000,
  });
}

export function useCreateTreatmentPlan() {
  const qc = useQueryClient();
  return useOfflineMutation<DentalTreatmentPlanResponse, DentalTreatmentPlanCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/dental/treatment-plans", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: DENTAL_KEYS.all }),
    },
    { url: `${API_URL}/dental/treatment-plans`, method: "POST" }
  );
}

/**
 * Hook for moving a treatment plan through its lifecycle.
 *
 * @returns Mutation for updating a treatment plan's status
 */
export function useUpdateTreatmentPlanStatus() {
  const qc = useQueryClient();
  return useOfflineMutation<
    DentalTreatmentPlanResponse,
    DentalTreatmentPlanStatusUpdate & { planId: string }
  >(
    {
      mutationFn: ({ planId, status }) =>
        idempotentApiFetch(
          `/api/v1/dental/treatment-plans/${planId}/status`,
          { method: "PATCH", body: JSON.stringify({ status }) }
        ),
      onSuccess: () => qc.invalidateQueries({ queryKey: DENTAL_KEYS.all }),
    },
    {
      url: (variables) =>
        `${API_URL}/dental/treatment-plans/${variables.planId}/status`,
      method: "PATCH",
      body: (variables) => ({ status: variables.status }),
    }
  );
}
