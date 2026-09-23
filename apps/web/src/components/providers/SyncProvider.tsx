"use client";

import { useEffect } from "react";
import { initSyncWorker } from "@/lib/sync-worker";

/**
 * Initializes the offline sync worker on app mount.
 * @param props.children - Child components
 * @returns Children unchanged
 */
export function SyncProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    return initSyncWorker();
  }, []);

  return <>{children}</>;
}
