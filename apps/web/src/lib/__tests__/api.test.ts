import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiFetch } from "../api";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
});

describe("apiFetch", () => {
  it("prepends API_BASE for /api/v1 paths", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "123" }),
    });

    await apiFetch("/api/v1/patients");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/patients",
      expect.objectContaining({
        credentials: "include",
      })
    );
  });

  it("does not prepend API_BASE for relative paths", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/api/auth/me");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({
        credentials: "include",
      })
    );
  });

  it("sets Content-Type to application/json", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/api/v1/patients");

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = opts.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("returns parsed JSON on success", async () => {
    const data = { id: "abc", name: "Test" };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(data),
    });

    const result = await apiFetch<typeof data>("/api/v1/patients");
    expect(result).toEqual(data);
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
    });

    const result = await apiFetch("/api/v1/patients/123");
    expect(result).toBeUndefined();
  });

  it("throws on non-ok response with detail", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: () => Promise.resolve({ detail: "Patient not found" }),
    });

    await expect(apiFetch("/api/v1/patients/123")).rejects.toThrow(
      "404: Patient not found"
    );
  });

  it("throws with statusText when json parse fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("parse error")),
    });

    await expect(apiFetch("/api/v1/patients")).rejects.toThrow(
      "500: Internal Server Error"
    );
  });

  it("passes custom headers", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/api/v1/patients", {
      headers: { "X-Idempotency-Key": "idem-123" },
    });

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = opts.headers as Record<string, string>;
    expect(headers["X-Idempotency-Key"]).toBe("idem-123");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("always sends credentials: include", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/api/v1/billing/summary");

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(opts.credentials).toBe("include");
  });
});
