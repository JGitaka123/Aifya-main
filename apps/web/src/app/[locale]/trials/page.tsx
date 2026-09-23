"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle,
  ClipboardList,
  Clock,
  FlaskConical,
  Plus,
  Search,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useTrialsSummary, useTrials } from "@/hooks/useClinicalTrials";
import { AdverseEventsPanel } from "@/components/trials/AdverseEventsPanel";
import { AIScreeningPanel } from "@/components/trials/AIScreeningPanel";
import { NewTrialDialog } from "@/components/trials/NewTrialDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn } from "@/lib/utils";
import type { TrialStatus } from "@aifya/shared";

/** Badge colour per trial status. */
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

const STATUS_FILTERS = [
  "setup",
  "recruiting",
  "active",
  "follow_up",
  "completed",
  "suspended",
  "terminated",
];

/** Resolve a badge colour for a possibly-unknown status string. */
function statusVariant(
  status: string,
): "neutral" | "blue" | "success" | "purple" | "teal" | "warning" | "error" {
  return STATUS_VARIANT[status as TrialStatus] ?? "neutral";
}

type TabKey = "registry" | "adverse_events" | "ai_screening";

/**
 * Clinical Trials registry page.
 * ICH-GCP compliant trial management with AI screening and SAE tracking.
 *
 * @returns Clinical Trials page component
 */
