"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Scan,
  Clock,
  Activity,
  AlertCircle,
  FileText,
  CheckCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { ScheduledAppointments } from "@/components/appointments/ScheduledAppointments";
import { useRadiologySummary, useImagingWorklist } from "@/hooks/useRadiology";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** Modality display labels and colors. */
const MODALITY_CONFIG: Record<string, { label: string; color: string }> = {
  xray: { label: "X-Ray", color: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200" },
  ultrasound: { label: "US", color: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200" },
  ct: { label: "CT", color: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200" },
  mri: { label: "MRI", color: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200" },
  fluoroscopy: { label: "Fluoro", color: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200" },
  mammography: { label: "Mammo", color: "bg-pink-100 text-pink-800 dark:bg-pink-950 dark:text-pink-200" },
  ecg: { label: "ECG", color: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200" },
  echo: { label: "Echo", color: "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200" },
};

/** Priority badge styling. */
const PRIORITY_STYLES: Record<string, string> = {
  stat: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  routine: "bg-muted text-muted-foreground",
};

/** Order status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  ordered: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  scheduled: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-muted text-muted-foreground",
};

/**
 * Radiology Worklist — dashboard showing imaging orders, summary stats, and modality filters.
 * Auto-refreshes for real-time workflow management.
 *
 * @returns Radiology worklist page
 */
export default function RadiologyWorklistPage() {
  const t = useTranslations("radiology");
  const tc = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [modalityFilter, setModalityFilter] = useState<string>("");

  const { data: summary } = useRadiologySummary();
  const { data: worklist, isLoading } = useImagingWorklist(
    statusFilter || undefined,
    modalityFilter || undefined
  );

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Scan className="h-7 w-7 text-primary" />
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          >
            <option value="">{t("filterAllStatuses")}</option>
            <option value="ordered">{t("statusOrdered")}</option>
            <option value="scheduled">{t("statusScheduled")}</option>
            <option value="in_progress">{t("statusInProgress")}</option>
            <option value="completed">{t("statusCompleted")}</option>
          </select>
          {/* Modality filter */}
          <select
            value={modalityFilter}
            onChange={(e) => setModalityFilter(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          >
            <option value="">{t("filterAllModalities")}</option>
            <option value="xray">X-Ray</option>
            <option value="ultrasound">Ultrasound</option>
            <option value="ct">CT</option>
            <option value="mri">MRI</option>
            <option value="fluoroscopy">Fluoroscopy</option>
            <option value="mammography">Mammography</option>
            <option value="ecg">ECG</option>
            <option value="echo">Echo</option>
          </select>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard
            icon={<Scan className="h-5 w-5 text-muted-foreground" />}
            label={t("ordersToday")}
            value={String(summary.total_orders_today)}
          />
          <SummaryCard
            icon={<Clock className="h-5 w-5 text-blue-500" />}
            label={t("pendingOrders")}
            value={String(summary.pending_orders)}
            highlight={summary.pending_orders > 10}
          />
          <SummaryCard
            icon={<Activity className="h-5 w-5 text-amber-500" />}
            label={t("inProgress")}
            value={String(summary.in_progress)}
          />
          <SummaryCard
            icon={<CheckCircle className="h-5 w-5 text-green-500" />}
            label={t("completedToday")}
            value={String(summary.completed_today)}
          />
          <SummaryCard
            icon={<FileText className="h-5 w-5 text-purple-500" />}
            label={t("pendingReports")}
            value={String(summary.pending_reports)}
            highlight={summary.pending_reports > 5}
          />
          <SummaryCard
            icon={<AlertCircle className="h-5 w-5 text-red-500" />}
            label={t("criticalFindings")}
            value={String(summary.critical_findings)}
            highlight={summary.critical_findings > 0}
          />
        </div>
      )}

      {/* Appointments reception booked for radiology */}
      <div className="mb-6">
        <ScheduledAppointments appointmentType="radiology" />
      </div>

      {/* Worklist */}
      <h2 className="mb-3 font-semibold text-foreground">{t("worklist")}</h2>
      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          {tc("loading")}
        </div>
      ) : !worklist?.items?.length ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Scan className="mb-3 h-12 w-12 opacity-40" />
          <p className="text-lg">{t("noOrders")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {(worklist.items ?? []).map((item) => {
            const modConfig = MODALITY_CONFIG[item.modality] ?? {
              label: item.modality.toUpperCase(),
              color: "bg-muted text-muted-foreground",
            };

            return (
              <Link
                key={item.id}
                href={`/radiology/${item.id}`}
                className={cn(
                  "flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:shadow-md",
                  item.is_critical && "border-red-400 dark:border-red-700"
                )}
              >
                {/* Modality badge */}
                <div
                  className={cn(
                    "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                    modConfig.color
                  )}
                >
                  {modConfig.label}
                </div>

                {/* Patient & study info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-semibold text-foreground">
                      {item.patient_name ?? "—"}
                    </span>
                    {item.patient_mrn && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {item.patient_mrn}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                    <span className="font-mono">{item.order_number}</span>
                    <span>• {item.study_description}</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{item.body_part}</span>
                    {item.laterality && item.laterality !== "na" && (
                      <span>({t(item.laterality as "left" | "right" | "bilateral")})</span>
                    )}
                    {item.contrast_required && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                        {t("contrast")}
                      </span>
                    )}
                    {item.is_critical && (
                      <span className="rounded bg-red-100 px-1.5 py-0.5 font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                        {t("critical")}
                      </span>
                    )}
                  </div>
                </div>

                {/* Result status */}
                {item.has_result && item.result_status && (
                  <div className="hidden flex-shrink-0 text-center sm:block">
                    <FileText className="mx-auto h-4 w-4 text-muted-foreground" />
                    <div className="text-xs text-muted-foreground">
                      {t(`report${item.result_status.charAt(0).toUpperCase()}${item.result_status.slice(1)}` as "reportDraft" | "reportPreliminary" | "reportFinal")}
                    </div>
                  </div>
                )}

                {/* Priority badge */}
                <span
                  className={cn(
                    "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium uppercase",
                    PRIORITY_STYLES[item.priority] ?? PRIORITY_STYLES.routine
                  )}
                >
                  {t(item.priority as "stat" | "urgent" | "routine")}
                </span>

                {/* Status badge */}
                <span
                  className={cn(
                    "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                    STATUS_STYLES[item.status] ?? STATUS_STYLES.ordered
                  )}
                >
                  {t(`status${item.status.charAt(0).toUpperCase()}${item.status.slice(1).replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())}` as "statusOrdered" | "statusScheduled" | "statusInProgress" | "statusCompleted")}
                </span>

                {/* Time */}
                <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(item.created_at)}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Summary card for dashboard stats.
 *
 * @param props - Card props
 * @returns Summary card component
 */
function SummaryCard({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]",
        highlight && "border-amber-300 dark:border-amber-800"
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p
        className={cn(
          "mt-1 text-xl font-bold",
          highlight ? "text-amber-700 dark:text-amber-400" : "text-foreground"
        )}
      >
        {value}
      </p>
    </div>
  );
}
