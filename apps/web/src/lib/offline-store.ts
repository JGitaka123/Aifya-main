import { openDB, type IDBPDatabase } from "idb";

const DB_NAME = "aifya-offline";
const DB_VERSION = 2;

export const MUTATION_QUEUE_CHANGED_EVENT = "aifya:mutation-queue-changed";

export interface MutationQueueItem {
  id: string;
  url: string;
  method: string;
  body: string;
  headers: Record<string, string>;
  createdAt: string;
  retries: number;
  lastAttemptAt?: string;
  lastError?: string;
}

function notifyQueueChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(MUTATION_QUEUE_CHANGED_EVENT));
  }
}

/**
 * Open the IndexedDB database for offline storage.
 * @returns IDB database instance
 */
async function getDB(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("query-cache")) {
        db.createObjectStore("query-cache");
      }
      if (!db.objectStoreNames.contains("mutation-queue")) {
        const store = db.createObjectStore("mutation-queue", {
          keyPath: "id",
        });
        store.createIndex("createdAt", "createdAt");
      }
      if (!db.objectStoreNames.contains("mutation-dead-letter")) {
        db.createObjectStore("mutation-dead-letter", { keyPath: "id" });
      }
    },
  });
}

/**
 * Cache a query response for offline access.
 * @param key - Cache key (typically the query key)
 * @param data - Data to cache
 */
export async function cacheQueryData(key: string, data: unknown): Promise<void> {
  const db = await getDB();
  await db.put("query-cache", { data, cachedAt: new Date().toISOString() }, key);
}

/**
 * Retrieve cached query data.
 * @param key - Cache key
 * @returns Cached data or undefined
 */
export async function getCachedQueryData<T>(key: string): Promise<T | undefined> {
  const db = await getDB();
  const result = await db.get("query-cache", key);
  return result?.data as T | undefined;
}

/**
 * Queue a mutation for later sync when offline.
 * @param item - Mutation details
 */
export async function queueMutation(
  item: Omit<MutationQueueItem, "retries">
): Promise<void> {
  const db = await getDB();
  await db.put("mutation-queue", { ...item, retries: 0 });
  notifyQueueChanged();
}

/**
 * Get all pending mutations in creation order.
 * @returns Array of queued mutations
 */
export async function getPendingMutations(): Promise<MutationQueueItem[]> {
  const db = await getDB();
  return db.getAllFromIndex("mutation-queue", "createdAt");
}

/**
 * Remove a mutation from the queue after successful sync.
 * @param id - Mutation ID
 */
export async function removeMutation(id: string): Promise<void> {
  const db = await getDB();
  await db.delete("mutation-queue", id);
  notifyQueueChanged();
}

/**
 * Retain a failed mutation and record its latest retry details.
 * Clinical writes are never silently discarded after replay failures.
 * @param id - Mutation ID
 * @param error - Human-readable failure reason
 */
export async function updateMutationFailure(
  id: string,
  error: string
): Promise<void> {
  const db = await getDB();
  const mutation = (await db.get(
    "mutation-queue",
    id
  )) as MutationQueueItem | undefined;

  if (!mutation) return;

  await db.put("mutation-queue", {
    ...mutation,
    retries: mutation.retries + 1,
    lastAttemptAt: new Date().toISOString(),
    lastError: error,
  });
  notifyQueueChanged();
}

/**
 * Increment a queued mutation's retry counter.
 * @param id - Mutation ID
 * @returns The new retry count (0 if the mutation no longer exists)
 */
export async function incrementMutationRetries(id: string): Promise<number> {
  const db = await getDB();
  const item = (await db.get("mutation-queue", id)) as
    | MutationQueueItem
    | undefined;
  if (!item) return 0;
  const retries = (item.retries ?? 0) + 1;
  await db.put("mutation-queue", { ...item, retries });
  return retries;
}

/**
 * Move a permanently failed mutation to the dead-letter store so clinical
 * data is never silently discarded — it stays inspectable/recoverable.
 * @param id - Mutation ID
 * @param reason - Why the mutation was given up on (e.g. HTTP status)
 */
export async function deadLetterMutation(
  id: string,
  reason: string
): Promise<void> {
  const db = await getDB();
  const item = (await db.get("mutation-queue", id)) as
    | MutationQueueItem
    | undefined;
  if (!item) return;
  await db.put("mutation-dead-letter", {
    ...item,
    failedAt: new Date().toISOString(),
    reason,
  });
  await db.delete("mutation-queue", id);
}
