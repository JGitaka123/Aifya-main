import type { ComponentType } from "react";
import {
  Activity,
  ArrowUpRight,
  Baby,
  BarChart3,
  BedDouble,
  BookOpen,
  CalendarClock,
  ClipboardList,
  FileText,
  FlaskConical,
  LayoutDashboard,
  MessageSquare,
  Package,
  PersonStanding,
  Pill,
  Plug,
  Receipt,
  Scan,
  Scissors,
  Settings,
  Shield,
  Siren,
  SmilePlus,
  Stethoscope,
  GraduationCap,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";

/** Shared module navigation definition used by the sidebar and command palette. */
export interface NavItem {
  key: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  module?: string;
  /**
   * Permission the signed-in user must hold for this destination to appear.
   *
   * Undefined means every signed-in user may see it (the dashboard, the help
   * pages). The API enforces the same permission, so hiding here is a courtesy
   * that keeps a cashier out of the doctor's workspace rather than a control.
   */
  permission?: string;
  separator?: boolean;
}

/** Canonical navigation catalog for every user-facing Aifya module. */
export const NAV_ITEMS: readonly NavItem[] = [
  { key: "dashboard", href: "/", icon: LayoutDashboard },
  { key: "patients", href: "/patients", icon: Users, module: "patients", permission: "patients.view" },
  { key: "registration", href: "/patients/register", icon: UserPlus, module: "patients", permission: "patients.register" },
  { key: "consultationRoom", href: "/consultation", icon: Stethoscope, module: "encounters", permission: "clinical.view", separator: true },
  { key: "clinical", href: "/clinical", icon: ClipboardList, module: "encounters", permission: "clinical.view" },
  { key: "opd", href: "/opd", icon: Stethoscope, module: "opd", permission: "opd.view" },
  { key: "ipd", href: "/ipd", icon: BedDouble, module: "ipd", permission: "ipd.view" },
  { key: "emergency", href: "/emergency", icon: Siren, module: "emergency", permission: "emergency.view" },
  { key: "pharmacy", href: "/pharmacy", icon: Pill, module: "pharmacy", permission: "pharmacy.view", separator: true },
  { key: "laboratory", href: "/laboratory", icon: FlaskConical, module: "laboratory", permission: "laboratory.view" },
  { key: "radiology", href: "/radiology", icon: Scan, module: "radiology", permission: "radiology.view" },
  { key: "theatre", href: "/theatre", icon: Scissors, module: "theatre", permission: "theatre.view" },
  { key: "dental", href: "/dental", icon: SmilePlus, module: "dental", permission: "dental.view" },
  { key: "mch", href: "/mch", icon: Baby, module: "mch", permission: "mch.view" },
  { key: "billing", href: "/billing", icon: Receipt, module: "billing", permission: "billing.view", separator: true },
  { key: "pos", href: "/billing/pos", icon: Wallet, module: "billing", permission: "billing.payment" },
  { key: "finance", href: "/finance", icon: Wallet, module: "finance", permission: "finance.view" },
  { key: "chartOfAccounts", href: "/finance/accounts", icon: BookOpen, module: "finance", permission: "finance.view" },
  { key: "glTransactions", href: "/finance/transactions", icon: FileText, module: "finance", permission: "finance.view" },
  { key: "financeReports", href: "/finance/reports", icon: BarChart3, module: "finance", permission: "finance.view" },
  { key: "budgets", href: "/finance/budgets", icon: Receipt, module: "finance", permission: "finance.view" },
  { key: "fixedAssets", href: "/finance/assets", icon: Package, module: "finance", permission: "finance.view" },
  { key: "periods", href: "/finance/periods", icon: CalendarClock, module: "finance", permission: "finance.view" },
  { key: "reconciliation", href: "/finance/reconciliation", icon: Activity, module: "finance", permission: "finance.view" },
  { key: "insurance", href: "/insurance", icon: Shield, module: "insurance", permission: "insurance.view" },
  { key: "inventory", href: "/inventory", icon: Package, module: "inventory", permission: "inventory.view" },
  { key: "appointments", href: "/appointments", icon: CalendarClock, module: "appointments", permission: "appointments.view", separator: true },
  { key: "referrals", href: "/referrals", icon: ArrowUpRight, module: "referrals", permission: "referrals.view" },
  { key: "hr", href: "/hr", icon: PersonStanding, module: "hr", permission: "hr.view" },
  { key: "payroll", href: "/hr/payroll", icon: Wallet, module: "hr", permission: "hr.view" },
  { key: "employees", href: "/hr/employees", icon: Users, module: "hr", permission: "hr.view" },
  { key: "leave", href: "/hr/leave", icon: CalendarClock, module: "hr", permission: "hr.view" },
  { key: "payrollReports", href: "/hr/payroll/reports", icon: FileText, module: "hr", permission: "hr.view" },
  { key: "statutory", href: "/hr/payroll/statutory", icon: Shield, module: "hr", permission: "hr.view" },
  { key: "aifyaUsage", href: "/hr/aifya-usage", icon: Activity, module: "hr", permission: "hr.view" },
  { key: "reports", href: "/reports", icon: BarChart3, module: "reports", permission: "reports.view" },
  { key: "analytics", href: "/analytics", icon: Activity, module: "analytics", permission: "analytics.view" },
  { key: "performance", href: "/performance", icon: Activity, module: "analytics", permission: "analytics.view" },
  { key: "communications", href: "/communications", icon: MessageSquare, module: "communications", permission: "communications.view" },
  { key: "integrations", href: "/integrations/fhir", icon: Plug, module: "fhir", permission: "settings.manage" },
  { key: "trials", href: "/trials", icon: FlaskConical, module: "clinical_trials", permission: "trials.view", separator: true },
  { key: "knowledge", href: "/knowledge", icon: BookOpen, module: "knowledge", permission: "knowledge.view" },
  { key: "userGuide", href: "/user-guide", icon: GraduationCap, separator: true },
  { key: "settings", href: "/settings", icon: Settings, permission: "settings.manage" },
];

/** Navigation destinations shown before the user starts typing a command. */
export const PRIMARY_COMMAND_HREFS = new Set([
  "/patients",
  "/patients/register",
  "/opd",
  "/emergency",
  "/pharmacy",
  "/laboratory",
  "/billing",
  "/reports",
]);

/**
 * Remove the supported locale prefix and normalize an application pathname.
 *
 * @param pathname - Pathname returned by Next.js navigation.
 * @returns A locale-independent pathname beginning with a slash.
 */
export function normalizeNavigationPath(pathname: string): string {
  return pathname.replace(/^\/(en|sw)(?=\/|$)/, "") || "/";
}

/**
 * Resolve the most specific navigation destination for a pathname.
 *
 * @param pathname - Current localized or locale-independent pathname.
 * @param items - Navigation catalog to search.
 * @returns The active destination href, or undefined when no item matches.
 */
export function getActiveNavigationHref(
  pathname: string,
  items: readonly NavItem[] = NAV_ITEMS,
): string | undefined {
  const normalizedPath = normalizeNavigationPath(pathname);

  return items
    .filter((item) =>
      item.href === "/"
        ? normalizedPath === "/"
        : normalizedPath === item.href ||
          normalizedPath.startsWith(`${item.href}/`),
    )
    .sort((left, right) => right.href.length - left.href.length)[0]?.href;
}
