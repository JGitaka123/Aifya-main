"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  TheatreResponse,
  TheatreCreate,
  SurgicalCaseListResponse,
  SurgicalCaseResponse,
  SurgicalCaseCreate,
  OperativeNotesRequest,
  TheatreSummary,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const THEATRE_KEYS = {
  all: ["theatre"] as const,
  summary: () => [...THEATRE_KEYS.all, "summary"] as const,
  theatres: () => [...THEATRE_KEYS.all, "theatres"] as const,
  cases: (date?: string, status?: string) => [...THEATRE_KEYS.all, "cases", date, status] as const,
  case_: (id: string) => [...THEATRE_KEYS.all, "case", id] as const,
};

/** Get theatre summary. */
export function useTheatreSummary() {
  return useOfflineQuery<TheatreSummary>({
    queryKey: THEATRE_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/theatre/summary"),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

/** Get theatres. */
export function useTheatres() {
  return useOfflineQuery<TheatreResponse[]>({
    queryKey: THEATRE_KEYS.theatres(),
    queryFn: () => apiFetch("/api/v1/theatre/theatres"),
    staleTime: 60_000,
  });
}

/** Create theatre. */
export function useCreateTheatre() {
  const qc = useQueryClient();
  return useOfflineMutation<TheatreResponse, TheatreCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/theatre/theatres", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: THEATRE_KEYS.all }),
    },
    { url: `${API_URL}/theatre/theatres`, method: "POST" }
  );
}

/** Get surgical case list. */
export function useSurgicalCases(date?: string, status?: string) {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<SurgicalCaseListResponse>({
    queryKey: THEATRE_KEYS.cases(date, status),
    queryFn: () => apiFetch(`/api/v1/theatre/cases${qs ? `?${qs}` : ""}`),
    staleTime: 15_000,
  });
}

/** Get a single surgical case. */
export function useSurgicalCase(caseId: string) {
  return useOfflineQuery<SurgicalCaseResponse>({
    queryKey: THEATRE_KEYS.case_(caseId),
    queryFn: () => apiFetch(`/api/v1/theatre/cases/${caseId}`),
    enabled: !!caseId,
  });
}

/** Schedule a surgical case. */
export function useScheduleCase() {
  const qc = useQueryClient();
  return useOfflineMutation<SurgicalCaseResponse, SurgicalCaseCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/theatre/cases", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: THEATRE_KEYS.all }),
    },
    { url: `${API_URL}/theatre/cases`, method: "POST" }
  );
}

/** Update case status. */
export function useUpdateCaseStatus(caseId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SurgicalCaseResponse, { status: string }>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/theatre/cases/${caseId}/status?status=${data.status}`, { method: "PATCH" }),
      onSuccess: () => qc.invalidateQueries({ queryKey: THEATRE_KEYS.all }),
    },
    { url: `${API_URL}/theatre/cases/${caseId}/status`, method: "PATCH" }
  );
}

/** Record operative notes. */
export function useRecordOperativeNotes(caseId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SurgicalCaseResponse, OperativeNotesRequest>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/theatre/cases/${caseId}/operative-notes`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: THEATRE_KEYS.all }),
    },
    { url: `${API_URL}/theatre/cases/${caseId}/operative-notes`, method: "POST" }
  );
}
