"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, FlaskConical, Users } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useTrial, useTrialParticipants } from "@/hooks/useClinicalTrials";
import { AdverseEventsPanel } from "@/components/trials/AdverseEventsPanel";
import { AIScreeningPanel } from "@/components/trials/AIScreeningPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn } from "@/lib/utils";
import type { TrialStatus } from "@aifya/shared";

const STATUS_VARIANT: Record<
  TrialStatus,
  "neutral" | "blue" | "success" | "purple" | "teal" | "warning" | "error"
> = {
  setup: "neutral",
  recruiting: "blue",
  active: "success",
  follow_up: "purple",
  completed: "teal",
  suspended: "warning",
  terminated: "error",
  withdrawn: "neutral",
};

/** Resolve a badge colour for a possibly-unknown status string. */
function statusVariant(
  status: string,
): "neutral" | "blue" | "success" | "purple" | "teal" | "warning" | "error" {
  return STATUS_VARIANT[status as TrialStatus] ?? "neutral";
}

type TabKey = "overview" | "participants" | "adverse_events" | "ai_screening";

/**
 * Single trial detail page: protocol summary, participants, adverse events and
 * AI screening results for one trial.
 *
 * @returns Trial detail page component
 */
export default function TrialDetailPage() {
  const params = useParams<{ id: string }>();
  const trialId = params.id;
  const t = useTranslations("trials");
  const tc = useTranslations("common");
  const [tab, setTab] = useState<TabKey>("overview");

  const { data: trial, isLoading } = useTrial(trialId);
  const { data: participants, isLoading: participantsLoading } =
    useTrialParticipants(trialId);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1500px] p-5 sm:p-6 lg:p-8">
        <p className="py-16 text-center text-sm text-muted-foreground">
          {t("loading")}
        </p>
      </div>
    );
  }

  if (!trial) {
    return (
      <div className="mx-auto max-w-[1500px] p-5 sm:p-6 lg:p-8">
        <EmptyState
          icon={FlaskConical}
          title={t("trialNotFound")}
          description={t("trialNotFoundHint")}
          action={
            <Link
              href="/trials"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("backToTrials")}
            </Link>
          }
        />
      </div>
    );
  }

  const tabs: TabKey[] = [
    "overview",
    "participants",
    "adverse_events",
    "ai_screening",
  ];

  const enrolledCount =
    participants?.items.filter(
      (item) =>
        item.status === "enrolled" ||
        item.status === "active" ||
        item.status === "completed",
    ).length ?? 0;

  const overviewRows: Array<{ label: string; value: string }> = [
    { label: t("trialCode"), value: trial.trial_code },
    { label: t("sponsor"), value: trial.sponsor },
    {
      label: t("phaseHeader"),
      value: trial.phase ? t(`phase.${trial.phase}`) : "-",
    },
    { label: t("studyTypeLabel"), value: t(`studyType.${trial.study_type}`) },
    { label: t("therapeuticArea"), value: trial.therapeutic_area || "-" },
    { label: t("protocolVersion"), value: trial.protocol_version },
    {
      label: t("protocolDate"),
      value: new Date(trial.protocol_date).toLocaleDateString(),
    },
    {
      label: t("enrollment"),
      value: `${enrolledCount}${
        trial.target_enrollment ? ` / ${trial.target_enrollment}` : ""
      }`,
    },
    {
      label: t("dates"),
      value: `${trial.start_date ? new Date(trial.start_date).toLocaleDateString() : "-"} -> ${
        trial.end_date ? new Date(trial.end_date).toLocaleDateString() : "-"
      }`,
    },
    { label: t("irbNumber"), value: trial.irb_approval_number || "-" },
    { label: t("ethicsCommittee"), value: trial.ethics_committee || "-" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <Link
            href="/trials"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t("backToTrials")}
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/10">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                {trial.short_title || trial.title}
              </h1>
              <p className="text-sm text-muted-foreground">{trial.trial_code}</p>
            </div>
          </div>
        </div>
        <StatusBadge variant={statusVariant(trial.status)}>
          {t(`trialStatus.${trial.status}`)}
        </StatusBadge>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border">
        {tabs.map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === key
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`detailTab.${key}`)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h2 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">
              {t("protocolTitle")}
            </h2>
            <p className="text-sm text-foreground">{trial.title}</p>
          </div>

          <dl className="grid grid-cols-1 gap-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] sm:grid-cols-2 lg:grid-cols-3">
            {overviewRows.map((row) => (
              <div key={row.label}>
                <dt className="text-xs uppercase text-muted-foreground">
                  {row.label}
                </dt>
                <dd className="mt-0.5 text-sm font-medium text-foreground">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
              <h2 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">
                {t("inclusionCriteria")}
              </h2>
              <CriteriaList criteria={trial.inclusion_criteria} />
            </div>
            <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
              <h2 className="mb-2 text-sm font-semibold uppercase text-muted-foreground">
                {t("exclusionCriteria")}
              </h2>
              <CriteriaList criteria={trial.exclusion_criteria} />
            </div>
          </div>
        </div>
      )}

      {tab === "participants" && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Users className="h-5 w-5 text-indigo-500" />
            <h2 className="text-lg font-semibold text-foreground">
              {t("participantsTitle")}
            </h2>
          </div>

          {participantsLoading ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {t("loading")}
            </p>
          ) : !participants?.items.length ? (
            <EmptyState
              icon={Users}
              title={t("noParticipantsTitle")}
              description={t("noParticipants")}
            />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("participantNumber")}</th>
                    <th className="px-4 py-3">{t("patientName")}</th>
                    <th className="px-4 py-3">{t("arm")}</th>
                    <th className="px-4 py-3">{t("statusLabel")}</th>
                    <th className="px-4 py-3">{t("screeningDate")}</th>
                    <th className="px-4 py-3">{t("enrollmentDate")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {participants.items.map((participant) => (
                    <tr
                      key={participant.id}
                      className="bg-card hover:bg-muted/50"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">
                        {participant.participant_number}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {participant.patient_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {participant.randomization_arm || "-"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge variant="neutral">
                          {t(`participantStatus.${participant.status}`)}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {participant.screening_date
                          ? new Date(
                              participant.screening_date,
                            ).toLocaleDateString()
                          : "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {participant.enrollment_date
                          ? new Date(
                              participant.enrollment_date,
                            ).toLocaleDateString()
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            {tc("totalItems")}: {participants?.items.length ?? 0}
          </p>
        </div>
      )}

      {tab === "adverse_events" && <AdverseEventsPanel trialId={trialId} />}
      {tab === "ai_screening" && <AIScreeningPanel trialId={trialId} />}
    </div>
  );
}

/**
 * Render a trial's criteria mapping as a readable list.
 *
 * @param criteria - Inclusion or exclusion criteria mapping
 * @returns Criteria list
 */
function CriteriaList({ criteria }: { criteria: Record<string, unknown> }) {
  const entries: string[] = [];
  const ageMin = criteria["age_min"];
  const ageMax = criteria["age_max"];
  if (typeof ageMin === "number" || typeof ageMin === "string") {
    entries.push(`age_min: ${String(ageMin)}`);
  }
  if (typeof ageMax === "number" || typeof ageMax === "string") {
    entries.push(`age_max: ${String(ageMax)}`);
  }
  const conditions = criteria["conditions"];
  if (Array.isArray(conditions)) {
    entries.push(`conditions: ${conditions.map(String).join(", ")}`);
  }
  const list = criteria["criteria"];
  const lines = Array.isArray(list) ? list.map(String) : [];

  if (!entries.length && !lines.length) {
    return <p className="text-sm text-muted-foreground">-</p>;
  }

  return (
    <div className="space-y-2">
      {entries.length > 0 && (
        <ul className="space-y-1 text-sm text-foreground">
          {entries.map((entry) => (
            <li key={entry}>{entry}</li>
          ))}
        </ul>
      )}
      {lines.length > 0 && (
        <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}