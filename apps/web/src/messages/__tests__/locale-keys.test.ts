import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import en from "../en.json";
import sw from "../sw.json";
import { NAV_ITEMS } from "../../lib/navigation";

/**
 * D9 guard: locale files must be structurally complete so no raw dotted
 * translation key (e.g. `opd.prescriptionStatus.pending`) ever leaks to the
 * UI. If a key exists in one locale but not the other, a `t()` call renders
 * the raw key in the missing locale — this test fails the build first.
 */

function flattenKeys(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object") return [prefix];
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flattenKeys(v, prefix ? `${prefix}.${k}` : k),
  );
}

describe("locale key parity", () => {
  it("en and sw expose the exact same key set", () => {
    const enKeys = new Set(flattenKeys(en));
    const swKeys = new Set(flattenKeys(sw));

    const missingInSw = [...enKeys].filter((k) => !swKeys.has(k)).sort();
    const missingInEn = [...swKeys].filter((k) => !enKeys.has(k)).sort();

    expect(missingInSw, `keys missing in sw.json: ${missingInSw.join(", ")}`).toEqual([]);
    expect(missingInEn, `keys missing in en.json: ${missingInEn.join(", ")}`).toEqual([]);
  });
});

describe("clinical status labels are translated", () => {
  // Must match the backend enums (prescription.status, encounter.billing_status).
  const prescriptionStatuses = [
    "pending",
    "dispensed",
    "partially_dispensed",
    "cancelled",
    "on_hold",
  ];
  const billingStatuses = ["pending", "billed", "paid", "waived"];

  for (const locale of [
    { name: "en", data: en },
    { name: "sw", data: sw },
  ]) {
    it(`${locale.name}: all prescription/billing statuses have labels`, () => {
      const data = locale.data as {
        opd?: {
          prescriptionStatus?: Record<string, string>;
          billingStatus?: Record<string, string>;
        };
      };
      for (const s of prescriptionStatuses) {
        expect(
          data.opd?.prescriptionStatus?.[s],
          `${locale.name} prescriptionStatus.${s}`,
        ).toBeTruthy();
      }
      for (const s of billingStatuses) {
        expect(
          data.opd?.billingStatus?.[s],
          `${locale.name} billingStatus.${s}`,
        ).toBeTruthy();
      }
    });
  }
});

describe("navigation labels resolve in every locale", () => {
  // The sidebar renders `t(item.key)` inside the `nav` namespace, so a catalog
  // entry without a matching message leaks its raw dotted key (e.g. "nav.pos")
  // into the sidebar. Every NAV_ITEMS key must have a label in both locales.
  for (const locale of [
    { name: "en", data: en },
    { name: "sw", data: sw },
  ]) {
    it(`${locale.name}: every NAV_ITEMS key has a nav label`, () => {
      const nav = (locale.data as { nav?: Record<string, unknown> }).nav ?? {};

      const missing = NAV_ITEMS.map((item) => item.key).filter((key) => {
        const label = nav[key];
        return typeof label !== "string" || label.trim().length === 0;
      });

      expect(
        missing,
        `keys missing from ${locale.name}.json nav: ${missing.join(", ")}`,
      ).toEqual([]);
    });
  }
});

/**
 * JSON.parse keeps the last of a repeated key and silently drops the rest, so
 * the parsed objects above can never reveal a collision. `billing.mpesa` was
 * once both the "M-Pesa" payment label and an object of prompt strings, which
 * made `t("mpesa")` render an object instead of text. Scan the raw files.
 */
function findDuplicateKeys(raw: string): string[] {
  const duplicates: string[] = [];
  let index = 0;

  function skipWhitespace(): void {
    while (index < raw.length && /\s/.test(raw.charAt(index))) index += 1;
  }

  function readString(): string {
    index += 1;
    let value = "";
    while (index < raw.length) {
      if (raw[index] === "\\") {
        value += raw[index + 1];
        index += 2;
      } else if (raw[index] === '"') {
        index += 1;
        return value;
      } else {
        value += raw[index];
        index += 1;
      }
    }
    throw new Error("unterminated string in locale file");
  }

  function readValue(path: string[]): void {
    skipWhitespace();
    const char = raw[index];
    if (char === "{") readObject(path);
    else if (char === "[") readArray(path);
    else if (char === '"') readString();
    else while (index < raw.length && !/[\s,[\]}]/.test(raw.charAt(index))) index += 1;
  }

  function readObject(path: string[]): void {
    index += 1;
    const seen = new Set<string>();
    skipWhitespace();
    if (raw[index] === "}") {
      index += 1;
      return;
    }
    for (;;) {
      skipWhitespace();
      const key = readString();
      const keyPath = [...path, key];
      if (seen.has(key)) duplicates.push(keyPath.join("."));
      seen.add(key);
      skipWhitespace();
      index += 1; // the ":" separator
      readValue(keyPath);
      skipWhitespace();
      if (raw[index] === ",") {
        index += 1;
        continue;
      }
      index += 1; // the closing "}"
      return;
    }
  }

  function readArray(path: string[]): void {
    index += 1;
    skipWhitespace();
    if (raw[index] === "]") {
      index += 1;
      return;
    }
    for (;;) {
      readValue(path);
      skipWhitespace();
      if (raw[index] === ",") {
        index += 1;
        continue;
      }
      index += 1; // the closing "]"
      return;
    }
  }

  readValue([]);
  return duplicates;
}

describe("locale files declare every key once", () => {
  it("the duplicate-key scanner detects a repeated key", () => {
    expect(findDuplicateKeys('{"a":"x","a":{"b":"y"}}')).toEqual(["a"]);
  });

  for (const name of ["en", "sw"] as const) {
    it(`${name}.json has no duplicate keys`, () => {
      const raw = readFileSync(new URL(`../${name}.json`, import.meta.url), "utf8");
      const duplicates = findDuplicateKeys(raw);

      expect(
        duplicates,
        `duplicate keys in ${name}.json: ${duplicates.join(", ")}`,
      ).toEqual([]);
    });
  }
});

describe("billing payment method labels render as text", () => {
  // The payment-method column calls `t(inv.payment_method)`, so every value the
  // backend can store must resolve to a label string, never to an object.
  const methods = ["cash", "mpesa", "insurance", "exemption"];

  for (const locale of [
    { name: "en", data: en },
    { name: "sw", data: sw },
  ]) {
    it(`${locale.name}: every payment method is a translated label`, () => {
      const billing = (locale.data as { billing: Record<string, unknown> }).billing;

      for (const method of methods) {
        const label = billing?.[method];
        expect(
          typeof label,
          `${locale.name}.billing.${method} must be a string`,
        ).toBe("string");
        expect(
          String(label).trim().length,
          `${locale.name}.billing.${method} must not be blank`,
        ).toBeGreaterThan(0);
      }
    });
  }
});
