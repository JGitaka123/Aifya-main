import { patientCreateSchema, type PatientCreateFormData } from "@/lib/validations/patient";

/**
 * Bulk patient import (D11). Parses a CSV into validated patient rows,
 * reusing `patientCreateSchema` so the same required-field, DOB (D8) and
 * format rules as the single-registration form apply to every row. Invalid
 * rows are reported with a 1-based line number and never imported.
 */

/** Columns accepted in the import CSV (order-independent; header-driven). */
export const PATIENT_IMPORT_COLUMNS = [
  "first_name",
  "middle_name",
  "last_name",
  "date_of_birth",
  "gender",
  "national_id",
  "phone_number",
  "county",
  "sub_county",
  "next_of_kin_name",
  "next_of_kin_phone",
  "insurance_provider",
  "sha_number",
  "allergies",
] as const;

export interface PatientBulkParseResult {
  rows: PatientCreateFormData[];
  errors: string[];
}

/** Split a single CSV line, honoring simple double-quoted fields. */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out.map((v) => v.trim());
}

/**
 * Parse and validate a patient-import CSV.
 *
 * @param text - Raw CSV text (first line is the header row)
 * @returns Validated rows plus per-row error messages
 */
export function parsePatientCsv(text: string): PatientBulkParseResult {
  const lines = text.trim().split(/\r?\n/);
  const headerLine = lines[0];
  if (!headerLine) {
    return { rows: [], errors: ["CSV header row required"] };
  }

  const headers = splitCsvLine(headerLine).map((h) => h.replace(/"/g, ""));
  const rows: PatientCreateFormData[] = [];
  const errors: string[] = [];

  lines.slice(1).forEach((line, index) => {
    if (!line.trim()) return;
    const lineNo = index + 2; // header is line 1

    const values = splitCsvLine(line);
    const raw = headers.reduce<Record<string, string>>((acc, header, i) => {
      acc[header] = values[i] ?? "";
      return acc;
    }, {});

    // Build a candidate; blank optional fields become undefined so schema
    // `.optional()` accepts them rather than failing on "".
    const candidate: Record<string, unknown> = {
      first_name: raw["first_name"] ?? "",
      middle_name: raw["middle_name"] || undefined,
      last_name: raw["last_name"] ?? "",
      date_of_birth: raw["date_of_birth"] ?? "",
      gender: (raw["gender"] || "").toLowerCase() || undefined,
      national_id: raw["national_id"] || undefined,
      phone_number: raw["phone_number"] ?? "",
      county: raw["county"] || undefined,
      sub_county: raw["sub_county"] || undefined,
      next_of_kin_name: raw["next_of_kin_name"] || undefined,
      next_of_kin_phone: raw["next_of_kin_phone"] || undefined,
      insurance_provider: raw["insurance_provider"] || undefined,
      sha_number: raw["sha_number"] || undefined,
      // Allergies are semicolon-separated within the cell (commas delimit columns).
      allergies: raw["allergies"]
        ? raw["allergies"]
            .split(";")
            .map((s) => s.trim())
            .filter(Boolean)
        : undefined,
    };

    const parsed = patientCreateSchema.safeParse(candidate);
    if (!parsed.success) {
      const msg = parsed.error.issues
        .map((i) => `${i.path.join(".") || "row"}: ${i.message}`)
        .join("; ");
      errors.push(`Row ${lineNo}: ${msg}`);
      return;
    }
    rows.push(parsed.data);
  });

  return { rows, errors };
}

/** CSV header + example row for the downloadable template. */
export function patientImportTemplate(): string {
  const header = PATIENT_IMPORT_COLUMNS.join(",");
  const example = [
    "Wanjiku",
    "Njeri",
    "Kamau",
    "1990-05-15",
    "female",
    "29384756",
    "0712345678",
    "Nairobi",
    "Westlands",
    "John Kamau",
    "0723456789",
    "SHA",
    "SHA-1234567",
    "Penicillin;Sulfa",
  ].join(",");
  return `${header}\n${example}`;
}
