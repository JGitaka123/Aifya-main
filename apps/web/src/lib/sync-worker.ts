import {
  getPendingMutations,
  removeMutation,
  updateMutationFailure,
} from "./offline-store";

/**
 * Offline sync worker — replays queued mutations when connectivity returns.
 * Clinical writes remain queued until the server accepts them or confirms a
 * duplicate idempotency key.
 */

let isSyncing = false;

export const SYNC_STATUS_EVENT = "aifya:sync-status";

export type SyncPhase = "idle" | "syncing" | "success" | "error";

export interface SyncStatus {
  phase: SyncPhase;
  pendingCount: number;
  syncedCount: number;
}

function publishSyncStatus(status: SyncStatus): void {
  window.dispatchEvent(
    new CustomEvent<SyncStatus>(SYNC_STATUS_EVENT, { detail: status })
  );
}

function responseFailureMessage(response: Response): string {
  return `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ""}`;
}

/**
 * Process all pending offline mutations in FIFO order.
 * Failed writes are retained for retry and surfaced to the clinical user.
 * @returns Number of successfully synced mutations
 */
export async function syncPendingMutations(): Promise<number> {
  if (isSyncing || !navigator.onLine) return 0;

  isSyncing = true;
  let synced = 0;
  let failed = false;

  try {
    const pending = await getPendingMutations();

    if (pending.length === 0) {
      publishSyncStatus({ phase: "idle", pendingCount: 0, syncedCount: 0 });
      return 0;
    }

    publishSyncStatus({
      phase: "syncing",
      pendingCount: pending.length,
      syncedCount: 0,
    });

    for (const mutation of pending) {
      try {
        // Auth rides on the httpOnly session cookie (credentials: include);
        // JS can't read that token, so no Authorization header is set.
        const headers: Record<string, string> = { ...mutation.headers };
        headers["X-Idempotency-Key"] ??= mutation.id;

        const response = await fetch(mutation.url, {
          method: mutation.method,
          headers,
          body: mutation.body,
          credentials: "include",
        });

        if (response.ok || response.status === 409) {
          await removeMutation(mutation.id);
          synced++;
          continue;
        }

        failed = true;
        await updateMutationFailure(
          mutation.id,
          responseFailureMessage(response)
        );
        // Preserve FIFO ordering for dependent clinical writes.
        break;
      } catch (error) {
        failed = true;
        const message =
          error instanceof Error ? error.message : "Network request failed";
        await updateMutationFailure(mutation.id, message);
        break;
      }
    }

    const remaining = await getPendingMutations();
    publishSyncStatus({
      phase: failed ? "error" : "success",
      pendingCount: remaining.length,
      syncedCount: synced,
    });
  } finally {
    isSyncing = false;
  }

  return synced;
}

/**
 * Initialize the sync worker and begin listening for connectivity changes.
 * @returns Cleanup function for the online listener and periodic timer
 */
export function initSyncWorker(): () => void {
  const handleOnline = (): void => {
    void syncPendingMutations();
  };

  window.addEventListener("online", handleOnline);

  const intervalId = window.setInterval(() => {
    if (navigator.onLine) {
      void syncPendingMutations();
    }
  }, 30_000);

  if (navigator.onLine) {
    void syncPendingMutations();
  }

  return () => {
    window.removeEventListener("online", handleOnline);
    window.clearInterval(intervalId);
  };
}
