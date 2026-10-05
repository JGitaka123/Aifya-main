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
  ListOrdered,
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
  /**
   * Roles the destination belongs to.
   *
   * Undefined means the permission alone decides. When a list is given the
   * destination belongs to those roles and nobody else, which is how Aifya
   * keeps one entry per worker: Pharmacy is the pharmacist's room even though
   * a doctor may read a drug list from inside a consultation.
   */
  roles?: readonly string[];
  separator?: boolean;
}

/**
 * Administrator roles.
 *
 * They run the back office - HR, payroll, staff records, reports and the
 * facility settings - but they do not thereby work in the clinic, the pharmacy
 * or the finance desk. A destination belongs to an administrator only when a
 * list that names them is put on it, exactly as it does for every other duty,
 * so the role HR recorded is the key that opens the room.
 */
export const ADMINISTRATOR_ROLES: readonly string[] = [
  "super_admin",
  "admin",
  "facility_admin",
  "hospital_administrator",
];

/** Clinicians who run consultations. */
const DOCTORS: readonly string[] = ["doctor", "clinician"];
/** Surgeons and consultants, who own the theatre list. */
const SPECIALISTS: readonly string[] = ["specialist"];
/** The dental clinic. */
const DENTISTS: readonly string[] = ["dentist"];
/** Ward, triage and outpatient nursing. */
const NURSES: readonly string[] = ["nurse", "triage_nurse", "ward_nurse"];
/** Maternal and child health. */
const MIDWIVES: readonly string[] = ["midwife"];
/** The dispensary. */
const PHARMACISTS: readonly string[] = ["pharmacist"];
/** The laboratory bench. */
const LABORATORY_TEAM: readonly string[] = ["lab_tech", "pathologist"];
/** The imaging suite. */
const RADIOLOGY_TEAM: readonly string[] = ["radiologist", "rad_tech"];
/** The front desk: registration and patient records. */
const FRONT_DESK: readonly string[] = ["receptionist", "records", "medical_records"];
/** The HR desk. */
const HR_TEAM: readonly string[] = ["hr_admin", "hr", "hr_officer"];
/** The money desk: billing, cashiering, finance and the ledger. */
const ACCOUNTANTS: readonly string[] = [
  "finance_admin",
  "cashier",
  "billing",
  "billing_clerk",
  "billing_officer",
];
/** Stores, which keeps the inventory. */
const STORES_TEAM: readonly string[] = ["store_keeper"];
/** Research, which keeps the clinical-trial workspace. */
const RESEARCH_TEAM: readonly string[] = ["research_coordinator", "principal_investigator"];

/** Doctors and nurses, who share OPD, IPD and emergency. */
const CLINICAL_TEAM: readonly string[] = [...DOCTORS, ...NURSES];

/** The clinical trials workspace: the clinical team plus research. */
const TRIALS_TEAM: readonly string[] = [...CLINICAL_TEAM, ...RESEARCH_TEAM];

/** The knowledge base: HR and the clinical team. */
const KNOWLEDGE_TEAM: readonly string[] = [...HR_TEAM, ...DOCTORS, ...NURSES];

/** The back-office desks: HR's rooms, staffed by HR and the administrators. */
const BACK_OFFICE: readonly string[] = [...HR_TEAM, ...ADMINISTRATOR_ROLES];

/** WHO is the navigation being rendered for. */
export interface NavigationAudience {
  /** Role names carried by the access token; undefined before the session loads. */
  roles?: readonly string[];
  /** Permission test from usePermissions(); true when nothing is required. */
  hasPermission: (permission?: string) => boolean;
}

/**
 * Whether a destination belongs in this user's navigation.
 *
 * Both gates must pass: the person must hold the tab's permission and one of
 * its roles. An unset role list leaves the decision to the permission alone.
 * A role-owned tab is hidden until the session reports its roles, because the
 * role is the key that opens the room - an unknown role is "not yet", never a
 * grant.
 *
 * @param item - Navigation destination from NAV_ITEMS
 * @param viewer - The signed-in user's roles and permission test
 * @returns True when the destination should appear
 */
