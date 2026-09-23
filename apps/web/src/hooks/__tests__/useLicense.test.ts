import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

const mockApiFetch = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

vi.mock("@/lib/auth/beta", () => ({
  BETA_PUBLIC_ACCESS_ENABLED: false,
  getBetaLicense: vi.fn(),
  getBetaModuleAccess: vi.fn(),
  getBetaPatientLimit: vi.fn(),
}));

vi.mock("@/lib/offline-store", () => ({
  cacheQueryData: vi.fn().mockResolvedValue(undefined),
  getCachedQueryData: vi.fn().mockResolvedValue(undefined),
}));

import { useLicense, usePatientLimit, useModuleAccess } from "../useLicense";

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

describe("useLicense", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("fetches license validation", async () => {
    const license = {
      valid: true,
      tier: "professional",
      modules: ["patients", "encounters", "pharmacy"],
    };
    mockApiFetch.mockResolvedValue(license);

    const { result } = renderHook(() => useLicense(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(license);
    expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/licensing/license");
  });
});

describe("usePatientLimit", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("fetches patient limit info", async () => {
    const limit = { current: 45, max: 500, reached: false };
    mockApiFetch.mockResolvedValue(limit);

    const { result } = renderHook(() => usePatientLimit(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(limit);
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/licensing/license/patient-limit"
    );
  });
});

describe("useModuleAccess", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("checks module access", async () => {
    const access = { module: "clinical_trials", allowed: true };
    mockApiFetch.mockResolvedValue(access);

    const { result } = renderHook(() => useModuleAccess("clinical_trials"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(access);
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/licensing/license/module/clinical_trials"
    );
  });

  it("does not fetch when module is empty", () => {
    const { result } = renderHook(() => useModuleAccess(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockApiFetch).not.toHaveBeenCalled();
  });
});
