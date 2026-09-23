import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MutationQueueItem } from "./offline-store";

const mockGetPendingMutations = vi.fn<() => Promise<MutationQueueItem[]>>();
const mockRemoveMutation = vi.fn<(id: string) => Promise<void>>();
const mockUpdateMutationFailure = vi.fn<
  (id: string, error: string) => Promise<void>
>();

vi.mock("./offline-store", () => ({
  getPendingMutations: () => mockGetPendingMutations(),
  removeMutation: (id: string) => mockRemoveMutation(id),
  updateMutationFailure: (id: string, error: string) =>
    mockUpdateMutationFailure(id, error),
}));

import {
  initSyncWorker,
  SYNC_STATUS_EVENT,
  syncPendingMutations,
  type SyncStatus,
} from "./sync-worker";

const QUEUED_MUTATION: MutationQueueItem = {
  id: "offline-write-1",
  url: "/api/v1/patients",
  method: "POST",
  body: JSON.stringify({ firstName: "Amina" }),
  headers: { "Content-Type": "application/json" },
  createdAt: "2026-07-15T10:00:00.000Z",
  retries: 0,
};

function setOnline(value: boolean): void {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    get: () => value,
  });
}

describe("syncPendingMutations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setOnline(true);
    localStorage.clear();
    mockRemoveMutation.mockResolvedValue(undefined);
    mockUpdateMutationFailure.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("replays queued writes with an idempotency key and removes accepted writes", async () => {
    mockGetPendingMutations
      .mockResolvedValueOnce([QUEUED_MUTATION])
      .mockResolvedValueOnce([]);
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, { status: 201 })
    );
    vi.stubGlobal("fetch", fetchMock);

    const statuses: SyncStatus[] = [];
    const handleStatus = (event: Event): void => {
      statuses.push((event as CustomEvent<SyncStatus>).detail);
    };
    window.addEventListener(SYNC_STATUS_EVENT, handleStatus);

    const synced = await syncPendingMutations();

    window.removeEventListener(SYNC_STATUS_EVENT, handleStatus);
    expect(synced).toBe(1);
    expect(mockRemoveMutation).toHaveBeenCalledWith("offline-write-1");
    expect(mockUpdateMutationFailure).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/patients",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          "X-Idempotency-Key": "offline-write-1",
        }),
      })
    );
    expect(statuses.map((status) => status.phase)).toEqual([
      "syncing",
      "success",
    ]);
  });

  it("retains failed clinical writes and records the failure", async () => {
    mockGetPendingMutations
      .mockResolvedValueOnce([QUEUED_MUTATION])
      .mockResolvedValueOnce([QUEUED_MUTATION]);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(null, { status: 503, statusText: "Unavailable" })
      )
    );

    const synced = await syncPendingMutations();

    expect(synced).toBe(0);
    expect(mockRemoveMutation).not.toHaveBeenCalled();
    expect(mockUpdateMutationFailure).toHaveBeenCalledWith(
      "offline-write-1",
      "HTTP 503 Unavailable"
    );
  });

  it("treats an idempotent duplicate as successfully synchronized", async () => {
    mockGetPendingMutations
      .mockResolvedValueOnce([QUEUED_MUTATION])
      .mockResolvedValueOnce([]);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 409 }))
    );

    await expect(syncPendingMutations()).resolves.toBe(1);
    expect(mockRemoveMutation).toHaveBeenCalledWith("offline-write-1");
  });
});

describe("initSyncWorker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    setOnline(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns cleanup that removes its online listener and interval", () => {
    const removeListenerSpy = vi.spyOn(window, "removeEventListener");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");

    const cleanup = initSyncWorker();
    cleanup();

    expect(removeListenerSpy).toHaveBeenCalledWith(
      "online",
      expect.any(Function)
    );
    expect(clearIntervalSpy).toHaveBeenCalledOnce();
  });
});
