"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { generateId } from "@/lib/utils";
import type {
  AgentWorkflow,
  AgentTypeInfo,
  DischargeAgentInput,
  ClaimsAgentInput,
  ScreeningAgentInput,
} from "@aifya/shared";

// ── Agent Types ─────────────────────────────────────────────────────────────

/**
 * Hook for fetching available agent workflow types.
 *
 * @returns Query result with agent type metadata
 */
export function useAgentTypes() {
  return useOfflineQuery<AgentTypeInfo[]>({
    queryKey: ["agents", "types"],
    queryFn: () => apiClient.get<AgentTypeInfo[]>("/agents/types"),
    refetchInterval: 300_000,
  });
}

// ── Discharge Agent ─────────────────────────────────────────────────────────

/**
 * Hook for running the discharge planning agent.
 *
 * @returns Mutation for discharge agent execution
 */
export function useDischargeAgent() {
  return useOfflineMutation<AgentWorkflow, DischargeAgentInput>(
    {
      mutationFn: (data: DischargeAgentInput) =>
        apiClient.post<AgentWorkflow>(
          "/agents/discharge",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/agents/discharge", method: "POST" },
  );
}

// ── Claims Agent ────────────────────────────────────────────────────────────

/**
 * Hook for running the SHA claims automation agent.
 *
 * @returns Mutation for claims agent execution
 */
export function useClaimsAgent() {
  return useOfflineMutation<AgentWorkflow, ClaimsAgentInput>(
    {
      mutationFn: (data: ClaimsAgentInput) =>
        apiClient.post<AgentWorkflow>("/agents/claims", data, generateId()),
    },
    { url: "/api/v1/agents/claims", method: "POST" },
  );
}

// ── Screening Agent ─────────────────────────────────────────────────────────

/**
 * Hook for running the clinical trial screening agent.
 *
 * @returns Mutation for screening agent execution
 */
export function useScreeningAgent() {
  return useOfflineMutation<AgentWorkflow, ScreeningAgentInput>(
    {
      mutationFn: (data: ScreeningAgentInput) =>
        apiClient.post<AgentWorkflow>(
          "/agents/screening",
          data,
          generateId(),
        ),
    },
    { url: "/api/v1/agents/screening", method: "POST" },
  );
}
