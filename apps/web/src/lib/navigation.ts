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
  separator?: boolean;
}

/** Canonical navigation catalog for every user-facing Aifya module. */
export const NAV_ITEMS: readonly NavItem[] = [
  { key: "dashboard", href: "/", icon: LayoutDashboard },
  { key: "patients", href: "/patients", icon: Users, module: "patients" },
  { key: "registration", href: "/patients/register", icon: UserPlus, module: "patients" },
  { key: "clinical", href: "/clinical", icon: ClipboardList, module: "encounters", separator: true },
  { key: "opd", href: "/opd", icon: Stethoscope, module: "opd" },
  { key: "ipd", href: "/ipd", icon: BedDouble, module: "ipd" },
  { key: "emergency", href: "/emergency", icon: Siren, module: "emergency" },
  { key: "pharmacy", href: "/pharmacy", icon: Pill, module: "pharmacy", separator: true },
  { key: "laboratory", href: "/laboratory", icon: FlaskConical, module: "laboratory" },
  { key: "radiology", href: "/radiology", icon: Scan, module: "radiology" },
  { key: "theatre", href: "/theatre", icon: Scissors, module: "theatre" },
  { key: "dental", href: "/dental", icon: SmilePlus, module: "dental" },
  { key: "mch", href: "/mch", icon: Baby, module: "mch" },
  { key: "billing", href: "/billing", icon: Receipt, module: "billing", separator: true },
  { key: "pos", href: "/billing/pos", icon: Wallet, module: "billing" },
  { key: "finance", href: "/finance", icon: Wallet, module: "finance" },
  { key: "chartOfAccounts", href: "/finance/accounts", icon: BookOpen, module: "finance" },
  { key: "glTransactions", href: "/finance/transactions", icon: FileText, module: "finance" },
  { key: "financeReports", href: "/finance/reports", icon: BarChart3, module: "finance" },
  { key: "budgets", href: "/finance/budgets", icon: Receipt, module: "finance" },
  { key: "fixedAssets", href: "/finance/assets", icon: Package, module: "finance" },
  { key: "periods", href: "/finance/periods", icon: CalendarClock, module: "finance" },
  { key: "reconciliation", href: "/finance/reconciliation", icon: Activity, module: "finance" },
  { key: "insurance", href: "/insurance", icon: Shield, module: "insurance" },
  { key: "inventory", href: "/inventory", icon: Package, module: "inventory" },
  { key: "appointments", href: "/appointments", icon: CalendarClock, module: "appointments", separator: true },
  { key: "referrals", href: "/referrals", icon: ArrowUpRight, module: "referrals" },
  { key: "hr", href: "/hr", icon: PersonStanding, module: "hr" },
  { key: "payroll", href: "/hr/payroll", icon: Wallet, module: "hr" },
  { key: "employees", href: "/hr/employees", icon: Users, module: "hr" },
  { key: "leave", href: "/hr/leave", icon: CalendarClock, module: "hr" },
  { key: "payrollReports", href: "/hr/payroll/reports", icon: FileText, module: "hr" },
  { key: "statutory", href: "/hr/payroll/statutory", icon: Shield, module: "hr" },
  { key: "reports", href: "/reports", icon: BarChart3, module: "reports" },
  { key: "analytics", href: "/analytics", icon: Activity, module: "analytics" },
  { key: "performance", href: "/performance", icon: Activity, module: "analytics" },
  { key: "communications", href: "/communications", icon: MessageSquare, module: "communications" },
  { key: "integrations", href: "/integrations/fhir", icon: Plug, module: "fhir" },
  { key: "trials", href: "/trials", icon: FlaskConical, module: "clinical_trials", separator: true },
  { key: "knowledge", href: "/knowledge", icon: BookOpen, module: "knowledge" },
  { key: "userGuide", href: "/user-guide", icon: GraduationCap, separator: true },
  { key: "settings", href: "/settings", icon: Settings },
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
