import { z } from "zod";

/**
 * Coerce the empty-string value that an unselected `<select>` or empty
 * `<input>` emits into `null`, so genuinely-optional fields accept "not set"
 * instead of failing enum/number validation and silently blocking the submit
 * button (defect D4).
 */
export const emptyToNull = (v: unknown) => (v === "" ? null : v);

/** Zod schema for the lab result entry form. */
export const resultEntrySchema = z.object({
  result_value: z.string().min(1, "Result value is required"),
  result_numeric: z.preprocess(
    emptyToNull,
    z.coerce.number().nullable().optional(),
  ),
  result_unit: z.string().nullable().optional(),
  reference_range: z.string().nullable().optional(),
  // Interpretation is genuinely optional: the "—" option emits "", which must
  // resolve to null rather than fail the enum and no-op the submit (D4).
  interpretation: z.preprocess(
    emptyToNull,
    z.enum(["normal", "abnormal", "critical", "inconclusive"]).nullable().optional(),
  ),
  is_abnormal: z.boolean().optional(),
  notes: z.string().nullable().optional(),
  method: z.string().nullable().optional(),
});

export type ResultEntryFormData = z.infer<typeof resultEntrySchema>;
