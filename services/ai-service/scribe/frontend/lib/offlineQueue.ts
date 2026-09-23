import Dexie, { type Table } from "dexie";

export interface QueuedAction {
  id?: number;
  action: string;
  endpoint: string;
  method: string;
  payload: any;
  createdAt: Date;
  retries: number;
  status: "pending" | "syncing" | "failed";
  errorMessage?: string;
}

class AifyaOfflineDB extends Dexie {
  queue!: Table<QueuedAction>;

  constructor() {
    super("AifyaOfflineDB");
    this.version(1).stores({
      queue: "++id, action, status, createdAt",
    });
  }
}

export const db = new AifyaOfflineDB();

export async function enqueueAction(action: string, endpoint: string, method: string, payload: any) {
  await db.queue.add({
    action,
    endpoint,
    method,
    payload,
    createdAt: new Date(),
    retries: 0,
    status: "pending",
  });
}

export async function getPendingActions(): Promise<QueuedAction[]> {
  return db.queue.where("status").equals("pending").toArray();
}

export async function syncPendingActions(apiBase: string, getHeaders: () => Record<string, string>) {
  const pending = await getPendingActions();
  if (pending.length === 0) return { synced: 0, failed: 0 };

  let synced = 0;
  let failed = 0;

  for (const item of pending) {
    try {
      await db.queue.update(item.id!, { status: "syncing" });

      const res = await fetch(`${apiBase}${item.endpoint}`, {
        method: item.method,
        headers: { "Content-Type": "application/json", ...getHeaders() },
        body: item.method !== "GET" ? JSON.stringify(item.payload) : undefined,
      });

      if (res.ok) {
        await db.queue.delete(item.id!);
        synced++;
      } else {
        const retries = item.retries + 1;
        await db.queue.update(item.id!, {
          status: retries >= 3 ? "failed" : "pending",
          retries,
          errorMessage: `HTTP ${res.status}`,
        });
        failed++;
      }
    } catch (err: any) {
      const retries = item.retries + 1;
      await db.queue.update(item.id!, {
        status: retries >= 3 ? "failed" : "pending",
        retries,
        errorMessage: err.message,
      });
      failed++;
    }
  }

  return { synced, failed };
}

export async function getQueueCount(): Promise<number> {
  return db.queue.where("status").anyOf("pending", "failed").count();
}

export async function clearQueue() {
  await db.queue.clear();
}
