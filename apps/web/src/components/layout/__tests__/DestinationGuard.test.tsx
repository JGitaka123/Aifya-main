import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { session } = vi.hoisted(() => ({
  session: {
    pathname: "/en",
    roles: undefined as readonly string[] | undefined,
    permissions: undefined as readonly string[] | undefined,
  },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => session.pathname,
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/hooks/usePermissions", () => ({
  usePermissions: () => {
    const granted = session.permissions ? new Set(session.permissions) : null;
    return {
      permissions: session.permissions,
      roles: session.roles,
      hasPermission: (permission?: string) =>
        !permission || !granted || granted.has(permission),
      hasAnyPermission: (required: readonly string[]) =>
        required.length === 0 || !granted
          ? true
          : required.some((permission) => granted.has(permission)),
      canSeeClinical: true,
    };
  },
}));

import { DestinationGuard } from "../DestinationGuard";

const PAGE = <p>the page</p>;

const signIn = (
  pathname: string,
  roles?: readonly string[],
  permissions?: readonly string[],
) => {
  session.pathname = pathname;
  session.roles = roles;
  session.permissions = permissions;
};

const renderAt = (
  pathname: string,
  roles?: readonly string[],
  permissions?: readonly string[],
) => {
  signIn(pathname, roles, permissions);
  render(<DestinationGuard>{PAGE}</DestinationGuard>);
};

describe("DestinationGuard", () => {
  afterEach(() => {
    cleanup();
    signIn("/en");
  });

  it("refuses a doctor who types the pharmacy URL by hand", () => {
    renderAt("/en/pharmacy", ["doctor"], [
      "clinical.view",
      "opd.view",
      "patients.view",
      "pharmacy.view",
    ]);

    expect(screen.getByRole("alert")).toHaveAttribute(
      "data-destination",
      "pharmacy",
    );
    expect(screen.queryByText("the page")).not.toBeInTheDocument();
  });

  it("lets the pharmacist into the same URL", () => {
    renderAt("/en/pharmacy", ["pharmacist"], ["pharmacy.view"]);

    expect(screen.getByText("the page")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("opens a lab result the consultation handed on", () => {
    renderAt("/en/laboratory/9f1c", ["doctor"], [
      "laboratory.view",
      "patients.view",
    ]);

    expect(screen.getByText("the page")).toBeInTheDocument();
  });

  it("still refuses a room the user has no permission for, record or not", () => {
    renderAt("/en/settings/team", ["hr_officer"], ["hr.view"]);

    expect(screen.getByRole("alert")).toHaveAttribute(
      "data-destination",
      "settings",
    );
  });

  it("lets an HR admin into the settings records", () => {
    renderAt("/en/settings/team", ["hr_admin"], ["hr.view", "settings.manage"]);

    expect(screen.getByText("the page")).toBeInTheDocument();
  });

  it("refuses a nurse the registration desk", () => {
    renderAt("/en/patients/register", ["nurse"], [
      "clinical.view",
      "patients.view",
    ]);

    expect(screen.getByRole("alert")).toHaveAttribute(
      "data-destination",
      "registration",
    );
  });

  it("lets the front desk register", () => {
    renderAt("/en/patients/register", ["receptionist"], ["patients.register"]);

    expect(screen.getByText("the page")).toBeInTheDocument();
  });

  it("leaves a route that is not a destination to Next.js", () => {
    renderAt("/en/patient-support", ["doctor"], ["patients.view"]);

    expect(screen.getByText("the page")).toBeInTheDocument();
  });

  it("does not flash a refusal before the session reports its roles", () => {
    renderAt("/en/pharmacy");

    expect(screen.getByText("the page")).toBeInTheDocument();
  });
});
