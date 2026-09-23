import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock("@/lib/offline-store", () => ({
  cacheQueryData: vi.fn().mockResolvedValue(undefined),
  getCachedQueryData: vi.fn().mockResolvedValue(undefined),
  queueMutation: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/utils", () => ({
  generateId: () => "test-uuid",
}));

import { usePatientSearch, usePatient } from "../usePatients";

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

describe("usePatientSearch", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches patients with default params", async () => {
    const data = { items: [], total: 0, page: 1, page_size: 20 };
    mockGet.mockResolvedValue(data);

    const { result } = renderHook(() => usePatientSearch(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(data);
    expect(mockGet).toHaveBeenCalledWith(
      "/patients",
      expect.objectContaining({ page: "1", page_size: "20" })
    );
  });

  it("passes search query parameter", async () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });

    const { result } = renderHook(() => usePatientSearch("Wanjiku"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith(
      "/patients",
      expect.objectContaining({ q: "Wanjiku" })
    );
  });

  it("passes pagination params", async () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });

    const { result } = renderHook(() => usePatientSearch(undefined, 3, 50), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith(
      "/patients",
      expect.objectContaining({ page: "3", page_size: "50" })
    );
  });
});

describe("usePatient", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches a single patient by ID", async () => {
    const patient = { id: "abc", first_name: "Grace", last_name: "Achieng" };
    mockGet.mockResolvedValue(patient);

    const { result } = renderHook(() => usePatient("abc"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(patient);
    expect(mockGet).toHaveBeenCalledWith("/patients/abc");
  });

  it("does not fetch when patientId is empty", () => {
    const { result } = renderHook(() => usePatient(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});
