"use client";

import { useLicenseContext } from "./LicenseProvider";
import { UpgradePrompt } from "./UpgradePrompt";

/**
 * Gate that conditionally renders children based on feature flag.
 * Shows upgrade prompt if feature not available on current tier.
 *
 * @param flag - Feature flag name to check
 * @param children - Content to show if feature is enabled
 * @param fallback - Optional custom fallback (default: UpgradePrompt)
 * @param silent - If true, renders nothing instead of upgrade prompt
 * @returns Gated content or upgrade prompt
 */
export function FeatureGate({
  flag,
  children,
  fallback,
  silent = false,
}: {
  flag: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  silent?: boolean;
}) {
  const { hasFeature, tier } = useLicenseContext();

  if (hasFeature(flag)) {
    return <>{children}</>;
  }

  if (silent) {
    return null;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <UpgradePrompt
      feature={flag}
      currentTier={tier}
    />
  );
}

/**
 * Gate that conditionally renders children based on module access.
 * Shows upgrade prompt if module not available on current tier.
 *
 * @param module - Module name to check
 * @param children - Content to show if module is enabled
 * @param fallback - Optional custom fallback
 * @param silent - If true, renders nothing instead of upgrade prompt
 * @returns Gated content or upgrade prompt
 */
export function ModuleGate({
  module,
  children,
  fallback,
  silent = false,
}: {
  module: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  silent?: boolean;
}) {
  const { hasModule, tier } = useLicenseContext();

  if (hasModule(module)) {
    return <>{children}</>;
  }

  if (silent) {
    return null;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  return (
    <UpgradePrompt
      module={module}
      currentTier={tier}
    />
  );
}
