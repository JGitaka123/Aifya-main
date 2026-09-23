"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  TrialListResponse,
  TrialResponse,
  TrialCreate,
  TrialUpdate,
  TrialStatusUpdate,
  ParticipantListResponse,
  ParticipantResponse,
  ParticipantEnroll,
  ParticipantStatusUpdate,
  VisitScheduleResponse,
  VisitScheduleCreate,
  ParticipantVisitResponse,
  ParticipantVisitCreate,
  ParticipantVisitUpdate,
  AdverseEventListResponse,
  AdverseEventResponse,
  AdverseEventCreate,
  SAEReportSubmit,
  AIScreeningCreate,
  AIScreeningListResponse,
  AIScreeningResponse,
  AIScreeningReview,
  TrialsSummary,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const TRIAL_KEYS = {
  all: ["trials"] as const,
  summary: () => [...TRIAL_KEYS.all, "summary"] as const,
  list: (status?: string) => [...TRIAL_KEYS.all, "list", status] as const,
  detail: (id: string) => [...TRIAL_KEYS.all, "detail", id] as const,
  participants: (trialId: string, status?: string) =>
    [...TRIAL_KEYS.all, "participants", trialId, status] as const,
  participant: (trialId: string, participantId: string) =>
    [...TRIAL_KEYS.all, "participant", trialId, participantId] as const,
  visitSchedule: (trialId: string) =>
    [...TRIAL_KEYS.all, "visit-schedule", trialId] as const,
  participantVisits: (trialId: string, participantId: string) =>
    [...TRIAL_KEYS.all, "visits", trialId, participantId] as const,
  adverseEvents: (trialId: string, seriousOnly?: boolean) =>
    [...TRIAL_KEYS.all, "adverse-events", trialId, seriousOnly] as const,
  adverseEvent: (trialId: string, aeId: string) =>
    [...TRIAL_KEYS.all, "adverse-event", trialId, aeId] as const,
  aiScreenings: (trialId: string, unreviewedOnly?: boolean) =>
    [...TRIAL_KEYS.all, "ai-screening", trialId, unreviewedOnly] as const,
};

// ── Summary ─────────────────────────────────────────────────────────────────

/** Get clinical trials summary. */
export function useTrialsSummary() {
  return useOfflineQuery<TrialsSummary>({
    queryKey: TRIAL_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/trials/summary"),
    staleTime: 30_000,
  });
}

// ── Trials ──────────────────────────────────────────────────────────────────

/** Get trial list. */
export function useTrials(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<TrialListResponse>({
    queryKey: TRIAL_KEYS.list(status),
    queryFn: () => apiFetch(`/api/v1/trials${params}`),
    staleTime: 30_000,
  });
}

/** Get a single trial. */
export function useTrial(id: string) {
  return useOfflineQuery<TrialResponse>({
    queryKey: TRIAL_KEYS.detail(id),
    queryFn: () => apiFetch(`/api/v1/trials/${id}`),
    enabled: !!id,
  });
}

/** Create a clinical trial. */
export function useCreateTrial() {
  const qc = useQueryClient();
  return useOfflineMutation<TrialResponse, TrialCreate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch("/api/v1/trials", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials`, method: "POST" },
  );
}

/** Update a clinical trial. */
export function useUpdateTrial(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<TrialResponse, TrialUpdate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${id}`, method: "PATCH" },
  );
}

/** Update trial status. */
export function useUpdateTrialStatus(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<TrialResponse, TrialStatusUpdate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${id}/status`, { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${id}/status`, method: "POST" },
  );
}

// ── Participants ────────────────────────────────────────────────────────────

/** Get trial participants. */
export function useTrialParticipants(trialId: string, status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<ParticipantListResponse>({
    queryKey: TRIAL_KEYS.participants(trialId, status),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/participants${params}`),
    enabled: !!trialId,
    staleTime: 30_000,
  });
}

/** Get a single participant. */
export function useTrialParticipant(trialId: string, participantId: string) {
  return useOfflineQuery<ParticipantResponse>({
    queryKey: TRIAL_KEYS.participant(trialId, participantId),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/participants/${participantId}`),
    enabled: !!trialId && !!participantId,
  });
}

/** Enroll participant. */
export function useEnrollParticipant(trialId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ParticipantResponse, ParticipantEnroll>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/participants`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${trialId}/participants`, method: "POST" },
  );
}

/** Update participant status. */
export function useUpdateParticipantStatus(trialId: string, participantId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ParticipantResponse, ParticipantStatusUpdate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/participants/${participantId}/status`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${trialId}/participants/${participantId}/status`, method: "PATCH" },
  );
}

// ── Visit Schedule ──────────────────────────────────────────────────────────

