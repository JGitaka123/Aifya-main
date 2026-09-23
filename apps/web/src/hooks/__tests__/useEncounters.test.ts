import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPatch = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
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

import {
  useOPDQueue,
  useEncounter,
  useEncounterVitals,
  useEncounterDiagnoses,
  useEncounterPrescriptions,
  useEncounterLabOrders,
} from "../useEncounters";

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

describe("useOPDQueue", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches the OPD queue", async () => {
    const data = { items: [], total: 0 };
    mockGet.mockResolvedValue(data);

    const { result } = renderHook(() => useOPDQueue(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(data);
    expect(mockGet).toHaveBeenCalledWith("/encounters/queue", {});
  });

  it("passes status filter", async () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });

    const { result } = renderHook(() => useOPDQueue("in_progress"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/queue", {
      status: "in_progress",
    });
  });
});

describe("useEncounter", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches a single encounter", async () => {
    const encounter = { id: "enc-1", patient_id: "p-1", status: "in_progress" };
    mockGet.mockResolvedValue(encounter);

    const { result } = renderHook(() => useEncounter("enc-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/enc-1");
  });

  it("does not fetch when encounterId is empty", () => {
    const { result } = renderHook(() => useEncounter(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});

describe("useEncounterVitals", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches vitals for an encounter", async () => {
    const vitals = [{ temperature: 37.2, pulse_rate: 72 }];
    mockGet.mockResolvedValue(vitals);

    const { result } = renderHook(() => useEncounterVitals("enc-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/enc-1/vitals");
    expect(result.current.data).toEqual(vitals);
  });
});

describe("useEncounterDiagnoses", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches diagnoses for an encounter", async () => {
    const diagnoses = [{ icd10_code: "J06.9", diagnosis_type: "primary" }];
    mockGet.mockResolvedValue(diagnoses);

    const { result } = renderHook(() => useEncounterDiagnoses("enc-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/enc-1/diagnoses");
  });
});

describe("useEncounterPrescriptions", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches prescriptions for an encounter", async () => {
    mockGet.mockResolvedValue([]);

    const { result } = renderHook(() => useEncounterPrescriptions("enc-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/enc-1/prescriptions");
  });
});

describe("useEncounterLabOrders", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("fetches lab orders for an encounter", async () => {
    mockGet.mockResolvedValue([]);

    const { result } = renderHook(() => useEncounterLabOrders("enc-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGet).toHaveBeenCalledWith("/encounters/enc-1/lab-orders");
  });

  it("does not fetch when encounterId is empty", () => {
    const { result } = renderHook(() => useEncounterLabOrders(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });
});
