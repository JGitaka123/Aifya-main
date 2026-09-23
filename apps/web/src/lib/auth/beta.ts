import type {
  LicenseValidation,
  PatientLimitInfo,
  SubscriptionTier,
} from "@aifya/shared";

export interface BetaUser {
  id: string;
  email: string;
  name: string;
  roles: string[];
  facilityId: string;
}

export const BETA_PUBLIC_ACCESS_ENABLED =
  process.env.NEXT_PUBLIC_BETA_PUBLIC_ACCESS !== "false";

const BETA_USER: BetaUser = {
  id: "beta-user",
  email: "beta@aifyamed.com",
  name: "Aifya Beta Tester",
  roles: [
    "admin",
    "clinician",
    "nurse",
    "pharmacist",
    "billing",
    "hr",
  ],
  facilityId: "aifya-beta",
};

const BETA_TIER: SubscriptionTier = "government";

const BETA_ENABLED_MODULES = [
  "patients",
  "encounters",
  "opd",
  "vitals",
  "billing",
  "ipd",
  "pharmacy",
  "laboratory",
  "radiology",
  "appointments",
  "mch",
  "dental",
  "emergency",
  "theatre",
  "referrals",
  "insurance",
  "inventory",
  "finance",
  "hr",
  "reports",
  "scribe_ai",
  "claimflow_ai",
  "clinical_trials",
  "analytics",
  "communications",
  "dhis2_sync",
  "fhir",
  "fhir_api",
  "mpesa_billing",
  "api_access",
  "multi_facility",
  "county_dashboard",
  "aggregate_reporting",
  "facility_comparison",
];

const BETA_FEATURE_FLAGS: Record<string, boolean> = {
  ai_features: true,
  custom_reports: true,
  api_access: true,
  data_export: true,
  white_label: true,
  priority_support: true,
  sla_guarantee: true,
  offline_mode: true,
  multi_language: true,
};

/**
 * Return the beta tester profile used while public beta access is enabled.
 *
 * @returns A fresh beta user object for auth context and /api/auth/me
 */
export function getBetaUser(): BetaUser {
  return {
    ...BETA_USER,
    roles: [...BETA_USER.roles],
  };
}

/**
 * Return the beta facility license used for public walkthroughs.
 *
 * @returns A full-access beta license validation response
 */
export function getBetaLicense(): LicenseValidation {
  return {
    is_valid: true,
    tier: BETA_TIER,
    enabled_modules: [...BETA_ENABLED_MODULES],
    feature_flags: { ...BETA_FEATURE_FLAGS },
    max_users: 1000,
    max_patients: 100000,
    expires_at: null,
    days_remaining: null,
    in_grace_period: false,
    upgrade_available: false,
    upgrade_message: null,
    latest_version: null,
    update_required: false,
  };
}

/**
 * Return the beta patient limit response.
 *
 * @returns A generous patient limit for beta testing
 */
export function getBetaPatientLimit(): PatientLimitInfo {
  return {
    current: 0,
    limit: 100000,
    remaining: 100000,
    limit_reached: false,
    tier: BETA_TIER,
    upgrade_available: false,
  };
}

/**
 * Check beta access for a module.
 *
 * @param module - Module key to check
 * @returns Whether the beta entitlement includes the module
 */
export function getBetaModuleAccess(module: string): {
  module: string;
  allowed: boolean;
} {
  return {
    module,
    allowed: BETA_ENABLED_MODULES.includes(module),
  };
}
