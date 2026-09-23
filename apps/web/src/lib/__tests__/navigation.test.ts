import { describe, expect, it } from "vitest";

import {
  getActiveNavigationHref,
  NAV_ITEMS,
  normalizeNavigationPath,
  PRIMARY_COMMAND_HREFS,
} from "../navigation";

describe("navigation catalog", () => {
  it("uses unique keys and destinations", () => {
    const keys = NAV_ITEMS.map((item) => item.key);
    const hrefs = NAV_ITEMS.map((item) => item.href);

    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("keeps every primary command in the canonical catalog", () => {
    const hrefs = new Set(NAV_ITEMS.map((item) => item.href));

    for (const commandHref of PRIMARY_COMMAND_HREFS) {
      expect(hrefs.has(commandHref)).toBe(true);
    }
  });
});

describe("navigation route resolution", () => {
  it.each([
    ["/en", "/"],
    ["/sw/", "/"],
    ["/en/patients", "/patients"],
    ["/sw/finance/reports", "/finance/reports"],
  ])("normalizes %s", (pathname, expected) => {
    expect(normalizeNavigationPath(pathname)).toBe(expected);
  });

  it("selects the most specific parent for nested routes", () => {
    expect(getActiveNavigationHref("/en/finance/reports/monthly")).toBe(
      "/finance/reports",
    );
    expect(getActiveNavigationHref("/sw/hr/payroll/reports/statutory")).toBe(
      "/hr/payroll/reports",
    );
  });

  it("does not match partial path segments", () => {
    expect(getActiveNavigationHref("/en/patient-support")).toBeUndefined();
  });
});
