import { describe, expect, it } from "vitest";

import { parsePatientCsv, patientImportTemplate } from "../patientBulkImport";

/**
 * D11 regression: bulk patient import parses valid rows and reports per-row
 * errors, reusing the single-form validation (required fields + DOB rules).
 */
describe("parsePatientCsv (D11)", () => {
  it("parses valid rows from the template", () => {
    const { rows, errors } = parsePatientCsv(patientImportTemplate());
    expect(errors).toEqual([]);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.first_name).toBe("Wanjiku");
    expect(rows[0]?.gender).toBe("female");
  });

  it("reports a per-row error for a missing required field", () => {
    const csv = [
      "first_name,last_name,date_of_birth,gender,phone_number",
      ",Kamau,1990-05-15,female,0712345678", // missing first_name
    ].join("\n");
    const { rows, errors } = parsePatientCsv(csv);
    expect(rows).toHaveLength(0);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toMatch(/^Row 2:/);
  });

  it("rejects a future date of birth (D8 rule applies per row)", () => {
    const csv = [
      "first_name,last_name,date_of_birth,gender,phone_number",
      "Ada,Test,2999-01-01,female,0712345678",
    ].join("\n");
    const { rows, errors } = parsePatientCsv(csv);
    expect(rows).toHaveLength(0);
    expect(errors[0]).toMatch(/Row 2:/);
  });

  it("imports the valid rows and skips only the invalid ones", () => {
    const csv = [
      "first_name,last_name,date_of_birth,gender,phone_number",
      "Grace,Achieng,1995-07-01,female,0701234567",
      ",Bad,1990-01-01,male,0700000000",
      "Peter,Otieno,1988-03-03,male,0722222222",
    ].join("\n");
    const { rows, errors } = parsePatientCsv(csv);
    expect(rows).toHaveLength(2);
    expect(errors).toHaveLength(1);
  });

  it("returns a header error for empty input", () => {
    const { rows, errors } = parsePatientCsv("");
    expect(rows).toEqual([]);
    expect(errors[0]).toMatch(/header/i);
  });
});
