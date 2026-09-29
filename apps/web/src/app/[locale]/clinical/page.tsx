"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ClipboardList,
  Clock,
  Phone,
  Plus,
  Search,
  ShieldAlert,
  Siren,
  Stethoscope,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useCallInPatient,
  useCallNext,
  useClinicalWorklist,
  useDepartmentLoad,
} from "@/hooks/useEncounters";
import { usePermissions } from "@/hooks/usePermissions";
import { isServerUnavailable } from "@/lib/api-client";
import { PERMISSIONS } from "@/lib/auth/permissions";
import { cn, formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { TabGroup } from "@/components/ui/TabGroup";
import { MyLeavePanel } from "@/components/clinical/MyLeavePanel";
import type { ClinicalScope, TriageCategory } from "@aifya/shared";

/** Triage accent down the left edge of a row, matching the OPD queue. */
const TRIAGE_ACCENT: Record<TriageCategory, string> = {
  emergency: "border-l-4 border-l-red-500",
  urgent: "border-l-4 border-l-orange-500",
  standard: "border-l-4 border-l-yellow-500",
  non_urgent: "border-l-4 border-l-green-500",
  dead: "border-l-4 border-l-blue-500",
};

/** Emergency-origin chip, coloured by the ED triage band on the visit. */
const EMERGENCY_CHIP: Record<string, string> = {
  red: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  orange:
    "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  yellow:
    "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  green:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  blue: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
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
 * Clinical Workspace - the receiving department's queue.
 *
 * Aifya already knows who is signed in, and their staff record says which unit
 * they belong to. So this page opens on that unit's queue rather than asking a
 * dentist to search for their own name: the patients routed to Dental by the
 * consultation room are simply waiting when the dentist arrives.
 *
 * Reception registers and routes, the consultation room decides where a patient
 * should go, and this page is where the receiving unit works that queue and
 * records the outcome. Opening a patient leads into the existing encounter,
 * where the assessment, diagnosis and orders already live.
 *
 * @returns Clinical workspace page
 */
export default function ClinicalWorkspacePage() {
  const t = useTranslations("clinical");
  const tq = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();

  // Empty means "not chosen yet": the server picks for the role, and the page
  // then settles on the clinician's own unit once it knows which that is.
  const [scope, setScope] = useState<ClinicalScope | "">("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [unit, setUnit] = useState("");
  const [callError, setCallError] = useState("");
  const [tab, setTab] = useState<"patients" | "leave">("patients");
  // Settle the scope once. After that the picker is the clinician's to use.
  const settled = useRef(false);

  const { canSeeClinical, hasPermission } = usePermissions();
  const canConsult = hasPermission(PERMISSIONS.CLINICAL_CONSULT);

  const { data, isLoading, isError, error } = useClinicalWorklist(
    scope || undefined,
    status || undefined,
    {
      enabled: canSeeClinical,
      search: query || undefined,
      departmentId: unit || undefined,
    },
  );
  const callNext = useCallNext();
  const callIn = useCallInPatient();

  const counts = data?.counts;
  const items = data?.items ?? [];
  const facilityWide = data?.facility_wide ?? false;
  const myDepartment = data?.clinician.department_name ?? null;
  const myDepartmentId = data?.clinician.department_id ?? null;
  const { data: departmentLoad } = useDepartmentLoad(
    canSeeClinical && facilityWide,
  );

  // A clinician works their own unit, so open there instead of on "my
  // patients" - a patient routed to Dental and not yet claimed belongs to the
  // dentist who is on duty, not to nobody. Administrators keep the facility.
  useEffect(() => {
    if (settled.current || scope !== "" || !data) return;
    settled.current = true;
    if (data.facility_wide) setScope("facility");
    else if (data.clinician.department_id) setScope("department");
  }, [data, scope]);

  // The box filters on the server, so wait for a pause in typing rather than
  // firing a query per keystroke.
  useEffect(() => {
    const id = window.setTimeout(() => setQuery(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

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
        router.push(`/opd/${encounter.id}?tab=consultation`);
      },
      onError: (err: Error) => {
        setCallError(err.message || tq("callNextFailed"));
      },
    });
  };

  /**
   * Bring one chosen patient into the room, rather than the next in the queue.
   *
   * @param encounterId - Encounter UUID the clinician picked off the list
   */
  const handleCallIn = (encounterId: string) => {
    setCallError("");
    callIn.mutate(encounterId, {
      onSuccess: (encounter) => {
        router.push(`/opd/${encounter.id}?tab=consultation`);
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
      label: t("inTreatment"),
      value: counts?.in_consultation ?? 0,
      accent: "text-blue-600 dark:text-blue-400",
    },
    {
      key: "completed",
      label: t("done"),
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

  const scopeLabel: Record<ClinicalScope, string> = {
    mine: t("scopeMine"),
    department: t("scopeDepartment"),
    facility: t("scopeFacility"),
  };

  if (!canSeeClinical) {
    return (
      <div className="mx-auto max-w-2xl animate-[fade-in_0.3s_ease-out] p-5 sm:p-6 lg:p-8">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-card p-10 text-center shadow-[var(--shadow-card)]">
          <ShieldAlert className="h-12 w-12 text-amber-500" />
          <h1 className="text-lg font-bold text-foreground">
            {t("noAccessTitle")}
          </h1>
          <p className="max-w-md text-sm text-muted-foreground">
            {t("noAccessHint")}
          </p>
          <Link href="/" className="text-sm text-primary hover:underline">
            {tc("home")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={ClipboardList}
        title={myDepartment ? t("titleWithUnit", { unit: myDepartment }) : t("title")}
        subtitle={t("subtitle")}
        badge={counts?.total}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          tab === "patients" ? (
            <>
              {/* Only an administrator has more than one queue to choose
                  between, so only they get the scope picker. */}
              {facilityWide && (
                <select
                  value={scope || "facility"}
                  onChange={(event) => {
                    settled.current = true;
                    setUnit("");
                    setScope(event.target.value as ClinicalScope);
                  }}
                  aria-label={t("scopeLabel")}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {SCOPES.map((option) => (
                    <option key={option} value={option}>
                      {scopeLabel[option]}
                    </option>
                  ))}
                </select>
              )}

              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                aria-label={tc("status")}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">{t("allStatuses")}</option>
                <option value="waiting">{tq("waiting")}</option>
                <option value="in_consultation">{t("inTreatment")}</option>
                <option value="completed">{t("done")}</option>
              </select>

              {canConsult && (
                <button
                  type="button"
                  onClick={handleCallNext}
                  disabled={callNext.isPending}
                  className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
                >
                  <Phone className="h-4 w-4" />
                  {callNext.isPending ? tq("callingNext") : tq("callNext")}
                </button>
              )}

              <Link
                href="/patients/register"
                className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
              >
                <Plus className="h-4 w-4" />
                {tq("newEncounter")}
              </Link>
            </>
          ) : null
        }
      />

      {/* Two halves: today's patients, and the clinician's own leave. A
          doctor asks for leave here instead of being sent to the HR module. */}
      <TabGroup
        tabs={[
          { key: "patients", label: t("myPatients") },
          { key: "leave", label: t("myLeave") },
        ]}
        activeTab={tab}
        onTabChange={(key) => setTab(key as "patients" | "leave")}
        variant="underline"
      />

      {tab === "leave" && <MyLeavePanel />}

      {tab === "patients" && (
        <>
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
              <span className="text-xs font-medium text-foreground">
                {myDepartment ?? t("noDepartment")}
              </span>
            </div>
          )}

          {isError && (
            <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
              <p className="text-sm text-red-800 dark:text-red-200">
                {isServerUnavailable(error) ? t("serverDown") : t("loadFailed")}
              </p>
            </div>
          )}

          {/* Department load: an administrator sees every unit side by side and
              can narrow the list to one of them. A clinician is already
              looking at their own unit, so the strip would be a single card. */}
          {facilityWide && departmentLoad && departmentLoad.length > 0 && (
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-foreground">
                  {t("departmentLoad")}
                </h2>
                {unit && (
                  <button
                    type="button"
                    onClick={() => setUnit("")}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    {t("clearFilter")}
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {departmentLoad.map((row) => {
                  const mine = row.department_id === myDepartmentId;
                  const active = unit === row.department_id;
                  return (
                    <button
                      key={row.department_id}
                      type="button"
                      onClick={() =>
                        setUnit(active ? "" : row.department_id)
                      }
                      aria-pressed={active}
                      className={cn(
                        "rounded-xl border bg-card p-4 text-left shadow-[var(--shadow-card)] transition-all hover:shadow-[var(--shadow-card-hover)]",
                        active
                          ? "border-primary"
                          : mine
                            ? "border-primary/50"
                            : "border-border",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <p className="truncate text-xs text-muted-foreground">
                          {row.name}
                        </p>
                        {mine && (
                          <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold text-primary-foreground">
                            {t("yourUnit")}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-2xl font-bold text-foreground">
                        {row.total}
                      </p>
                      <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                        <span>
                          {tq("waiting")} {row.waiting}
                        </span>
                        <span>
                          {t("inTreatment")} {row.in_consultation}
                        </span>
                        <span>
                          {t("done")} {row.completed}
                        </span>
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* The queue itself. The counts describe the whole scoped day, so
              they stay put while the status filter narrows the list below. */}
          <div>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <h2 className="text-sm font-semibold text-foreground">
                {t("myQueue")}
              </h2>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={t("searchPlaceholder")}
                  aria-label={t("searchLabel")}
                  className="w-72 rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm text-foreground shadow-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>

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
                    <p className="text-xs text-muted-foreground">
                      {card.label}
                    </p>
                    <p className={cn("mt-1 text-2xl font-bold", card.accent)}>
                      {card.value}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold text-foreground">
              {t("todayPatients")}
            </h2>

            {isLoading ? (
              <PageSkeleton />
            ) : items.length === 0 ? (
              <EmptyState
                icon={Users}
                title={query ? t("searchNoMatch") : t("noPatients")}
                description={query ? t("searchNoMatchHint") : t("noPatientsHint")}
              />
            ) : (
              <div className="space-y-3">
                {items.map((item) => {
                  const emergencyHref = item.emergency_visit_id
                    ? `/emergency/${item.emergency_visit_id}`
                    : null;
                  return (
                    <div
                      key={item.id}
                      className={cn(
                        "flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all hover:shadow-[var(--shadow-card-hover)]",
                        TRIAGE_ACCENT[item.triage_category ?? "non_urgent"],
                      )}
                    >
                      <Link
                        href={`/opd/${item.id}`}
                        className="flex min-w-0 flex-1 items-center gap-4"
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
                            {item.source_department_name && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                                {t("referredFrom")}{" "}
                                {item.source_department_name}
                              </span>
                            )}
                            {emergencyHref && (
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                                  EMERGENCY_CHIP[
                                    item.emergency_triage_color ?? "yellow"
                                  ] ?? "bg-muted text-muted-foreground",
                                )}
                              >
                                <Siren className="h-3 w-3" />
                                {t("emergencyBadge")}
                                {item.emergency_visit_number && (
                                  <span className="font-mono normal-case">
                                    {item.emergency_visit_number}
                                  </span>
                                )}
                              </span>
                            )}
                          </div>
                          {item.chief_complaint && (
                            <p className="mt-0.5 truncate text-sm text-muted-foreground">
                              {item.chief_complaint}
                            </p>
                          )}
                        </div>
                      </Link>

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

                      {emergencyHref && (
                        <Link
                          href={emergencyHref}
                          className="inline-flex flex-shrink-0 items-center gap-1 rounded-full border border-red-300 px-3 py-1 text-xs font-semibold text-red-700 transition-colors hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950"
                        >
                          <Siren className="h-3 w-3" />
                          {t("openEmergency")}
                        </Link>
                      )}

                      {/* A patient the nurse has not assessed cannot be
                          called in, so the row says so instead of offering a
                          button the server would refuse. */}
                      {item.status === "waiting" && !item.triaged_at && (
                        <span className="inline-flex flex-shrink-0 items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                          {t("waitingForOpd")}
                        </span>
                      )}

                      {canConsult &&
                        item.status === "waiting" &&
                        item.triaged_at && (
                          <button
                            type="button"
                            onClick={() => handleCallIn(item.id)}
                            disabled={callIn.isPending}
                            className="inline-flex flex-shrink-0 items-center gap-1 rounded-full border border-primary px-3 py-1 text-xs font-semibold text-primary transition-colors hover:bg-primary/10 disabled:opacity-50"
                          >
                            <Phone className="h-3 w-3" />
                            {callIn.isPending && callIn.variables === item.id
                              ? t("callingIn")
                              : t("callIn")}
                          </button>
                        )}

                      <Link
                        href={`/opd/${item.id}`}
                        className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow transition-all"
                      >
                        {tc("open")}
                      </Link>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
