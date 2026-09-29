"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Clock,
  DoorOpen,
  Phone,
  Plus,
  ShieldAlert,
  Stethoscope,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useCallNext, useClinicalWorklist } from "@/hooks/useEncounters";
import { usePermissions } from "@/hooks/usePermissions";
import { isServerUnavailable } from "@/lib/api-client";
import { PERMISSIONS } from "@/lib/auth/permissions";
import { canOpenDestination } from "@/lib/navigation";
import { cn, formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { ConsultationPatientLookup } from "@/components/consultation/ConsultationPatientLookup";
import type { Encounter, TriageCategory } from "@aifya/shared";

/** Triage accent down the left edge of a row, matching the OPD queue. */
const TRIAGE_ACCENT: Record<TriageCategory, string> = {
  emergency: "border-l-4 border-l-red-500",
  urgent: "border-l-4 border-l-orange-500",
  standard: "border-l-4 border-l-yellow-500",
  non_urgent: "border-l-4 border-l-green-500",
  dead: "border-l-4 border-l-blue-500",
};

/**
 * How long a patient has been waiting since the nurse finished assessing them.
 *
 * @param encounter - The queued encounter
 * @returns Whole minutes waited, never negative
 */
function waitingMinutes(encounter: Encounter): number {
  const since = encounter.triaged_at ?? encounter.encounter_date;
  const startedAt = new Date(since).getTime();
  if (Number.isNaN(startedAt)) return 0;
  return Math.max(0, Math.floor((Date.now() - startedAt) / 60_000));
}

/**
 * Consultation Room - the clinician's live view of the room itself.
 *
 * The clinical workspace answers "what is my whole day?"; this page answers the
 * narrower question a doctor asks between patients: who is in the room right
 * now and who is waiting to come in. Opening a patient lands on the
 * consultation room tab of their encounter, which is where the examination,
 * the point-of-care tests and the routing to Dental, Physiotherapy, Laboratory
 * or Pharmacy are recorded.
 *
 * @returns Consultation room page
 */
export default function ConsultationRoomPage() {
  const t = useTranslations("consultationRoom");
  const tq = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();
  const [callError, setCallError] = useState("");

  const permissions = usePermissions();
  const { canSeeClinical, hasPermission } = permissions;
  const canConsult = hasPermission(PERMISSIONS.CLINICAL_CONSULT);

  // Without clinical.view the API answers 403; do not ask and then show an
  // error where an explanation belongs.
  // Only assessed patients belong here: the room hands out consultations, and
  // a patient still with OPD has nothing for the doctor to read yet.
  const { data, isLoading, isError, error } = useClinicalWorklist(
    undefined,
    undefined,
    { enabled: canSeeClinical, triaged: true },
  );
  const callNext = useCallNext();

  const counts = data?.counts;
  const items = data?.items ?? [];
  const inRoom = items.filter((item) => item.status === "in_consultation");
  // Triaged and still queued: the patients the room is holding for a doctor.
  const waiting = items.filter((item) => item.status === "waiting");
  const waitingCount = counts?.waiting ?? waiting.length;

  /** Call the next waiting patient and open their consultation room. */
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

  const cards = [
    {
      key: "in_consultation",
      label: tq("inConsultation"),
      value: inRoom.length,
      accent: "text-blue-600 dark:text-blue-400",
    },
    {
      key: "waiting",
      label: t("waitingTitle"),
      value: counts?.waiting ?? 0,
      accent: "text-amber-600 dark:text-amber-400",
    },
    {
      key: "completed",
      label: tq("completed"),
      value: counts?.completed ?? 0,
      accent: "text-green-600 dark:text-green-400",
    },
  ];

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

  const callNextButton = (
    <button
      type="button"
      onClick={handleCallNext}
      disabled={callNext.isPending}
      className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
    >
      <Phone className="h-4 w-4" />
      {callNext.isPending ? tq("callingNext") : tq("callNext")}
    </button>
  );

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={Stethoscope}
        title={t("title")}
        subtitle={t("subtitle")}
        badge={inRoom.length}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <>
            {canConsult && callNextButton}
            {canOpenDestination("/patients/register", permissions) && (
              <Link
                href="/patients/register"
                className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
              >
                <Plus className="h-4 w-4" />
                {tq("newEncounter")}
              </Link>
            )}
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

      {isError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-800 dark:text-red-200">
            {isServerUnavailable(error) ? t("serverDown") : t("loadFailed")}
          </p>
        </div>
      )}

      {/* A name at the door is not always in today's queue. */}
      <ConsultationPatientLookup />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        {cards.map((card) => (
          <div
            key={card.key}
            className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
          >
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <p className={cn("mt-1 text-2xl font-bold", card.accent)}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* The doctor's real question: who is next, and how long they waited. */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          {t("waitingHeading", { count: waitingCount })}
        </h2>

        {isLoading ? (
          <PageSkeleton />
        ) : waiting.length === 0 ? (
          <EmptyState
            icon={Clock}
            title={t("waitingEmpty")}
            description={t("waitingEmptyHint")}
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("waitingQueue")}</th>
                  <th className="px-4 py-3">{t("waitingPatient")}</th>
                  <th className="px-4 py-3">{t("waitingTime")}</th>
                  <th className="px-4 py-3">{t("waitingStatus")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {waiting.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/50">
                    <td
                      className={cn(
                        "px-4 py-3",
                        TRIAGE_ACCENT[item.triage_category ?? "non_urgent"],
                      )}
                    >
                      <Link
                        href={`/opd/${item.id}?tab=consultation`}
                        className="inline-flex h-8 min-w-8 items-center justify-center rounded-lg bg-muted px-2 text-xs font-bold text-foreground transition-colors hover:bg-muted/70"
                      >
                        {item.queue_number ?? "\u2014"}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/opd/${item.id}?tab=consultation`}
                        className="font-medium text-foreground hover:underline"
                      >
                        {item.patient_name ?? "\u2014"}
                      </Link>
                      {item.patient_mrn && (
                        <div className="font-mono text-xs text-muted-foreground">
                          {item.patient_mrn}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {t("waitingMinutes", { minutes: waitingMinutes(item) })}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
                        {t("waitingReady")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          {t("inRoom")}
        </h2>
        <p className="mb-3 text-xs text-muted-foreground">{t("inRoomHint")}</p>

        {isLoading ? (
          <PageSkeleton />
        ) : inRoom.length === 0 ? (
          <EmptyState
            icon={DoorOpen}
            title={t("empty")}
            description={t("emptyHint")}
            action={canConsult ? callNextButton : undefined}
          />
        ) : (
          <div className="space-y-3">
            {inRoom.map((item) => (
              <Link
                key={item.id}
                href={`/opd/${item.id}?tab=consultation`}
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
                  {item.department_name ?? t("unassigned")}
                </span>

                {item.attending_doctor_name && (
                  <span className="hidden text-xs text-muted-foreground xl:inline">
                    {t("with")} {item.attending_doctor_name}
                  </span>
                )}

                <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(item.encounter_date)}
                </div>

                <span className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow transition-all">
                  {t("openRoom")}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