export function isNavigationVisible(
  item: NavItem,
  viewer: NavigationAudience,
): boolean {
  if (!viewer.hasPermission(item.permission)) return false;

  const allowed = item.roles;
  if (!allowed || allowed.length === 0) return true;

  // The role is the key. A session that has not reported its roles yet is
  // treated as "not yet", so nobody is handed a room their duty does not own
  // while the sign-in is still resolving.
  const roles = viewer.roles;
  if (!roles || roles.length === 0) return false;

  return roles.some((role) => allowed.includes(role));
}

/**
 * Whether the viewer may open a destination's own page.
 *
 * The sidebar uses the same test to decide whether to draw a tab. Asking it
 * again for a link drawn elsewhere keeps a home tile or a hand-off button from
 * offering a door the signed-in role cannot walk through.
 *
 * @param href - Destination href, e.g. "/pharmacy"
 * @param viewer - The signed-in user's roles and permission test
 * @param items - Navigation catalog to search
 * @returns True when the destination may be opened
 */
export function canOpenDestination(
  href: string,
  viewer: NavigationAudience,
  items: readonly NavItem[] = NAV_ITEMS,
): boolean {
  const item = items.find((candidate) => candidate.href === href);
  return !item || isNavigationVisible(item, viewer);
}

/**
 * The destination a pathname belongs to, if any.
 *
 * @param pathname - Current localized or locale-independent pathname
 * @param items - Navigation catalog to search
 * @returns The destination, or undefined when the path is nobody's tab
 */
export function getDestinationForPath(
  pathname: string,
  items: readonly NavItem[] = NAV_ITEMS,
): NavItem | undefined {
  const href = getActiveNavigationHref(pathname, items);
  return href ? items.find((item) => item.href === href) : undefined;
}

/**
 * Whether the viewer may open a pathname at all.
 *
 * A record inside a room - a lab result, an imaging report, an appointment, an
 * invoice - needs the room's permission but not its roles, because the room
 * that raised it links straight to it: a doctor opens the result the OPD screen
 * handed on without working the bench. The room's own page needs both, so a
 * typed URL gets no further than the sidebar would have allowed. The API
 * refuses the same call again on the server.
 *
 * @param pathname - Current localized or locale-independent pathname
 * @param viewer - The signed-in user's roles and permission test
 * @param items - Navigation catalog to search
 * @returns True when the path may be rendered
 */
export function isPathAllowed(
  pathname: string,
  viewer: NavigationAudience,
  items: readonly NavItem[] = NAV_ITEMS,
): boolean {
  const item = getDestinationForPath(pathname, items);
  if (!item) return true;
  if (!viewer.hasPermission(item.permission)) return false;
  if (normalizeNavigationPath(pathname) !== item.href) return true;
  return isNavigationVisible(item, viewer);
}