export default function ClinicalTrialsPage() {
  const t = useTranslations("trials");
  const tc = useTranslations("common");
  const [tab, setTab] = useState<TabKey>("registry");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTrialId, setSelectedTrialId] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useTrialsSummary();
  const { data: trials, isLoading: trialsLoading } = useTrials(
    statusFilter || undefined,
  );

  // Default the trial-scoped tabs to the first trial in the register, so the
  // adverse event and screening panels are useful without an extra click.
  useEffect(() => {
    const firstTrialId = trials?.items[0]?.id;
    if (!selectedTrialId && firstTrialId) {
      setSelectedTrialId(firstTrialId);
    }
  }, [selectedTrialId, trials]);

  const summaryCards = [
    { label: t("totalTrials"), value: summary?.total_trials ?? 0, icon: FlaskConical, color: "text-blue-600 dark:text-blue-400" },
    { label: t("recruiting"), value: summary?.recruiting_trials ?? 0, icon: UserPlus, color: "text-emerald-600 dark:text-emerald-400" },
    { label: t("activeTrials"), value: summary?.active_trials ?? 0, icon: Activity, color: "text-green-600 dark:text-green-400" },
    { label: t("completedTrials"), value: summary?.completed_trials ?? 0, icon: CheckCircle, color: "text-teal-600 dark:text-teal-400" },
    { label: t("totalParticipants"), value: summary?.total_participants ?? 0, icon: Users, color: "text-purple-600 dark:text-purple-400" },
    { label: t("enrolled"), value: summary?.enrolled_participants ?? 0, icon: ClipboardList, color: "text-indigo-600 dark:text-indigo-400" },
    { label: t("adverseEvents"), value: summary?.total_adverse_events ?? 0, icon: AlertTriangle, color: "text-amber-600 dark:text-amber-400" },
    { label: t("saeCount"), value: summary?.serious_adverse_events ?? 0, icon: XCircle, color: "text-red-600 dark:text-red-400" },
    { label: t("pendingScreenings"), value: summary?.pending_ai_screenings ?? 0, icon: Brain, color: "text-cyan-600 dark:text-cyan-400" },
    { label: t("screenFailures"), value: summary?.screen_failures ?? 0, icon: Clock, color: "text-orange-600 dark:text-orange-400" },
  ];

  const filteredTrials = trials?.items.filter((trial) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      trial.title.toLowerCase().includes(q) ||
      trial.trial_code.toLowerCase().includes(q) ||
      trial.sponsor.toLowerCase().includes(q) ||
      (trial.therapeutic_area?.toLowerCase().includes(q) ?? false)
    );
  });

  const selectClass =
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground";

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          {t("newTrial")}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5 lg:grid-cols-10">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-1 text-lg font-bold text-foreground">
              {summaryLoading ? "-" : card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {(["registry", "adverse_events", "ai_screening"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t_
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`tab.${t_}`)}
          </button>
        ))}
      </div>

      {/* Registry Tab */}
      {tab === "registry" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder={t("searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-border bg-card py-2 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
            >
              <option value="">{t("allStatuses")}</option>
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {t(`trialStatus.${s}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Trial Table */}
          {!trialsLoading && !filteredTrials?.length ? (
            <EmptyState
              icon={FlaskConical}
              title={t("noTrials")}
              description={t("noTrialsHint")}
              action={
                <button
                  type="button"
                  onClick={() => setShowCreate(true)}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <Plus className="h-4 w-4" />
                  {t("newTrial")}
                </button>
              }
            />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("trialCode")}</th>
                    <th className="px-4 py-3">{t("trialTitle")}</th>
                    <th className="px-4 py-3">{t("phaseHeader")}</th>
                    <th className="px-4 py-3">{t("sponsor")}</th>
                    <th className="px-4 py-3">{t("therapeuticArea")}</th>
                    <th className="px-4 py-3">{t("enrollment")}</th>
                    <th className="px-4 py-3">{t("statusLabel")}</th>
                    <th className="px-4 py-3">{t("dates")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {trialsLoading ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                        {t("loading")}
                      </td>
                    </tr>
                  ) : (
                    filteredTrials?.map((trial) => (
                      <tr key={trial.id} className="bg-card hover:bg-muted/50">
                        <td className="px-4 py-3">
                          <Link
                            href={`/trials/${trial.id}`}
                            className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {trial.trial_code}
                          </Link>
                        </td>
                        <td className="max-w-xs truncate px-4 py-3 font-medium text-foreground">
                          {trial.short_title || trial.title}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {trial.phase ? t(`phase.${trial.phase}`) : "-"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{trial.sponsor}</td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {trial.therapeutic_area || "-"}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-foreground">{trial.enrolled_count}</span>
                          {trial.target_enrollment && (
                            <span className="text-muted-foreground">
                              /{trial.target_enrollment}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            variant={statusVariant(trial.status)}
                          >
                            {t(`trialStatus.${trial.status}`)}
                          </StatusBadge>
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {trial.start_date
                            ? new Date(trial.start_date).toLocaleDateString()
                            : "-"}
                          {trial.end_date && (
                            <>
                              {" -> "}
                              {new Date(trial.end_date).toLocaleDateString()}
                            </>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Trial-scoped tabs share one picker */}
      {(tab === "adverse_events" || tab === "ai_screening") && (
        <>
          <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <label htmlFor="trial-picker" className="mb-1 block text-sm font-medium text-foreground">
              {t("selectTrial")}
            </label>
            <select
              id="trial-picker"
              value={selectedTrialId}
              onChange={(e) => setSelectedTrialId(e.target.value)}
              className={selectClass}
            >
              <option value="">{tc("select")}</option>
              {trials?.items.map((trial) => (
                <option key={trial.id} value={trial.id}>
                  {trial.trial_code} - {trial.short_title || trial.title}
                </option>
              ))}
            </select>
          </div>

          {!selectedTrialId ? (
            <EmptyState
              icon={tab === "adverse_events" ? AlertTriangle : Brain}
              title={t("selectTrial")}
              description={t(
                tab === "adverse_events" ? "aeSelectTrial" : "aiSelectTrial",
              )}
            />
          ) : tab === "adverse_events" ? (
            <AdverseEventsPanel trialId={selectedTrialId} />
          ) : (
            <AIScreeningPanel trialId={selectedTrialId} />
          )}
        </>
      )}

      {showCreate && <NewTrialDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}