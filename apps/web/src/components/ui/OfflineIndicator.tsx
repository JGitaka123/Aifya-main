"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  WifiOff,
} from "lucide-react";
import {
  getPendingMutations,
  MUTATION_QUEUE_CHANGED_EVENT,
} from "@/lib/offline-store";
import {
  SYNC_STATUS_EVENT,
  syncPendingMutations,
  type SyncStatus,
} from "@/lib/sync-worker";

const INITIAL_STATUS: SyncStatus = {
  phase: "idle",
  pendingCount: 0,
  syncedCount: 0,
};

/**
 * Displays connectivity and durable offline-queue status.
 * Failed clinical writes remain visible and can be retried manually.
 * @returns Connectivity and sync status badge, or null when fully synchronized
 */
export function OfflineIndicator() {
  const t = useTranslations("common");
  const [isOffline, setIsOffline] = useState(false);
  const [status, setStatus] = useState<SyncStatus>(INITIAL_STATUS);

  const refreshPendingCount = useCallback(async (): Promise<void> => {
    const pending = await getPendingMutations();
    setStatus((current) => ({
      ...current,
      pendingCount: pending.length,
    }));
  }, []);

  useEffect(() => {
    setIsOffline(!navigator.onLine);
    void refreshPendingCount();

    const handleOffline = (): void => setIsOffline(true);
    const handleOnline = (): void => setIsOffline(false);
    const handleQueueChanged = (): void => {
      void refreshPendingCount();
    };
    const handleSyncStatus = (event: Event): void => {
      setStatus((event as CustomEvent<SyncStatus>).detail);
    };

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    window.addEventListener(MUTATION_QUEUE_CHANGED_EVENT, handleQueueChanged);
    window.addEventListener(SYNC_STATUS_EVENT, handleSyncStatus);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener(MUTATION_QUEUE_CHANGED_EVENT, handleQueueChanged);
      window.removeEventListener(SYNC_STATUS_EVENT, handleSyncStatus);
    };
  }, [refreshPendingCount]);

  useEffect(() => {
    if (status.phase !== "success") return;

    const timeoutId = window.setTimeout(() => {
      setStatus((current) => ({ ...current, phase: "idle", syncedCount: 0 }));
    }, 4_000);

    return () => window.clearTimeout(timeoutId);
  }, [status.phase]);

  if (!isOffline && status.phase === "idle" && status.pendingCount === 0) {
    return null;
  }

  const waitingText = t("changesWaiting", { count: status.pendingCount });

  if (isOffline) {
    return (
      <div
        className="fixed bottom-4 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-start gap-3 rounded-xl border border-warning/30 bg-card px-4 py-3 text-card-foreground shadow-xl dark:border-warning/40 dark:bg-card"
        role="status"
        aria-live="polite"
      >
        <span className="mt-0.5 rounded-full bg-warning/15 p-2 text-warning">
          <WifiOff className="h-4 w-4" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{t("offline")}</span>
          {status.pendingCount > 0 && (
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {waitingText}
            </span>
          )}
        </span>
      </div>
    );
  }

  if (status.phase === "syncing") {
    return (
      <div
        className="fixed bottom-4 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-primary/25 bg-card px-4 py-3 text-card-foreground shadow-xl dark:border-primary/40 dark:bg-card"
        role="status"
        aria-live="polite"
      >
        <LoaderCircle
          className="h-5 w-5 animate-spin text-primary"
          aria-hidden="true"
        />
        <span className="text-sm font-semibold">
          {t("syncingChanges", { count: status.pendingCount })}
        </span>
      </div>
    );
  }

  if (status.phase === "success") {
    return (
      <div
        className="fixed bottom-4 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-success/25 bg-card px-4 py-3 text-card-foreground shadow-xl dark:border-success/40 dark:bg-card"
        role="status"
        aria-live="polite"
      >
        <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />
        <span className="text-sm font-semibold">{t("syncComplete")}</span>
      </div>
    );
  }

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-destructive/25 bg-card px-4 py-3 text-card-foreground shadow-xl dark:border-destructive/40 dark:bg-card"
      role="alert"
    >
      <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">
          {t("syncNeedsAttention")}
        </span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {waitingText}
        </span>
      </span>
      <button
        type="button"
        onClick={() => void syncPendingMutations()}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-semibold transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
        {t("retrySync")}
      </button>
    </div>
  );
}
