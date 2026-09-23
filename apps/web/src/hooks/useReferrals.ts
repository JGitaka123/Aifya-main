"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  ReferralListResponse,
  ReferralResponse,
  ReferralCreate,
  ReferralUpdateStatus,
  ReferralSummary,
  FacilityLookupResponse,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { apiClient } from "@/lib/api-client";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const REF_KEYS = {
  all: ["referrals"] as const,
  summary: () => [...REF_KEYS.all, "summary"] as const,
  list: (direction?: string, status?: string) => [...REF_KEYS.all, "list", direction, status] as const,
  detail: (id: string) => [...REF_KEYS.all, "detail", id] as const,
  facilityLookup: (query: string) =>
    [...REF_KEYS.all, "facility-lookup", query] as const,
};

/** Get referral summary. */
export function useReferralSummary() {
  return useOfflineQuery<ReferralSummary>({
    queryKey: REF_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/referrals/summary"),
    staleTime: 30_000,
  });
}

/** Get referral list. */
export function useReferralList(direction?: string, status?: string) {
  const params = new URLSearchParams();
  if (direction) params.set("direction", direction);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useOfflineQuery<ReferralListResponse>({
    queryKey: REF_KEYS.list(direction, status),
    queryFn: () => apiFetch(`/api/v1/referrals${qs ? `?${qs}` : ""}`),
    staleTime: 30_000,
  });
}

/** Get referral detail. */
export function useReferralDetail(id: string) {
  return useOfflineQuery<ReferralResponse>({
    queryKey: REF_KEYS.detail(id),
    queryFn: () => apiFetch(`/api/v1/referrals/${id}`),
    enabled: !!id,
  });
}

/**
 * Look up candidate receiving facilities in the facility register.
 *
 * Lets the referral form confirm the destination hospital exists - and pull
 * its MFL code - before the referral is dispatched, mirroring the pharmacy
 * stock check made before a medicine is prescribed.
 *
 * @param query - Facility name, MFL code or facility code
 * @param limit - Maximum number of matches
 * @returns Query result with matching facilities
 */
export function useFacilityLookup(query: string, limit: number = 8) {
  const term = query.trim();

  return useOfflineQuery<FacilityLookupResponse>({
    queryKey: REF_KEYS.facilityLookup(term),
    queryFn: () =>
      apiClient.get<FacilityLookupResponse>("/referrals/facility-lookup", {
        q: term,
        limit: String(limit),
      }),
    enabled: term.length >= 3,
    staleTime: 300_000,
  });
}

/** Create referral. */
export function useCreateReferral() {
  const qc = useQueryClient();
  return useOfflineMutation<ReferralResponse, ReferralCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/referrals", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: REF_KEYS.all }),
    },
    { url: `${API_URL}/referrals`, method: "POST" }
  );
}

/** Update referral status. */
export function useUpdateReferralStatus(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ReferralResponse, ReferralUpdateStatus>(
    {
      mutationFn: (data) => idempotentApiFetch(`/api/v1/referrals/${id}/status`, { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: REF_KEYS.all }),
    },
    { url: `${API_URL}/referrals/${id}/status`, method: "POST" }
  );
}
