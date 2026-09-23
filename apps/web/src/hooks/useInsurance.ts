"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  InsuranceSchemeListResponse,
  InsuranceSchemeResponse,
  InsuranceSchemeCreate,
  ClaimListResponse,
  ClaimResponse,
  ClaimCreate,
  ClaimStatusUpdate,
  InsuranceSummary,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const INS_KEYS = {
  all: ["insurance"] as const,
  summary: () => [...INS_KEYS.all, "summary"] as const,
  schemes: () => [...INS_KEYS.all, "schemes"] as const,
  claims: (status?: string) => [...INS_KEYS.all, "claims", status] as const,
  claim: (id: string) => [...INS_KEYS.all, "claim", id] as const,
};

/** Get insurance summary. */
export function useInsuranceSummary() {
  return useOfflineQuery<InsuranceSummary>({
    queryKey: INS_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/insurance/summary"),
    staleTime: 30_000,
  });
}

/** Get insurance schemes. */
export function useInsuranceSchemes() {
  return useOfflineQuery<InsuranceSchemeListResponse>({
    queryKey: INS_KEYS.schemes(),
    queryFn: () => apiFetch("/api/v1/insurance/schemes"),
    staleTime: 60_000,
  });
}

/** Create insurance scheme. */
export function useCreateScheme() {
  const qc = useQueryClient();
  return useOfflineMutation<InsuranceSchemeResponse, InsuranceSchemeCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/insurance/schemes", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.schemes() }),
    },
    { url: `${API_URL}/insurance/schemes`, method: "POST" }
  );
}

/** Get insurance claims. */
export function useInsuranceClaims(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<ClaimListResponse>({
    queryKey: INS_KEYS.claims(status),
    queryFn: () => apiFetch(`/api/v1/insurance/claims${params}`),
    staleTime: 30_000,
  });
}

/** Get a single insurance claim. */
export function useInsuranceClaim(id: string) {
  return useOfflineQuery<ClaimResponse>({
    queryKey: INS_KEYS.claim(id),
    queryFn: () => apiFetch(`/api/v1/insurance/claims/${id}`),
    enabled: !!id,
  });
}

/** Create insurance claim. */
export function useCreateClaim() {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimResponse, ClaimCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/insurance/claims", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    { url: `${API_URL}/insurance/claims`, method: "POST" }
  );
}

/** Update claim status. */
export function useUpdateClaimStatus(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<ClaimResponse, ClaimStatusUpdate>(
    {
      mutationFn: (data) => idempotentApiFetch(`/api/v1/insurance/claims/${id}/status`, { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INS_KEYS.all }),
    },
    { url: `${API_URL}/insurance/claims/${id}/status`, method: "POST" }
  );
}
