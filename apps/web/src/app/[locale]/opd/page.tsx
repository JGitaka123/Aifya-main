"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  Stethoscope,
  Phone,
  Clock,
  AlertTriangle,
  Plus,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useOPDQueue, useCallNext } from "@/hooks/useEncounters";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import type { TriageCategory } from "@aifya/shared";

/** Map triage categories to StatusBadge variants and border colors for queue cards. */
const TRIAGE_MAP: Record<TriageCategory, {
  variant: "red-solid" | "orange-solid" | "yellow-solid" | "green-solid" | "blue-solid";
  border: string;
  label: string;
}> = {
  emergency: {
    variant: "red-solid",
    border: "border-red-400 dark:border-red-700",
    label: "triageEmergency",
  },
  urgent: {
    variant: "orange-solid",
    border: "border-orange-400 dark:border-orange-700",
    label: "triageUrgent",
  },
  standard: {
    variant: "yellow-solid",
    border: "border-yellow-400 dark:border-yellow-600",
    label: "triageStandard",
  },
  non_urgent: {
    variant: "green-solid",
    border: "border-green-400 dark:border-green-700",
    label: "triageNonUrgent",
  },
  dead: {
    variant: "blue-solid",
    border: "border-blue-400 dark:border-blue-700",
    label: "triageDead",
  },
};

/** Map encounter statuses to StatusBadge variants. */
const STATUS_VARIANT: Record<string, "warning" | "info" | "success" | "purple" | "default" | "error"> = {
  waiting: "warning",
  in_consultation: "info",
  completed: "success",
  admitted: "purple",
  discharged: "default",
  cancelled: "error",
};

/**
 * OPD Queue page with SATS triage colors and real-time updates.
 * Queue auto-refreshes every 15 seconds.
 * @returns OPD queue page
 */
export default function OPDQueuePage() {
  const t = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("");
  // Set when the API refuses to start a consultation, e.g. the reception
  // consultation fee is still outstanding.
  const [callError, setCallError] = useState<string>("");

  const { data, isLoading } = useOPDQueue(statusFilter || undefined);
  const callNext = useCallNext();

  /**
   * Call the next patient in queue and navigate to their encounter.
   */
  const handleCallNext = () => {
    setCallError("");
    callNext.mutate(undefined, {
      onSuccess: (encounter) => {
        router.push(`/opd/${encounter.id}`);
      },
      onError: (err: Error) => {
        setCallError(err.message || t("callNextFailed"));
      },
    });
  };

  const statusOptions: { value: string; label: string }[] = [
    { value: "", label: tc("actions") },
    { value: "waiting", label: t("waiting") },
    { value: "in_consultation", label: t("inConsultation") },
    { value: "completed", label: t("completed") },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Page header */}
      <PageHeader
        icon={Stethoscope}
        title={t("queue")}
        badge={data?.total}
        breadcrumbs={[{ label: t("queue") }]}
        actions={
          <>
            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Call next button */}
            <button
              onClick={handleCallNext}
              disabled={callNext.isPending}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Phone className="h-4 w-4" />
              {callNext.isPending ? t("callingNext") : t("callNext")}
            </button>

            {/* New encounter link */}
            <Link
              href="/opd/new"
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <Plus className="h-4 w-4" />
              {t("newEncounter")}
            </Link>
          </>
        }
      />

      {/* Consultation fee gate / call-next failure */}
      {callError && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-sm text-amber-800 dark:text-amber-200">{callError}</p>
        </div>
      )}

      {/* Triage legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(TRIAGE_MAP).map(([key, triage]) => (
          <StatusBadge key={key} variant={triage.variant} size="xs">
            {t(triage.label as Parameters<typeof t>[0])}
          </StatusBadge>
        ))}
      </div>

      {/* Queue list */}
      {isLoading ? (
        <PageSkeleton />
      ) : !data?.items.length ? (
        <EmptyState
          icon={Users}
          title={t("queueEmpty")}
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((encounter) => {
            const triage = TRIAGE_MAP[encounter.triage_category ?? "non_urgent"];

            return (
              <Link
                key={encounter.id}
                href={`/opd/${encounter.id}`}
                className={cn(
                  "flex items-center gap-4 rounded-lg border p-4 transition-all",
                  "bg-card shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-card-hover)]",
                  triage.border,
                )}
              >
                {/* Patient avatar */}
                <Avatar
                  name={encounter.patient_name ?? "?"}
                  size="lg"
                />

                {/* Queue number */}
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-muted text-sm font-bold text-foreground">
                  {encounter.queue_number ?? "-"}
                </div>

                {/* Patient info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-semibold text-foreground">
                      {encounter.patient_name ?? "\u2014"}
                    </span>
                    {encounter.patient_mrn && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {encounter.patient_mrn}
                      </span>
                    )}
                  </div>
                  {encounter.chief_complaint && (
                    <p className="mt-0.5 truncate text-sm text-muted-foreground">
                      {encounter.chief_complaint}
                    </p>
                  )}
                </div>

                {/* Triage badge */}
                <StatusBadge
                  variant={triage.variant}
                  size="sm"
                  className="hidden sm:inline-flex"
                >
                  {t(triage.label as Parameters<typeof t>[0])}
                </StatusBadge>

                {/* Status badge */}
                <StatusBadge
                  variant={STATUS_VARIANT[encounter.status] ?? "warning"}
                  size="sm"
                  dot
                >
                  {t(
                    encounter.status === "in_consultation"
                      ? "inConsultation"
                      : (encounter.status as Parameters<typeof t>[0]),
                  )}
                </StatusBadge>

                {/* Time */}
                <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(encounter.created_at)}
                </div>

                {/* Priority indicator for emergencies */}
                {encounter.priority >= 4 && (
                  <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-500" />
                )}
                {/* Open encounter CTA */}
                <span className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow transition-all">
                  {tc("open")}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
