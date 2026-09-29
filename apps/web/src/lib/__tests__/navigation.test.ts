import { describe, expect, it } from "vitest";

import {
  getActiveNavigationHref,
  isNavigationVisible,
  NAV_ITEMS,
  normalizeNavigationPath,
  PRIMARY_COMMAND_HREFS,
  type NavItem,
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

describe("role destinations", () => {
  const tabsFor = (roles: string[], permissions: string[]): string[] =>
    NAV_ITEMS.filter((item: NavItem) =>
      isNavigationVisible(item, {
        roles,
        hasPermission: (permission?: string) =>
          !permission || permissions.includes(permission),
      }),
    ).map((item) => item.key);

  it("keeps a doctor in the clinical workspace", () => {
    const tabs = tabsFor(["doctor"], [
      "clinical.view",
      "trials.view",
      "emergency.view",
      "ipd.view",
      "knowledge.view",
      "opd.view",
      "patients.view",
    ]);

    expect(tabs).toEqual([
      "dashboard",
      "patients",
      "clinical",
      "opd",
      "ipd",
      "emergency",
      "trials",
      "knowledge",
      "userGuide",
    ]);
  });

  it("keeps a nurse out of the finance and HR desks", () => {
    const tabs = tabsFor(["nurse"], [
      "clinical.view",
      "trials.view",
      "emergency.view",
      "ipd.view",
      "knowledge.view",
      "opd.view",
      "patients.view",
    ]);

    expect(tabs).toContain("consultationRoom");
    expect(tabs).not.toContain("pharmacy");
    expect(tabs).not.toContain("billing");
    expect(tabs).not.toContain("hr");
    expect(tabs).not.toContain("settings");
  });

  it("gives the pharmacist the dispensary and nothing clinical", () => {
    const tabs = tabsFor(["pharmacist"], [
      "pharmacy.view",
      "inventory.view",
      "billing.view",
      "knowledge.view",
      "patients.view",
    ]);

    expect(tabs).toContain("pharmacy");
    expect(tabs).not.toContain("clinical");
    expect(tabs).not.toContain("opd");
  });

  it("gives HR the staff destinations", () => {
    const tabs = tabsFor(["hr_admin"], [
      "analytics.view",
      "appointments.view",
      "communications.view",
      "hr.view",
      "knowledge.view",
      "referrals.view",
      "reports.view",
      "settings.manage",
    ]);

    expect(tabs).toContain("hr");
    expect(tabs).toContain("payroll");
    expect(tabs).toContain("appointments");
    expect(tabs).toContain("reports");
    expect(tabs).toContain("settings");
    expect(tabs).not.toContain("clinical");
    expect(tabs).not.toContain("pharmacy");
  });

  it("lets an administrator reach every destination", () => {
    const everyPermission = NAV_ITEMS.map((item) => item.permission).filter(
      (permission): permission is string => Boolean(permission),
    );

    expect(tabsFor(["facility_admin"], everyPermission)).toEqual(
      NAV_ITEMS.map((item) => item.key),
    );
  });

  it("does not hide a destination from a session that has not loaded", () => {
    const item = NAV_ITEMS.find((candidate) => candidate.key === "pharmacy");

    expect(
      item &&
        isNavigationVisible(item, {
          roles: undefined,
          hasPermission: () => true,
        }),
    ).toBe(true);
  });
});