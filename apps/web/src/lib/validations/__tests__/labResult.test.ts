import { describe, expect, it } from "vitest";

import { resultEntrySchema } from "../labResult";

/**
 * D4 regression: entering a result with a value but no Interpretation
 * (the "—" option, value "") used to fail the enum and make the submit
 * button silently no-op. The form must now accept an unset interpretation.
 */
describe("resultEntrySchema (D4)", () => {
  it("accepts a result value with interpretation left unset (empty string)", () => {
    const parsed = resultEntrySchema.safeParse({
      result_value: "Positive",
      interpretation: "", // the "—" option emits ""
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      // "" is normalized to null — genuinely optional, not a validation error.
      expect(parsed.data.interpretation).toBeNull();
    }
  });

  it("accepts a result value with no interpretation field at all", () => {
    const parsed = resultEntrySchema.safeParse({ result_value: "4.5" });
    expect(parsed.success).toBe(true);
  });

  it("still accepts a real interpretation value", () => {
    const parsed = resultEntrySchema.safeParse({
      result_value: "12.1",
      interpretation: "critical",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data.interpretation).toBe("critical");
  });

  it("normalizes an empty numeric field to null instead of coercing to 0", () => {
    const parsed = resultEntrySchema.safeParse({
      result_value: "Trace",
      result_numeric: "",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data.result_numeric).toBeNull();
  });

  it("rejects a missing result value with a clear message (never silent)", () => {
    const parsed = resultEntrySchema.safeParse({ result_value: "" });
    expect(parsed.success).toBe(false);
    if (!parsed.success) {
      expect(parsed.error.issues[0]?.message).toMatch(/required/i);
    }
  });
});
