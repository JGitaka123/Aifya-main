import { beforeEach, describe, expect, it, vi } from "vitest";
import { idempotentApiFetch } from "../idempotentApiFetch";

const mockApiFetch = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

vi.mock("@/lib/utils", () => ({
  generateId: () => "request-id",
}));

describe("idempotentApiFetch", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
    mockApiFetch.mockResolvedValue({ ok: true });
  });

  it("adds an idempotency key and preserves existing headers", async () => {
    await idempotentApiFetch("/api/v1/trials", {
      method: "POST",
      body: JSON.stringify({ title: "Trial" }),
      headers: { "X-Request-Source": "test" },
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/v1/trials", {
      method: "POST",
      body: JSON.stringify({ title: "Trial" }),
      headers: {
        "X-Request-Source": "test",
        "X-Idempotency-Key": "request-id",
      },
    });
  });
});
