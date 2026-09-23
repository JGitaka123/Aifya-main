import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useOfflineMutation } from "../useOfflineMutation";

const mockQueueMutation = vi.fn();

vi.mock("@/lib/offline-store", () => ({
  queueMutation: (...args: unknown[]) => mockQueueMutation(...args),
  cacheQueryData: vi.fn().mockResolvedValue(undefined),
  getCachedQueryData: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/utils", () => ({
  generateId: () => "mock-uuid",
}));

function createWrapper(): ({ children }: { children: ReactNode }) => ReactNode {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }): ReactNode {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe("useOfflineMutation", () => {
  beforeEach(() => {
    mockQueueMutation.mockReset();
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => true,
    });
  });

  it("calls mutationFn when online", async () => {
    const mutationFn = vi.fn().mockResolvedValue({ id: "new" });

    const { result } = renderHook(
      () =>
        useOfflineMutation<{ id: string }, { name: string }>(
          { mutationFn },
          { url: "/api/v1/patients", method: "POST" }
        ),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      result.current.mutate({ name: "Test" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mutationFn.mock.calls[0]?.[0]).toEqual({ name: "Test" });
    expect(mockQueueMutation).not.toHaveBeenCalled();
  });

  it("queues mutation when offline", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });
    mockQueueMutation.mockResolvedValue(undefined);

    const mutationFn = vi.fn();

    const { result } = renderHook(
      () =>
        useOfflineMutation<{ name: string }, { name: string }>(
          { mutationFn },
          { url: "/api/v1/patients", method: "POST" }
        ),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      result.current.mutate({ name: "Offline Patient" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mutationFn).not.toHaveBeenCalled();
    expect(mockQueueMutation).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "/api/v1/patients",
        method: "POST",
        body: JSON.stringify({ name: "Offline Patient" }),
      })
    );
  });

  it("returns optimistic data when offline", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });
    mockQueueMutation.mockResolvedValue(undefined);

    const { result } = renderHook(
      () =>
        useOfflineMutation<{ name: string }, { name: string }>(
          { mutationFn: vi.fn() },
          { url: "/api/v1/patients", method: "POST" }
        ),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      result.current.mutate({ name: "Optimistic" });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ name: "Optimistic" });
  });

  it("resolves dynamic replay URLs and removes route-only variables", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      get: () => false,
    });
    mockQueueMutation.mockResolvedValue(undefined);

    const { result } = renderHook(
      () =>
        useOfflineMutation<
          { status: string },
          { invoiceId: string; amount: number }
        >(
          { mutationFn: vi.fn() },
          {
            url: ({ invoiceId }) =>
              `/api/v1/billing/invoices/${invoiceId}/pay`,
            method: "POST",
            body: ({ amount }) => ({ amount }),
          }
        ),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      result.current.mutate({ invoiceId: "invoice-1", amount: 2500 });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockQueueMutation).toHaveBeenCalledWith({
      id: "mock-uuid",
      url: "/api/v1/billing/invoices/invoice-1/pay",
      method: "POST",
      body: JSON.stringify({ amount: 2500 }),
      headers: {
        "Content-Type": "application/json",
        "X-Idempotency-Key": "mock-uuid",
      },
      createdAt: expect.any(String),
    });
  });

  it("throws when no mutationFn and online", async () => {
    const { result } = renderHook(
      () =>
        useOfflineMutation<unknown, { name: string }>(
          {},
          { url: "/api/v1/patients", method: "POST" }
        ),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      result.current.mutate({ name: "Test" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("No mutationFn provided");
  });
});
