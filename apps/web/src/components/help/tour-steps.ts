/**
 * Onboarding tour step definitions.
 *
 * Each tour targets a different role / module. Selectors use
 * `data-tour` attributes on real DOM elements — keep these stable.
 *
 * To add a new step, add an element with `data-tour="my-step"` somewhere
 * in the app and reference it here.
 */

import type { Config, DriveStep } from "driver.js";

/** Translation key prefix for all tour copy. */
export const TOUR_I18N_NS = "tour";

/** A tour is a named list of steps. */
export interface Tour {
  id: string;
  label: string; // i18n key (relative to `tour.tours`)
  steps: TourStep[];
}

/** Lightweight step shape used pre-translation. */
export interface TourStep {
  /** CSS selector or `data-tour` value (will be wrapped). */
  target: string;
  /** i18n key (relative to `tour.steps`). */
  key: string;
  side?: DriveStep["popover"] extends infer P
    ? P extends { side?: infer S }
      ? S
      : never
    : never;
  align?: DriveStep["popover"] extends infer P
    ? P extends { align?: infer A }
      ? A
      : never
    : never;
}

/** Default driver.js config shared by all tours. */
export const DEFAULT_DRIVER_CONFIG: Partial<Config> = {
  showProgress: true,
  allowClose: true,
  smoothScroll: true,
  overlayOpacity: 0.6,
  stagePadding: 6,
  stageRadius: 8,
  popoverClass: "aifya-tour-popover",
};

/**
 * Welcome tour — runs on first login regardless of role.
 * Introduces sidebar nav, help bot, dark mode, user menu.
 */
export const WELCOME_TOUR: Tour = {
  id: "welcome",
  label: "welcome.label",
  steps: [
    { target: '[data-tour="sidebar"]', key: "welcome.sidebar", side: "right", align: "start" },
    { target: '[data-tour="help-bot"]', key: "welcome.helpBot", side: "left", align: "end" },
    { target: '[data-tour="theme-toggle"]', key: "welcome.themeToggle", side: "right", align: "end" },
    { target: '[data-tour="user-menu"]', key: "welcome.userMenu", side: "right", align: "end" },
  ],
};

/** Finance module tour — for finance_admin / facility_admin / admin. */
export const FINANCE_TOUR: Tour = {
  id: "finance",
  label: "finance.label",
  steps: [
    { target: '[data-tour="finance-link"]', key: "finance.dashboard", side: "right" },
    { target: '[data-tour="billing-link"]', key: "finance.billing", side: "right" },
    { target: '[data-tour="reports-link"]', key: "finance.reports", side: "right" },
    { target: '[data-tour="help-bot"]', key: "finance.helpBot", side: "left", align: "end" },
  ],
};

/** Payroll module tour — for hr_admin / hr_officer / finance_admin. */
export const PAYROLL_TOUR: Tour = {
  id: "payroll",
  label: "payroll.label",
  steps: [
    { target: '[data-tour="payroll-link"]', key: "payroll.dashboard", side: "right" },
    { target: '[data-tour="employees-link"]', key: "payroll.employees", side: "right" },
    { target: '[data-tour="leave-link"]', key: "payroll.leave", side: "right" },
    { target: '[data-tour="payrollReports-link"]', key: "payroll.reports", side: "right" },
    { target: '[data-tour="statutory-link"]', key: "payroll.statutory", side: "right" },
  ],
};

/** Clinical tour — for doctors / nurses. */
export const CLINICAL_TOUR: Tour = {
  id: "clinical",
  label: "clinical.label",
  steps: [
    { target: '[data-tour="patients-link"]', key: "clinical.patients", side: "right" },
    { target: '[data-tour="opd-link"]', key: "clinical.opd", side: "right" },
    { target: '[data-tour="ipd-link"]', key: "clinical.ipd", side: "right" },
    { target: '[data-tour="emergency-link"]', key: "clinical.emergency", side: "right" },
    { target: '[data-tour="laboratory-link"]', key: "clinical.laboratory", side: "right" },
    { target: '[data-tour="pharmacy-link"]', key: "clinical.pharmacy", side: "right" },
  ],
};

/** Map tour id → tour definition for easy lookup. */
export const ALL_TOURS: Record<string, Tour> = {
  [WELCOME_TOUR.id]: WELCOME_TOUR,
  [FINANCE_TOUR.id]: FINANCE_TOUR,
  [PAYROLL_TOUR.id]: PAYROLL_TOUR,
  [CLINICAL_TOUR.id]: CLINICAL_TOUR,
};

/** Pick the most relevant tour for a user based on their roles. */
export function pickTourForRoles(roles: readonly string[]): Tour {
  if (roles.includes("doctor") || roles.includes("nurse")) {
    return CLINICAL_TOUR;
  }
  if (
    roles.includes("hr_admin") ||
    roles.includes("hr_officer")
  ) {
    return PAYROLL_TOUR;
  }
  if (roles.includes("finance_admin") || roles.includes("facility_admin")) {
    return FINANCE_TOUR;
  }
  return WELCOME_TOUR;
}
