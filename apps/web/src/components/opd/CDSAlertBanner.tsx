"use client";

import { useState, useMemo, useCallback } from "react";
import { useTranslations } from "next-intl";
import { ShieldAlert, AlertTriangle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CDSAlert, AlertSeverity } from "@aifya/shared";

interface CDSAlertBannerProps {
  /** List of CDS alerts to display, grouped and sorted by severity. */
  alerts: CDSAlert[];
  /** Callback when the entire alert banner is dismissed. Only available for non-critical alerts. */
  onDismiss?: () => void;
  /** Callback when a clinician overrides an alert, with the alert ID and override reason. */
  onOverride?: (alertId: string, reason: string) => void;
}

/** Severity ordering for sorting alerts (lower = more severe). */
const SEVERITY_ORDER: Record<AlertSeverity, number> = {
  critical: 0,
  high: 1,
  moderate: 2,
  low: 3,
  info: 4,
};

/**
 * Returns Tailwind classes for a given alert severity level.
 *
 * @param severity - The alert severity
 * @returns Object with container, icon, and pill class strings
 */
function severityStyles(severity: AlertSeverity): {
  container: string;
  icon: string;
  pill: string;
} {
  switch (severity) {
    case "critical":
    case "high":
      return {
        container:
          "bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200",
        icon: "text-red-600 dark:text-red-400",
        pill: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
      };
    case "moderate":
      return {
        container:
          "bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200",
        icon: "text-amber-600 dark:text-amber-400",
        pill: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
      };
    case "low":
    case "info":
      return {
        container:
          "bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200",
        icon: "text-blue-600 dark:text-blue-400",
        pill: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
      };
  }
}

/**
 * Returns the appropriate icon component for a given severity level.
 *
 * @param severity - The alert severity
 * @returns A Lucide icon element
 */
function SeverityIcon({ severity }: { severity: AlertSeverity }) {
  const styles = severityStyles(severity);
  const iconClass = cn("mt-0.5 h-4 w-4 flex-shrink-0", styles.icon);

  switch (severity) {
    case "critical":
    case "high":
      return <ShieldAlert className={iconClass} />;
    case "moderate":
      return <AlertTriangle className={iconClass} />;
    case "low":
    case "info":
      return <Info className={iconClass} />;
  }
}

/**
 * Individual alert row with optional override capability.
 *
 * @param props - Alert data and override callback
 * @returns Alert row element
 */
function AlertRow({
  alert,
  onOverride,
}: {
  alert: CDSAlert;
  onOverride?: (alertId: string, reason: string) => void;
}) {
  const t = useTranslations("cds");
  const [showOverrideInput, setShowOverrideInput] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");

  const styles = severityStyles(alert.severity);

  const handleOverride = useCallback(() => {
    if (alert.requires_reason && !overrideReason.trim()) {
      return;
    }
    onOverride?.(alert.alert_id, overrideReason.trim());
    setShowOverrideInput(false);
    setOverrideReason("");
  }, [alert.alert_id, alert.requires_reason, overrideReason, onOverride]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <SeverityIcon severity={alert.severity} />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm">{alert.title}</p>
          <p className="text-sm mt-0.5">{alert.message}</p>

          {/* Affected items as pills */}
          {alert.affected_items.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {alert.affected_items.map((item) => (
                <span
                  key={item}
                  className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                    styles.pill
                  )}
                >
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Override button */}
        {alert.overridable && onOverride && !showOverrideInput && (
          <button
            type="button"
            onClick={() => setShowOverrideInput(true)}
            className="flex-shrink-0 rounded-md border border-current/20 px-2.5 py-1 text-xs font-medium hover:bg-black/5 dark:hover:bg-white/10"
          >
            {t("override")}
          </button>
        )}
      </div>

      {/* Override reason input */}
      {showOverrideInput && (
        <div className="ml-6 flex items-center gap-2">
          {alert.requires_reason ? (
            <input
              type="text"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder={t("overrideReasonPlaceholder")}
              className="flex-1 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
            />
          ) : null}
          <button
            type="button"
            onClick={handleOverride}
            disabled={alert.requires_reason && !overrideReason.trim()}
            className="rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50 dark:bg-amber-700 dark:hover:bg-amber-600"
          >
            {t("confirmOverride")}
          </button>
          <button
            type="button"
            onClick={() => {
              setShowOverrideInput(false);
              setOverrideReason("");
            }}
            className="rounded-md border border-input px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
          >
            {t("cancelOverride")}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Clinical Decision Support alert banner.
 * Displays CDS alerts grouped by severity with override capability.
 * Critical alerts are non-dismissible. Supports dark mode and i18n.
 *
 * @param props - CDSAlertBannerProps with alerts, onDismiss, and onOverride
 * @returns CDS alert banner component, or null if no alerts
 */
export function CDSAlertBanner({
  alerts,
  onDismiss,
  onOverride,
}: CDSAlertBannerProps) {
  const t = useTranslations("cds");

  /** Sort alerts by severity (critical first) and group them. */
  const sortedAlerts = useMemo(
    () =>
      [...alerts].sort(
        (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
      ),
    [alerts]
  );

  const hasCritical = useMemo(
    () => sortedAlerts.some((a) => a.severity === "critical"),
    [sortedAlerts]
  );

  /** Group consecutive alerts by severity band for visual grouping. */
  const groups = useMemo(() => {
    const result: { severity: AlertSeverity; alerts: CDSAlert[] }[] = [];
    let currentGroup: { severity: AlertSeverity; alerts: CDSAlert[] } | null =
      null;

    for (const alert of sortedAlerts) {
      const band = getBand(alert.severity);
      if (!currentGroup || getBand(currentGroup.severity) !== band) {
        currentGroup = { severity: alert.severity, alerts: [alert] };
        result.push(currentGroup);
      } else {
        currentGroup.alerts.push(alert);
      }
    }

    return result;
  }, [sortedAlerts]);

  if (sortedAlerts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2" role="alert" aria-live="assertive">
      {/* Header with dismiss button */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-foreground">
          {t("alertsTitle", { count: sortedAlerts.length })}
        </h4>
        {onDismiss && !hasCritical && (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={t("dismiss")}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Grouped alert banners */}
      {groups.map((group) => {
        const styles = severityStyles(group.severity);
        return (
          <div
            key={`${group.severity}-${group.alerts[0]?.alert_id ?? "group"}`}
            className={cn(
              "rounded-lg border p-3 text-sm",
              styles.container
            )}
          >
            <div className="space-y-3">
              {group.alerts.map((alert) => (
                <AlertRow
                  key={alert.alert_id}
                  alert={alert}
                  onOverride={onOverride}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Maps a severity to a display band for grouping.
 *
 * @param severity - Alert severity level
 * @returns Band key for grouping
 */
function getBand(severity: AlertSeverity): "critical" | "moderate" | "info" {
  switch (severity) {
    case "critical":
    case "high":
      return "critical";
    case "moderate":
      return "moderate";
    case "low":
    case "info":
      return "info";
  }
}