/** Canonical navigation catalog for every user-facing Aifya module. */
export const NAV_ITEMS: readonly NavItem[] = [
  { key: "dashboard", href: "/", icon: LayoutDashboard },
  { key: "patients", href: "/patients", icon: Users, module: "patients", permission: "patients.view" },
  { key: "registration", href: "/patients/register", icon: UserPlus, module: "patients", permission: "patients.register", roles: FRONT_DESK },
  { key: "consultationRoom", href: "/consultation", icon: Stethoscope, module: "encounters", permission: "clinical.view", roles: NURSES, separator: true },
  { key: "clinical", href: "/clinical", icon: ClipboardList, module: "encounters", permission: "clinical.view", roles: CLINICAL_TEAM },
  // The waiting room: reception issues tickets, nurses call patients in.
  { key: "queue", href: "/queue", icon: ListOrdered, module: "encounters", permission: "clinical.view", roles: [...FRONT_DESK, ...NURSES] },
  { key: "opd", href: "/opd", icon: Stethoscope, module: "opd", permission: "opd.view", roles: CLINICAL_TEAM },
  { key: "ipd", href: "/ipd", icon: BedDouble, module: "ipd", permission: "ipd.view", roles: CLINICAL_TEAM },
  { key: "emergency", href: "/emergency", icon: Siren, module: "emergency", permission: "emergency.view", roles: CLINICAL_TEAM },
  { key: "pharmacy", href: "/pharmacy", icon: Pill, module: "pharmacy", permission: "pharmacy.view", roles: PHARMACISTS, separator: true },
  { key: "laboratory", href: "/laboratory", icon: FlaskConical, module: "laboratory", permission: "laboratory.view", roles: LABORATORY_TEAM },
  { key: "radiology", href: "/radiology", icon: Scan, module: "radiology", permission: "radiology.view", roles: RADIOLOGY_TEAM },
  { key: "theatre", href: "/theatre", icon: Scissors, module: "theatre", permission: "theatre.view", roles: SPECIALISTS },
  { key: "dental", href: "/dental", icon: SmilePlus, module: "dental", permission: "dental.view", roles: DENTISTS },
  { key: "mch", href: "/mch", icon: Baby, module: "mch", permission: "mch.view", roles: MIDWIVES },
  { key: "billing", href: "/billing", icon: Receipt, module: "billing", permission: "billing.view", roles: ACCOUNTANTS, separator: true },
  { key: "pos", href: "/billing/pos", icon: Wallet, module: "billing", permission: "billing.payment", roles: ACCOUNTANTS },
  { key: "finance", href: "/finance", icon: Wallet, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "chartOfAccounts", href: "/finance/accounts", icon: BookOpen, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "glTransactions", href: "/finance/transactions", icon: FileText, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "financeReports", href: "/finance/reports", icon: BarChart3, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "budgets", href: "/finance/budgets", icon: Receipt, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "fixedAssets", href: "/finance/assets", icon: Package, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "periods", href: "/finance/periods", icon: CalendarClock, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "reconciliation", href: "/finance/reconciliation", icon: Activity, module: "finance", permission: "finance.view", roles: ACCOUNTANTS },
  { key: "insurance", href: "/insurance", icon: Shield, module: "insurance", permission: "insurance.view", roles: ACCOUNTANTS },
  { key: "inventory", href: "/inventory", icon: Package, module: "inventory", permission: "inventory.view", roles: [...ACCOUNTANTS, ...STORES_TEAM] },
  { key: "appointments", href: "/appointments", icon: CalendarClock, module: "appointments", permission: "appointments.view", roles: BACK_OFFICE, separator: true },
  { key: "referrals", href: "/referrals", icon: ArrowUpRight, module: "referrals", permission: "referrals.view", roles: BACK_OFFICE },
  { key: "hr", href: "/hr", icon: PersonStanding, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "payroll", href: "/hr/payroll", icon: Wallet, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "employees", href: "/hr/employees", icon: Users, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "leave", href: "/hr/leave", icon: CalendarClock, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "payrollReports", href: "/hr/payroll/reports", icon: FileText, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "statutory", href: "/hr/payroll/statutory", icon: Shield, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "aifyaUsage", href: "/hr/aifya-usage", icon: Activity, module: "hr", permission: "hr.view", roles: BACK_OFFICE },
  { key: "reports", href: "/reports", icon: BarChart3, module: "reports", permission: "reports.view", roles: BACK_OFFICE },
  { key: "analytics", href: "/analytics", icon: Activity, module: "analytics", permission: "analytics.view", roles: BACK_OFFICE },
  { key: "performance", href: "/performance", icon: Activity, module: "analytics", permission: "analytics.view", roles: BACK_OFFICE },
  { key: "communications", href: "/communications", icon: MessageSquare, module: "communications", permission: "communications.view", roles: BACK_OFFICE },
  { key: "integrations", href: "/integrations/fhir", icon: Plug, module: "fhir", permission: "settings.manage", roles: BACK_OFFICE },
  { key: "trials", href: "/trials", icon: FlaskConical, module: "clinical_trials", permission: "trials.view", roles: TRIALS_TEAM, separator: true },
  { key: "knowledge", href: "/knowledge", icon: BookOpen, module: "knowledge", permission: "knowledge.view", roles: KNOWLEDGE_TEAM },
  { key: "userGuide", href: "/user-guide", icon: GraduationCap, separator: true },
  { key: "settings", href: "/settings", icon: Settings, permission: "settings.manage", roles: BACK_OFFICE },
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
