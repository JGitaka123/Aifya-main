"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Stethoscope,
  Phone,
  Clock,
  AlertTriangle,
  Plus,
  Users,
  ClipboardCheck,
  Loader2,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useOPDQueue,
  useDepartments,
  useCompleteAssessment,
} from "@/hooks/useEncounters";
import { useCallNext as useQueueCallNext, useQueueBoard } from "@/hooks/useQueue";
import { usePermissions } from "@/hooks/usePermissions";
import { PERMISSIONS } from "@/lib/auth/permissions";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { QueueAnnouncer } from "@/components/queue/QueueAnnouncer";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
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
 * Hand a patient from OPD to the consultation room.
 *
 * Recording vitals already completes the assessment; this covers the visit
 * that needed no measurements, so a patient is never stuck in a stage nobody
 * can clear.
 *
 * @param props.encounterId - Encounter to hand over
 * @returns Assessment hand-off button with an inline error
 */
function OpdAssessmentButton({ encounterId }: { encounterId: string }) {
  const t = useTranslations("opd");
  const complete = useCompleteAssessment(encounterId);
  const [error, setError] = useState("");

  return (
    <div className="flex w-36 flex-col items-center justify-center gap-1">
      <button
        type="button"
        onClick={() => {
          setError("");
          complete.mutate(undefined, {
            onError: (err: Error) =>
              setError(err.message || t("assessmentFailed")),
          });
        }}
        disabled={complete.isPending}
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-sm transition-colors hover:bg-muted disabled:opacity-50"
      >
        {complete.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ClipboardCheck className="h-4 w-4" />
        )}
        {complete.isPending ? t("completingAssessment") : t("completeAssessment")}
      </button>
      {error && (
        <span className="text-center text-[10px] leading-tight text-red-600 dark:text-red-400">
          {error}
        </span>
      )}
    </div>
  );
}

/**
 * OPD Queue page with SATS triage colors and real-time updates.
 * Queue auto-refreshes every 15 seconds.
 * @returns OPD queue page
 */
export default function OPDQueuePage() {
  const t = useTranslations("opd");
  const tc = useTranslations("common");
  const tq = useTranslations("queue");
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState<string>("");
  // One patient journey, two desks. "assessment" is the nurse taking the
  // observations; "consultation" is the doctor's waiting list. OPD opens on the
  // nurses' list, because that is the work this screen exists for.
  const [stageFilter, setStageFilter] = useState<string>("assessment");
  // The queue can be read for the whole facility or for one unit, so a doctor
  // (or reception) can look at exactly one department's patients.
  const [departmentFilter, setDepartmentFilter] = useState<string>("");
  // Set when the API refuses to start a consultation, e.g. the reception
  // consultation fee is still outstanding.
  const [callError, setCallError] = useState<string>("");

  const { data, isLoading } = useOPDQueue(
    statusFilter || undefined,
    departmentFilter || undefined,
    stageFilter || undefined
  );
  const { data: departmentDirectory } = useDepartments();
  const departments = departmentDirectory ?? [];
  const callNext = useQueueCallNext();
  // What the button will actually pull: the live waiting count for the chosen
  // unit. Nothing waiting means nothing to call, so the button says so instead
  // of answering with a 404 and silence. Left alone when the board cannot be
  // read (a role without board permission), so the old button still works.
  const { data: queueBoard } = useQueueBoard({
    departmentId: departmentFilter || undefined,
  });
  const queueEmpty = queueBoard !== undefined && queueBoard.waiting === 0;
  // Nursing and clinicians both run the line: the nurse calls the next
  // waiting patient up by ticket number, and the same button is offered
  // to a clinician when no nurse is on shift.
  const { hasPermission } = usePermissions();
  const canCallNext =
    hasPermission(PERMISSIONS.TRIAGE_RECORD) ||
    hasPermission(PERMISSIONS.CLINICAL_CONSULT);
  // The nurse closes the assessment; a clinician may do it too when no nurse
  // is on shift, which is why the server accepts either permission.
  const canTriage = hasPermission(PERMISSIONS.TRIAGE_RECORD);

  /**
   * Call the next waiting patient in and announce their ticket number.
   */
  const handleCallNext = () => {
    setCallError("");
    callNext.mutate(
      {
        department_id: departmentFilter || undefined,
        announce: true,
      },
      {
        onSuccess: (ticket) => {
          toast.success(tq("calledNext", { number: ticket.ticket_number }));
        },
        onError: (err: Error) => {
          if (err instanceof ApiError && err.status === 404) {
            toast.info(tq("nobodyWaiting"));
            return;
          }
          setCallError(err.message || t("callNextFailed"));
        },
      },
    );
  };

  const stageOptions: { value: string; label: string }[] = [
    { value: "", label: t("allStages") },
    { value: "assessment", label: t("awaitingOpd") },
    { value: "consultation", label: t("readyForDoctor") },
  ];

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
        subtitle={t("opdSubtitle")}
        badge={data?.total}
        breadcrumbs={[{ label: t("queue") }]}
        actions={
          <>
            {/* Department filter */}
            <select
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="">{t("allDepartments")}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>

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

            {/* Call the next waiting patient in by ticket number. */}
            {canCallNext && (
              <button
                onClick={handleCallNext}
                disabled={callNext.isPending || queueEmpty}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                <Phone className="h-4 w-4" />
                {callNext.isPending
            ? t("callingNext")
            : queueEmpty
              ? tq("nobodyWaiting")
              : t("callNext")}
              </button>
            )}

              <QueueAnnouncer />

            {/* New encounter link */}
            <Link
              href="/patients/register"
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <Plus className="h-4 w-4" />
              {t("newEncounter")}
            </Link>
          </>
        }
      />

      {/* Stage switch: still with OPD, or already handed to the doctor */}
      <div className="flex flex-wrap items-center gap-2">
        {stageOptions.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setStageFilter(opt.value)}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
              stageFilter === opt.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

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
            const assessed = Boolean(encounter.triaged_at);

            return (
              <div key={encounter.id} className="flex items-stretch gap-2">
                <Link
                  href={`/opd/${encounter.id}`}
                  className={cn(
                    "flex min-w-0 flex-1 items-center gap-4 rounded-lg border p-4 transition-all",
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

                  {/* Where the patient is between OPD and the doctor */}
                  <StatusBadge
                    variant={assessed ? "success" : "warning"}
                    size="sm"
                    className="hidden md:inline-flex"
                  >
                    {assessed ? t("triaged") : t("awaitingOpd")}
                  </StatusBadge>

                  {/* Who took the observations, once they have been taken */}
                  {assessed && encounter.nurse_name && (
                    <span className="hidden text-xs text-muted-foreground lg:inline">
                      {t("triagedBy", { name: encounter.nurse_name })}
                    </span>
                  )}

                  {/* Where reception directed the patient */}
                  <span className="hidden flex-shrink-0 items-center gap-1 text-xs text-muted-foreground xl:flex">
                    <Stethoscope className="h-3 w-3" />
                    {encounter.department_name ?? t("unassignedDepartment")}
                  </span>

                  {encounter.attending_doctor_name && (
                    <span className="hidden text-xs text-muted-foreground xl:inline">
                      {encounter.attending_doctor_name}
                    </span>
                  )}

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
                  {/* The nurse's next action on this patient */}
                  <span className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow transition-all">
                    {assessed ? tc("open") : t("triageAction")}
                  </span>
                </Link>
                {!assessed && canTriage && (
                  <OpdAssessmentButton encounterId={encounter.id} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
