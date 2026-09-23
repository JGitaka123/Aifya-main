"use client";

import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import type { LicenseValidation, PatientLimitInfo } from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import {
  BETA_PUBLIC_ACCESS_ENABLED,
  getBetaLicense,
  getBetaModuleAccess,
  getBetaPatientLimit,
} from "@/lib/auth/beta";

const LICENSE_KEYS = {
  all: ["license"] as const,
  validation: () => [...LICENSE_KEYS.all, "validation"] as const,
  patientLimit: () => [...LICENSE_KEYS.all, "patient-limit"] as const,
  moduleAccess: (module: string) => [...LICENSE_KEYS.all, "module", module] as const,
};

/**
 * Get current facility's license and entitlements.
 * Cached for 5 minutes — this is the primary source of truth for feature gating.
 *
 * @returns License validation with tier, modules, feature flags
 */
export function useLicense() {
  return useOfflineQuery<LicenseValidation>({
    queryKey: LICENSE_KEYS.validation(),
    queryFn: () =>
      BETA_PUBLIC_ACCESS_ENABLED
        ? getBetaLicense()
        : apiFetch("/api/v1/licensing/license"),
    staleTime: 5 * 60_000, // 5 minutes
    refetchInterval: 5 * 60_000,
  });
}

/**
 * Check if facility has reached patient registration limit.
 *
 * @returns Patient limit info
 */
export function usePatientLimit() {
  return useOfflineQuery<PatientLimitInfo>({
    queryKey: LICENSE_KEYS.patientLimit(),
    queryFn: () =>
      BETA_PUBLIC_ACCESS_ENABLED
        ? getBetaPatientLimit()
        : apiFetch("/api/v1/licensing/license/patient-limit"),
    staleTime: 60_000,
  });
}

/**
 * Check if a specific module is accessible.
 *
 * @param module - Module name to check
 * @returns Module access check result
 */
export function useModuleAccess(module: string) {
  return useOfflineQuery<{ module: string; allowed: boolean }>({
    queryKey: LICENSE_KEYS.moduleAccess(module),
    queryFn: () =>
      BETA_PUBLIC_ACCESS_ENABLED
        ? getBetaModuleAccess(module)
        : apiFetch(`/api/v1/licensing/license/module/${module}`),
    staleTime: 5 * 60_000,
    enabled: !!module,
  });
}
