import { QueryClient } from "@tanstack/react-query";

/**
 * Create a configured QueryClient for the app.
 * @returns QueryClient instance with default options
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        gcTime: 10 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

/**
 * Get the singleton QueryClient for browser use.
 * @returns QueryClient instance
 */
export function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    return makeQueryClient();
  }
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient();
  }
  return browserQueryClient;
}
