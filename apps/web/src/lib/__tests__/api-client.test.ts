import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiClient, ApiError } from "../api-client";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
});

describe("ApiClient", () => {
  describe("get", () => {
    it("makes a GET request", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });

      await apiClient.get("/patients");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/patients"),
        expect.objectContaining({ method: "GET", credentials: "include" })
      );
    });

    it("appends query params", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });

      await apiClient.get("/patients", { q: "John", page: "1" });

      const url = mockFetch.mock.calls[0]?.[0] as string;
      expect(url).toContain("q=John");
      expect(url).toContain("page=1");
    });

    it("returns parsed JSON", async () => {
      const data = { id: "123", first_name: "Wanjiku" };
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(data),
      });

      const result = await apiClient.get<typeof data>("/patients/123");
      expect(result).toEqual(data);
    });
  });

  describe("post", () => {
    it("makes a POST request with body", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ id: "new-id" }),
      });

      await apiClient.post("/patients", { first_name: "Grace" });

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(opts.method).toBe("POST");
      expect(opts.body).toBe(JSON.stringify({ first_name: "Grace" }));
    });

    it("includes idempotency key header when provided", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve({ id: "new-id" }),
      });

      await apiClient.post("/patients", {}, "idem-key-123");

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = opts.headers as Record<string, string>;
      expect(headers["X-Idempotency-Key"]).toBe("idem-key-123");
    });

    it("omits idempotency key when not provided", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve({}),
      });

      await apiClient.post("/patients", {});

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = opts.headers as Record<string, string>;
      expect(headers["X-Idempotency-Key"]).toBeUndefined();
    });
  });

  describe("patch", () => {
    it("makes a PATCH request", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ id: "123" }),
      });

      await apiClient.patch("/patients/123", { first_name: "Updated" });

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(opts.method).toBe("PATCH");
    });

    it("includes idempotency key for patch", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });

      await apiClient.patch("/patients/123", {}, "patch-idem");

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = opts.headers as Record<string, string>;
      expect(headers["X-Idempotency-Key"]).toBe("patch-idem");
    });
  });

  describe("error handling", () => {
    it("throws ApiError on non-ok response", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "Patient not found" }),
      });

      try {
        await apiClient.get("/patients/999");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(404);
        expect((error as ApiError).message).toBe("Patient not found");
      }
    });

    it("falls back to statusText when json fails", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("parse error")),
      });

      try {
        await apiClient.get("/patients");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).message).toBe("Internal Server Error");
      }
    });

    it("returns undefined for 204", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 204,
      });

      const result = await apiClient.get("/patients/123");
      expect(result).toBeUndefined();
    });
  });

  describe("credentials", () => {
    it("always sends credentials: include", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });

      await apiClient.get("/patients");

      const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(opts.credentials).toBe("include");
    });
  });
});
