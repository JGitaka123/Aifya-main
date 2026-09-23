"use client";

import { useMutation, type UseMutationOptions, type UseMutationResult } from "@tanstack/react-query";
import { queueMutation } from "@/lib/offline-store";
import { generateId } from "@/lib/utils";

type IdGenerator = () => string;

interface OfflineQueueConfig<TVariables> {
  url?: string | ((variables: TVariables) => string);
  method?: string;
  body?: (variables: TVariables) => unknown;
  storeName?: string;
  offlineKey?: string;
  generateId?: IdGenerator;
  generateOfflineId?: IdGenerator;
}

type OfflineMutationOptions<TData, TVariables> =
  UseMutationOptions<TData, Error, TVariables> & {
    offlineKey?: string;
    generateOfflineId?: IdGenerator;
  };

function normalizeOfflineConfig<TData, TVariables>(
  options: OfflineMutationOptions<TData, TVariables>,
  offlineConfig?: OfflineQueueConfig<TVariables> | string
): {
  url: string | ((variables: TVariables) => string);
  method: string;
  body: (variables: TVariables) => unknown;
  generateOfflineId: IdGenerator;
} {
  if (typeof offlineConfig === "string") {
    return {
      url: offlineConfig,
      method: "POST",
      body: (variables) => variables,
      generateOfflineId: options.generateOfflineId ?? generateId,
    };
  }

  const key =
    offlineConfig?.url ??
    offlineConfig?.offlineKey ??
    offlineConfig?.storeName ??
    options.offlineKey ??
    "offline-mutation";

  return {
    url: key,
    method: offlineConfig?.method ?? "POST",
    body: offlineConfig?.body ?? ((variables) => variables),
    generateOfflineId:
      offlineConfig?.generateOfflineId ??
      offlineConfig?.generateId ??
      options.generateOfflineId ??
      generateId,
  };
}

/**
 * TanStack Mutation wrapper that queues mutations when offline.
 * Per CLAUDE.md: every mutation must queue locally if offline, sync when connected.
 *
 * @param options - Standard TanStack Mutation options
 * @param offlineConfig - URL and method for offline queue
 * @returns Mutation result
 */
export function useOfflineMutation<TData, TVariables>(
  options: OfflineMutationOptions<TData, TVariables>,
  offlineConfig?: OfflineQueueConfig<TVariables> | string
): UseMutationResult<TData, Error, TVariables> {
  const mutationOptions = options;
  const queueConfig = normalizeOfflineConfig(options, offlineConfig);

  return useMutation<TData, Error, TVariables>({
    ...mutationOptions,
    mutationFn: async (variables: TVariables, context) => {
      if (!navigator.onLine) {
        const offlineId = queueConfig.generateOfflineId();
        const url =
          typeof queueConfig.url === "function"
            ? queueConfig.url(variables)
            : queueConfig.url;
        await queueMutation({
          id: offlineId,
          url,
          method: queueConfig.method,
          body: JSON.stringify(queueConfig.body(variables)),
          headers: {
            "Content-Type": "application/json",
            // Lets the backend dedupe if the replay is retried.
            "X-Idempotency-Key": offlineId,
          },
          createdAt: new Date().toISOString(),
        });
        // Return optimistic data for offline
        return variables as unknown as TData;
      }

      if (mutationOptions.mutationFn) {
        return mutationOptions.mutationFn(variables, context);
      }
      throw new Error("No mutationFn provided");
    },
  });
}
