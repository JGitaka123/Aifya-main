"use client";

import { useQuery, useQueryClient, type UseQueryOptions, type UseQueryResult } from "@tanstack/react-query";
import { useEffect } from "react";
import { cacheQueryData, getCachedQueryData } from "@/lib/offline-store";

/**
 * TanStack Query wrapper that caches results to IndexedDB for offline access.
 * Per CLAUDE.md: every data hook must cache to IndexedDB via useOfflineQuery.
 *
 * @param options - Standard TanStack Query options
 * @returns Query result, falls back to IndexedDB when offline
 */
export function useOfflineQuery<TData>(
  options: UseQueryOptions<TData>
): UseQueryResult<TData> {
  const queryClient = useQueryClient();
  const cacheKey = JSON.stringify(options.queryKey);

  const query = useQuery<TData>({
    ...options,
    placeholderData: undefined,
    initialData: undefined,
  });

  // Cache successful data to IndexedDB
  useEffect(() => {
    if (query.data !== undefined) {
      cacheQueryData(cacheKey, query.data).catch(() => {
        // Silently fail — offline cache is best-effort
      });
    }
  }, [query.data, cacheKey]);

  // If query fails (offline), try IndexedDB fallback
  useEffect(() => {
    if (query.isError && !navigator.onLine) {
      getCachedQueryData<TData>(cacheKey).then((cached) => {
        if (cached !== undefined && options.queryKey) {
          queryClient.setQueryData(options.queryKey, cached);
        }
      }).catch(() => {
        // Silently fail
      });
    }
  }, [query.isError, cacheKey, queryClient, options.queryKey]);

  return query;
}
