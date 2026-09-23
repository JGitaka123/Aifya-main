"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ClipboardList,
  Clock,
  Phone,
  Plus,
  Stethoscope,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useCallNext, useClinicalWorklist } from "@/hooks/useEncounters";
import { cn, formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import type { ClinicalScope, TriageCategory } from "@aifya/shared";

/** Triage accent down the left edge of a row, matching the OPD queue. */
const TRIAGE_ACCENT: Record<TriageCategory, string> = {
  emergency: "border-l-4 border-l-red-500",
  urgent: "border-l-4 border-l-orange-500",
  standard: "border-l-4 border-l-yellow-500",
  non_urgent: "border-l-4 border-l-green-500",
  dead: "border-l-4 border-l-blue-500",
};

/** Badge look for each encounter status. */
const STATUS_VARIANT: Record<
  string,
  "warning" | "info" | "success" | "purple" | "default" | "error"
> = {
  waiting: "warning",
  in_consultation: "info",
  completed: "success",
  admitted: "purple",
  discharged: "default",
  cancelled: "error",
};

/** Scopes a clinician can read, in picker order. */
const SCOPES: readonly ClinicalScope[] = ["mine", "department", "facility"];

/**
 * Clinical Workspace — the clinician's own day.
 *
 * A clinician does not need the whole hospital. Reception routes a patient to a
 * department, and sometimes to a named clinician; this page shows exactly those
 * patients, scoped to the clinician's own work, their unit, or (for an
 * administrator) the facility. Opening a patient leads into the existing
 * encounter, where the assessment, diagnosis and orders already live.
 *
 * @returns Clinical workspace page
 */
export default function ClinicalWorkspacePage() {
  const t = useTranslations("clinical");
  const tq = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();

  // Empty means "let the API decide for this role"; the picker then shows the
  // scope the server resolved instead of guessing on the client.
  const [scope, setScope] = useState<ClinicalScope | "">("");
  const [status, setStatus] = useState("");
  const [callError, setCallError] = useState("");

  const { data, isLoading, isError } = useClinicalWorklist(
    scope || undefined,
    status || undefined,
  );
  const callNext = useCallNext();

  const counts = data?.counts;
  const items = data?.items ?? [];
  const facilityWide = data?.facility_wide ?? false;
  const effectiveScope: ClinicalScope = scope || data?.scope || "mine";

  const scopeLabel: Record<ClinicalScope, string> = {
    mine: t("scopeMine"),
    department: t("scopeDepartment"),
    facility: t("scopeFacility"),
  };

  const statusLabel = (value: string): string =>
    value === "in_consultation"
      ? tq("inConsultation")
      : tq(value as Parameters<typeof tq>[0]);

  /**
   * Call the next waiting patient and go straight to their encounter.
   */
  const handleCallNext = () => {
    setCallError("");
    callNext.mutate(undefined, {
      onSuccess: (encounter) => {
        router.push(`/opd/${encounter.id}`);
      },
      onError: (err: Error) => {
        setCallError(err.message || tq("callNextFailed"));
      },
    });
  };

  const cards = [
    {
      key: "waiting",
      label: tq("waiting"),
      value: counts?.waiting ?? 0,
      accent: "text-amber-600 dark:text-amber-400",
    },
    {
      key: "in_consultation",
      label: tq("inConsultation"),
      value: counts?.in_consultation ?? 0,
      accent: "text-blue-600 dark:text-blue-400",
    },
    {
      key: "completed",
      label: tq("completed"),
      value: counts?.completed ?? 0,
      accent: "text-green-600 dark:text-green-400",
    },
    {
      key: "total",
      label: t("total"),
      value: counts?.total ?? 0,
      accent: "text-foreground",
    },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={ClipboardList}
        title={t("title")}
        subtitle={t("subtitle")}
        badge={counts?.total}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <>
            <select
              value={effectiveScope}
              onChange={(event) =>
                setScope(event.target.value as ClinicalScope)
              }
              aria-label={t("scopeLabel")}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {SCOPES.map((option) => (
                <option
                  key={option}
                  value={option}
                  disabled={option === "facility" && !facilityWide}
                >
                  {scopeLabel[option]}
                </option>
              ))}
            </select>

            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-label={tq("status")}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="">{t("allStatuses")}</option>
              <option value="waiting">{tq("waiting")}</option>
              <option value="in_consultation">{tq("inConsultation")}</option>
              <option value="completed">{tq("completed")}</option>
            </select>

            <button
              type="button"
              onClick={handleCallNext}
              disabled={callNext.isPending}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Phone className="h-4 w-4" />
              {callNext.isPending ? tq("callingNext") : tq("callNext")}
            </button>

            <Link
              href="/opd/new"
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <Plus className="h-4 w-4" />
              {tq("newEncounter")}
            </Link>
          </>
        }
      />

      {callError && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {callError}
          </p>
        </div>
      )}

      {/* Who this workspace belongs to: profession, speciality and unit are
          data on the staff record, not a separate role per department. */}
      {data?.clinician && data.clinician.name && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-border bg-card px-5 py-3 shadow-[var(--shadow-card)]">
          <Stethoscope className="h-4 w-4 text-primary" />
          <span className="font-semibold text-foreground">
            {data.clinician.name}
          </span>
          {data.clinician.profession && (
            <StatusBadge variant="info" size="xs">
              {data.clinician.profession}
            </StatusBadge>
          )}
          {data.clinician.specialty && (
            <span className="text-xs text-muted-foreground">
              {data.clinician.specialty}
            </span>
          )}
          <span className="text-xs text-muted-foreground">
            {data.clinician.department_name ?? t("noDepartment")}
          </span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-800 dark:text-red-200">
            {t("loadFailed")}
          </p>
        </div>
      )}

      {/* My queue: the counts describe the whole scoped day, so they stay put
          while the status filter narrows the list below. */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          {t("myQueue")}
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {cards.map((card) => {
            const active =
              card.key === "total" ? status === "" : status === card.key;
            return (
              <button
                key={card.key}
                type="button"
                onClick={() =>
                  setStatus(card.key === "total" ? "" : card.key)
                }
                className={cn(
                  "rounded-xl border bg-card p-4 text-left shadow-[var(--shadow-card)] transition-all hover:shadow-[var(--shadow-card-hover)]",
                  active ? "border-primary" : "border-border",
                )}
              >
                <p className="text-xs text-muted-foreground">{card.label}</p>
                <p className={cn("mt-1 text-2xl font-bold", card.accent)}>
                  {card.value}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Today's patients */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          {t("todayPatients")}
        </h2>

        {isLoading ? (
          <PageSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Users}
            title={t("noPatients")}
            description={t("noPatientsHint")}
          />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <Link
                key={item.id}
                href={`/opd/${item.id}`}
                className={cn(
                  "flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all hover:shadow-[var(--shadow-card-hover)]",
                  TRIAGE_ACCENT[item.triage_category ?? "non_urgent"],
                )}
              >
                <Avatar name={item.patient_name ?? "?"} size="lg" />

                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-muted text-sm font-bold text-foreground">
                  {item.queue_number ?? "-"}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-semibold text-foreground">
                      {item.patient_name ?? "\u2014"}
                    </span>
                    {item.patient_mrn && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {item.patient_mrn}
                      </span>
                    )}
                  </div>
                  {item.chief_complaint && (
                    <p className="mt-0.5 truncate text-sm text-muted-foreground">
                      {item.chief_complaint}
                    </p>
                  )}
                </div>

                <span className="hidden flex-shrink-0 items-center gap-1 text-xs text-muted-foreground md:flex">
                  <Stethoscope className="h-3 w-3" />
                  {item.department_name ?? t("unclaimed")}
                </span>

                {item.attending_doctor_name && (
                  <span className="hidden text-xs text-muted-foreground xl:inline">
                    {t("with")} {item.attending_doctor_name}
                  </span>
                )}

                <StatusBadge
                  variant={STATUS_VARIANT[item.status] ?? "warning"}
                  size="sm"
                  dot
                >
                  {statusLabel(item.status)}
                </StatusBadge>

                <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(item.encounter_date)}
                </div>

                <span className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow transition-all">
                  {tc("open")}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}