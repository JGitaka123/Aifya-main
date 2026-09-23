"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  EmergencyListResponse,
  EmergencySummary,
  EmergencyVisitResponse,
  EmergencyVisitCreate,
  TriageRequest,
  AssignDoctorRequest,
  DispositionRequest,
  DoctorOnDuty,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const EMERGENCY_KEYS = {
  all: ["emergency"] as const,
  summary: () => [...EMERGENCY_KEYS.all, "summary"] as const,
  queue: (status?: string) => [...EMERGENCY_KEYS.all, "queue", status] as const,
  onDuty: (date?: string) => [...EMERGENCY_KEYS.all, "on-duty", date] as const,
  visit: (id: string) => [...EMERGENCY_KEYS.all, "visit", id] as const,
};

/** Get emergency department summary stats. */
export function useEmergencySummary() {
  return useOfflineQuery<EmergencySummary>({
    queryKey: EMERGENCY_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/emergency/summary"),
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

/** Get emergency queue ordered by triage priority. */
export function useEmergencyQueue(status?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<EmergencyListResponse>({
    queryKey: EMERGENCY_KEYS.queue(status),
    queryFn: () => apiFetch(`/api/v1/emergency/queue${qs ? `?${qs}` : ""}`),
    staleTime: 10_000,
    refetchInterval: 10_000,
  });
}

/** Get a single emergency visit. */
export function useEmergencyVisit(visitId: string) {
  return useOfflineQuery<EmergencyVisitResponse>({
    queryKey: EMERGENCY_KEYS.visit(visitId),
    queryFn: () => apiFetch(`/api/v1/emergency/visits/${visitId}`),
    enabled: !!visitId,
  });
}

/** Register a new emergency visit. */
export function useRegisterEmergencyVisit() {
  const qc = useQueryClient();
  return useOfflineMutation<EmergencyVisitResponse, EmergencyVisitCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/emergency/visits", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: EMERGENCY_KEYS.all }),
    },
    { url: `${API_URL}/emergency/visits`, method: "POST" }
  );
}

/** Perform SATS triage on a visit. */
export function useTriageVisit(visitId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<EmergencyVisitResponse, TriageRequest>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/emergency/visits/${visitId}/triage`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: EMERGENCY_KEYS.all }),
    },
    { url: `${API_URL}/emergency/visits/${visitId}/triage`, method: "POST" }
  );
}

/** Assign a doctor to a visit. */
export function useAssignDoctor(visitId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<EmergencyVisitResponse, AssignDoctorRequest>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/emergency/visits/${visitId}/assign-doctor`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: EMERGENCY_KEYS.all }),
    },
    { url: `${API_URL}/emergency/visits/${visitId}/assign-doctor`, method: "POST" }
  );
}

/** Record disposition for a visit. */
export function useRecordDisposition(visitId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<EmergencyVisitResponse, DispositionRequest>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/emergency/visits/${visitId}/disposition`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: EMERGENCY_KEYS.all }),
    },
    { url: `${API_URL}/emergency/visits/${visitId}/disposition`, method: "POST" }
  );
}

/** Get doctors on duty (rostered shift today). */
export function useDoctorsOnDuty(date?: string) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  const qs = params.toString();

  return useOfflineQuery<DoctorOnDuty[]>({
    queryKey: EMERGENCY_KEYS.onDuty(date),
    queryFn: () => apiFetch(`/api/v1/emergency/doctors-on-duty${qs ? `?${qs}` : ""}`),
    refetchInterval: 30_000,
  });
}
