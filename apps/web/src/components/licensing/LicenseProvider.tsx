"use client";

import { createContext, useContext, useMemo } from "react";
import { useLicense } from "@/hooks/useLicense";
import type { LicenseValidation, SubscriptionTier } from "@aifya/shared";

/**
 * License context value — available to all child components.
 */
interface LicenseContextValue {
  /** Current tier: community | professional | enterprise | government */
  tier: SubscriptionTier;
  /** Full license validation data */
  license: LicenseValidation | undefined;
  /** Whether license data is still loading */
  isLoading: boolean;
  /** Check if a module is enabled */
  hasModule: (module: string) => boolean;
  /** Check if a feature flag is enabled */
  hasFeature: (flag: string) => boolean;
  /** Whether the license is in grace period */
  inGracePeriod: boolean;
  /** Whether an upgrade is available */
  upgradeAvailable: boolean;
  /** Days until expiry (null = no expiry) */
  daysRemaining: number | null;
}

const LicenseContext = createContext<LicenseContextValue>({
  tier: "community",
  license: undefined,
  isLoading: true,
  hasModule: () => true,
  hasFeature: () => false,
  inGracePeriod: false,
  upgradeAvailable: false,
  daysRemaining: null,
});

const TIER_MODULES: Record<SubscriptionTier, string[]> = {
  community: ["patients", "encounters", "opd", "vitals", "billing"],
  professional: [
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
  ],
  enterprise: [
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
  ],
  government: [
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
  ],
};

const TIER_FLAGS: Record<SubscriptionTier, Record<string, boolean>> = {
  community: {
    ai_features: false,
    custom_reports: false,
    api_access: false,
    data_export: false,
    white_label: false,
    priority_support: false,
    sla_guarantee: false,
    offline_mode: true,
    multi_language: true,
  },
  professional: {
    ai_features: false,
    custom_reports: true,
    api_access: false,
    data_export: true,
    white_label: false,
    priority_support: false,
    sla_guarantee: false,
    offline_mode: true,
    multi_language: true,
  },
  enterprise: {
    ai_features: true,
    custom_reports: true,
    api_access: true,
    data_export: true,
    white_label: true,
    priority_support: true,
    sla_guarantee: true,
    offline_mode: true,
    multi_language: true,
  },
  government: {
    ai_features: true,
    custom_reports: true,
    api_access: true,
    data_export: true,
    white_label: true,
    priority_support: true,
    sla_guarantee: true,
    offline_mode: true,
    multi_language: true,
  },
};

/**
 * Provider that fetches and caches facility license,
 * exposing tier info and entitlements to all child components.
 *
 * @param children - React child nodes
 * @returns Provider component
 */
export function LicenseProvider({ children }: { children: React.ReactNode }) {
  const { data: license, isLoading } = useLicense();

  const value = useMemo<LicenseContextValue>(() => {
    const tier = (license?.tier ?? "community") as SubscriptionTier;
    const enabledModules = license?.enabled_modules?.length
      ? license.enabled_modules
      : TIER_MODULES[tier];
    const modules = new Set(enabledModules);
    const flags = Object.keys(license?.feature_flags ?? {}).length
      ? license?.feature_flags ?? {}
      : TIER_FLAGS[tier];

    const isDev = process.env.NODE_ENV === "development";
    return {
      tier: isDev ? "professional" as SubscriptionTier : tier,
      license,
      isLoading,
      hasModule: (module: string) => isDev ? true : modules.has(module),
      hasFeature: (flag: string) => isDev ? true : flags[flag] === true,
      inGracePeriod: license?.in_grace_period ?? false,
      upgradeAvailable: license?.upgrade_available ?? false,
      daysRemaining: license?.days_remaining ?? null,
    };
  }, [license, isLoading]);

  return (
    <LicenseContext.Provider value={value}>
      {children}
    </LicenseContext.Provider>
  );
}

/**
 * Hook to access license context from any component.
 *
 * @returns License context value
 */
export function useLicenseContext() {
  return useContext(LicenseContext);
}
