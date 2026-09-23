"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { getQueryClient } from "@/lib/query-client";

/**
 * TanStack Query provider for the app.
 * @param props.children - Child components
 * @returns Provider-wrapped children
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
