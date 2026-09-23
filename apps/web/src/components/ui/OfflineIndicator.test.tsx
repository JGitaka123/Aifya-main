import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OfflineIndicator } from "./OfflineIndicator";

const mockGetPendingMutations = vi.fn();
const mockSyncPendingMutations = vi.fn();

vi.mock("next-intl", () => ({
  useTranslations: () =>
    (key: string, values?: Record<string, number | string>): string =>
      values?.count === undefined ? key : `${key}:${values.count}`,
}));

vi.mock("@/lib/offline-store", () => ({
  getPendingMutations: () => mockGetPendingMutations(),
  MUTATION_QUEUE_CHANGED_EVENT: "aifya:mutation-queue-changed",
}));

vi.mock("@/lib/sync-worker", () => ({
  SYNC_STATUS_EVENT: "aifya:sync-status",
  syncPendingMutations: () => mockSyncPendingMutations(),
}));

function setOnline(value: boolean): void {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    get: () => value,
  });
}

describe("OfflineIndicator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setOnline(true);
    mockGetPendingMutations.mockResolvedValue([]);
    mockSyncPendingMutations.mockResolvedValue(0);
  });

  it("stays hidden while online with an empty queue", async () => {
    const { container } = render(<OfflineIndicator />);

    await waitFor(() => expect(mockGetPendingMutations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows queued changes without blocking work while offline", async () => {
    setOnline(false);
    mockGetPendingMutations.mockResolvedValue([
      { id: "one" },
      { id: "two" },
    ]);

    render(<OfflineIndicator />);

    expect(await screen.findByText("offline")).toBeInTheDocument();
    expect(screen.getByText("changesWaiting:2")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });

  it("surfaces replay failures and lets the user retry", async () => {
    render(<OfflineIndicator />);
    await waitFor(() => expect(mockGetPendingMutations).toHaveBeenCalled());

    act(() => {
      window.dispatchEvent(
        new CustomEvent("aifya:sync-status", {
          detail: { phase: "error", pendingCount: 1, syncedCount: 0 },
        })
      );
    });

    const retryButton = await screen.findByRole("button", { name: "retrySync" });
    expect(screen.getByRole("alert")).toHaveTextContent("syncNeedsAttention");
    fireEvent.click(retryButton);
    expect(mockSyncPendingMutations).toHaveBeenCalledOnce();
  });
});