/** Get visit schedule for a trial. */
export function useVisitSchedule(trialId: string) {
  return useOfflineQuery<VisitScheduleResponse[]>({
    queryKey: TRIAL_KEYS.visitSchedule(trialId),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/visit-schedule`),
    enabled: !!trialId,
  });
}

/** Create visit schedule entry. */
export function useCreateVisitSchedule(trialId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<VisitScheduleResponse, VisitScheduleCreate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/visit-schedule`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () =>
        qc.invalidateQueries({ queryKey: TRIAL_KEYS.visitSchedule(trialId) }),
    },
    { url: `${API_URL}/trials/${trialId}/visit-schedule`, method: "POST" },
  );
}

// ── Participant Visits ──────────────────────────────────────────────────────

/** Get visits for a participant. */
export function useParticipantVisits(trialId: string, participantId: string) {
  return useOfflineQuery<ParticipantVisitResponse[]>({
    queryKey: TRIAL_KEYS.participantVisits(trialId, participantId),
    queryFn: () =>
      apiFetch(`/api/v1/trials/${trialId}/participants/${participantId}/visits`),
    enabled: !!trialId && !!participantId,
  });
}

/** Record a participant visit. */
export function useCreateParticipantVisit(trialId: string, participantId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ParticipantVisitResponse, ParticipantVisitCreate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/participants/${participantId}/visits`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    {
      url: `${API_URL}/trials/${trialId}/participants/${participantId}/visits`,
      method: "POST",
    },
  );
}

/** Update a participant visit. */
export function useUpdateParticipantVisit(
  trialId: string,
  participantId: string,
  visitId: string,
) {
  const qc = useQueryClient();
  return useOfflineMutation<ParticipantVisitResponse, ParticipantVisitUpdate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(
          `/api/v1/trials/${trialId}/participants/${participantId}/visits/${visitId}`,
          { method: "PATCH", body: JSON.stringify(data) },
        ),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    {
      url: `${API_URL}/trials/${trialId}/participants/${participantId}/visits/${visitId}`,
      method: "PATCH",
    },
  );
}

// ── Adverse Events ──────────────────────────────────────────────────────────

/** Get adverse events for a trial. */
export function useAdverseEvents(trialId: string, seriousOnly: boolean = false) {
  const params = seriousOnly ? "?serious_only=true" : "";
  return useOfflineQuery<AdverseEventListResponse>({
    queryKey: TRIAL_KEYS.adverseEvents(trialId, seriousOnly),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/adverse-events${params}`),
    enabled: !!trialId,
    staleTime: 30_000,
  });
}

/** Get a single adverse event. */
export function useAdverseEvent(trialId: string, aeId: string) {
  return useOfflineQuery<AdverseEventResponse>({
    queryKey: TRIAL_KEYS.adverseEvent(trialId, aeId),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/adverse-events/${aeId}`),
    enabled: !!trialId && !!aeId,
  });
}

/** Report an adverse event. */
export function useReportAdverseEvent(trialId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AdverseEventResponse, AdverseEventCreate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/adverse-events`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${trialId}/adverse-events`, method: "POST" },
  );
}

/** Submit SAE report. */
export function useSubmitSAEReport(trialId: string, aeId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AdverseEventResponse, SAEReportSubmit>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/adverse-events/${aeId}/sae-report`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    {
      url: `${API_URL}/trials/${trialId}/adverse-events/${aeId}/sae-report`,
      method: "POST",
    },
  );
}

// ── AI Screening ────────────────────────────────────────────────────────────

/** Get AI screening results. */
export function useAIScreenings(trialId: string, unreviewedOnly: boolean = false) {
  const params = unreviewedOnly ? "?unreviewed_only=true" : "";
  return useOfflineQuery<AIScreeningListResponse>({
    queryKey: TRIAL_KEYS.aiScreenings(trialId, unreviewedOnly),
    queryFn: () => apiFetch(`/api/v1/trials/${trialId}/ai-screening${params}`),
    enabled: !!trialId,
    staleTime: 30_000,
  });
}

/** Run (or refresh) an AI screening for a patient against a trial. */
export function useRunAIScreening(trialId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AIScreeningResponse, AIScreeningCreate>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/ai-screening`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    { url: `${API_URL}/trials/${trialId}/ai-screening`, method: "POST" },
  );
}

/** Review an AI screening result. */
export function useReviewAIScreening(trialId: string, screeningId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<AIScreeningResponse, AIScreeningReview>(
    {
      mutationFn: (data) =>
        idempotentApiFetch(`/api/v1/trials/${trialId}/ai-screening/${screeningId}/review`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: TRIAL_KEYS.all }),
    },
    {
      url: `${API_URL}/trials/${trialId}/ai-screening/${screeningId}/review`,
      method: "POST",
    },
  );
}
