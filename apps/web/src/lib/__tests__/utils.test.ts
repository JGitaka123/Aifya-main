import { describe, expect, it } from "vitest";
import { cn, formatKES, formatDate, formatDateTime, generateId } from "../utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("px-4", "py-2")).toBe("px-4 py-2");
  });

  it("resolves Tailwind conflicts with last-wins", () => {
    expect(cn("px-4", "px-8")).toBe("px-8");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "text-sm")).toBe("base text-sm");
  });

  it("handles undefined and null", () => {
    expect(cn("base", undefined, null, "end")).toBe("base end");
  });

  it("handles empty input", () => {
    expect(cn()).toBe("");
  });
});

describe("formatKES", () => {
  it("formats zero cents", () => {
    expect(formatKES(0)).toBe("KES 0.00");
  });

  it("formats 100 cents as 1.00", () => {
    expect(formatKES(100)).toBe("KES 1.00");
  });

  it("formats large amounts with commas", () => {
    const result = formatKES(150000);
    expect(result).toContain("KES");
    expect(result).toContain("1,500.00");
  });

  it("formats 50 cents as 0.50", () => {
    expect(formatKES(50)).toBe("KES 0.50");
  });

  it("formats negative amounts", () => {
    const result = formatKES(-5000);
    expect(result).toContain("-50.00");
  });
});

describe("formatDate", () => {
  it("formats an ISO date string", () => {
    const result = formatDate("2026-04-12");
    expect(result).toContain("2026");
    expect(result).toContain("Apr");
    expect(result).toContain("12");
  });

  it("formats a Date object", () => {
    const result = formatDate(new Date("2026-01-15T00:00:00Z"));
    expect(result).toContain("2026");
    expect(result).toContain("Jan");
  });
});

describe("formatDateTime", () => {
  it("formats datetime with time component", () => {
    const result = formatDateTime("2026-04-12T14:30:00Z");
    expect(result).toContain("2026");
    expect(result).toContain("Apr");
  });

  it("formats a Date object with time", () => {
    const result = formatDateTime(new Date("2026-06-01T09:15:00Z"));
    expect(result).toContain("2026");
    expect(result).toContain("Jun");
  });
});

describe("generateId", () => {
  it("returns a string", () => {
    expect(typeof generateId()).toBe("string");
  });

  it("returns a UUID-like format", () => {
    const id = generateId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
    );
  });
});
