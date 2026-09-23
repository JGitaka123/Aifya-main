"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  FlaskConical,
  Clock,
  AlertTriangle,
  Beaker,
  CheckCircle2,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { ScheduledAppointments } from "@/components/appointments/ScheduledAppointments";
import { useLabWorklist } from "@/hooks/useLaboratory";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** Priority badge styling. */
const PRIORITY_STYLES: Record<string, string> = {
  stat: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  routine: "bg-muted text-muted-foreground",
};

/** Order status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  ordered: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  collected: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  processing: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/**
 * Lab Worklist page — orders by status with priority badges, critical indicators.
 * Auto-refreshes every 15 seconds for real-time updates.
 *
 * @returns Lab worklist page
 */
export default function LabWorklistPage() {
  const t = useTranslations("lab");
  const tc = useTranslations("common");
  // Default to every status so a resulted order never disappears from the list.
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data, isLoading } = useLabWorklist(statusFilter || undefined);

  const statusOptions: { value: string; label: string }[] = [
    { value: "all", label: t("filterAll") },
    { value: "", label: t("filterActive") },
    { value: "ordered", label: t("ordered") },
    { value: "collected", label: t("collected") },
    { value: "processing", label: t("processing") },
    { value: "completed", label: t("completed") },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical className="h-7 w-7 text-primary" />
          <h1 className="text-2xl font-bold text-foreground">{t("worklist")}</h1>
          {data && (
            <span className="rounded-full bg-muted px-3 py-0.5 text-sm font-medium text-muted-foreground">
              {data.total}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Priority legend */}
      <div className="mb-4 flex flex-wrap gap-2">
        {(["stat", "urgent", "routine"] as const).map((p) => (
          <span
            key={p}
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium",
              PRIORITY_STYLES[p]
            )}
          >
            {t(p)}
          </span>
        ))}
      </div>

      {/* Appointments reception booked for the laboratory */}
      <div className="mb-6">
        <ScheduledAppointments appointmentType="lab" />
      </div>

      {/* Worklist */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          {tc("loading")}
        </div>
      ) : !data?.items?.length ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Beaker className="mb-3 h-12 w-12 opacity-40" />
          <p className="text-lg">{t("worklistEmpty")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {(data.items ?? []).map((order) => (
            <Link
              key={order.id}
              href={`/laboratory/${order.id}`}
              className={cn(
                "flex items-center gap-4 rounded-lg border p-4 transition-colors hover:shadow-md",
                "border-border bg-card shadow-[var(--shadow-card)]",
                order.critical_count > 0 && "border-red-300 dark:border-red-800"
              )}
            >
              {/* Order number badge */}
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                <FlaskConical className="h-5 w-5" />
              </div>

              {/* Patient info & order number */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-semibold text-foreground">
                    {order.patient_name ?? "—"}
                  </span>
                  {order.patient_mrn && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {order.patient_mrn}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                  <span className="font-mono">{order.order_number}</span>
                  {order.specimen_type && <span>• {order.specimen_type}</span>}
                  {order.fasting && (
                    <span className="text-amber-600 dark:text-amber-400">
                      • {t("fastingRequired")}
                    </span>
                  )}
                </div>
              </div>

              {/* Test counts */}
              <div className="hidden flex-shrink-0 items-center gap-3 text-xs sm:flex">
                <span className="flex items-center gap-1 text-muted-foreground">
                  <Beaker className="h-3.5 w-3.5" />
                  {order.test_count} {t("testCount")}
                </span>
                {order.pending_count > 0 && (
                  <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <Clock className="h-3.5 w-3.5" />
                    {order.pending_count} {t("pendingCount")}
                  </span>
                )}
                {order.critical_count > 0 && (
                  <span className="flex items-center gap-1 font-semibold text-red-600 dark:text-red-400">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {order.critical_count} {t("criticalCount")}
                  </span>
                )}
              </div>

              {/* Priority badge */}
              <span
                className={cn(
                  "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                  PRIORITY_STYLES[order.priority] ?? PRIORITY_STYLES.routine
                )}
              >
                {t(order.priority as "stat" | "urgent" | "routine")}
              </span>

              {/* Status badge */}
              <span
                className={cn(
                  "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                  STATUS_STYLES[order.status] ?? STATUS_STYLES.ordered
                )}
              >
                {t(order.status as "ordered" | "collected" | "processing" | "completed" | "cancelled")}
              </span>

              {/* Time */}
              <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                <Clock className="h-3 w-3" />
                {formatDateTime(order.created_at)}
              </div>

              {/* Critical indicator */}
              {order.critical_count > 0 && (
                <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-500" />
              )}

              {/* Completed indicator */}
              {order.status === "completed" && (
                <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-green-500" />
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
