/** Subscription tier levels */
export type SubscriptionTier = "community" | "professional" | "enterprise" | "government";

/** Billing cycle */
export type BillingCycle = "monthly" | "annual" | "perpetual";

/** Update channel */
export type UpdateChannel = "stable" | "beta" | "canary";

/** License validation response — core entitlements for the facility */
export interface LicenseValidation {
  is_valid: boolean;
  tier: SubscriptionTier;
  enabled_modules: string[];
  feature_flags: Record<string, boolean>;
  max_users: number;
  max_patients: number;
  expires_at: string | null;
  days_remaining: number | null;
  in_grace_period: boolean;
  upgrade_available: boolean;
  upgrade_message: string | null;
  latest_version: string | null;
  update_required: boolean;
}

/** Patient limit check response */
export interface PatientLimitInfo {
  current: number;
  limit: number;
  remaining: number;
  limit_reached: boolean;
  tier: SubscriptionTier;
  upgrade_available: boolean;
}

/** Module access check response */
export interface ModuleAccessCheck {
  module: string;
  allowed: boolean;
}

/** License error response from 403 */
export interface LicenseError {
  error: "module_not_licensed" | "feature_not_licensed" | "patient_limit_reached";
  module?: string;
  feature?: string;
  current_tier: SubscriptionTier;
  message: string;
  upgrade_url: string;
}

/** Heartbeat request payload */
export interface HeartbeatRequest {
  license_key: string;
  current_version: string;
  active_users?: number;
  total_patients?: number;
  modules_used?: string[];
}

/** Telemetry payload — no PII */
export interface TelemetryPayload {
  active_users: number;
  total_patients: number;
  encounters_today: number;
  prescriptions_today: number;
  lab_orders_today: number;
  admissions_today: number;
  billing_total_cents: number;
  ai_requests_today: number;
  modules_used: string[];
  app_version?: string;
}

/** Update check response */
export interface UpdateCheckResponse {
  update_available: boolean;
  current_version: string;
  latest_version: string | null;
  is_critical: boolean;
  is_mandatory: boolean;
  title: string | null;
  changelog: string | null;
  download_url: string | null;
  docker_tag: string | null;
}

/** Tier entitlements display info */
export interface TierInfo {
  name: SubscriptionTier;
  label: string;
  max_users: number;
  max_patients: number;
  modules: string[];
  price_monthly: string;
  price_annual: string;
  features: Record<string, boolean>;
}
