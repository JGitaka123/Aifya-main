"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Brain, Search, Sparkles, X } from "lucide-react";
import {
  useAIScreenings,
  useReviewAIScreening,
  useRunAIScreening,
} from "@/hooks/useClinicalTrials";
import { usePatientSearch } from "@/hooks/usePatients";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn } from "@/lib/utils";
import type { AIScreeningResponse, ScreeningDecision } from "@aifya/shared";

const DECISIONS: ScreeningDecision[] = [
  "proceed_to_screen",
  "not_eligible",
  "defer",
  "already_screened",
];

const DECISION_VARIANT: Record<
  ScreeningDecision,
  "success" | "neutral" | "warning" | "info"
> = {
  proceed_to_screen: "success",
  not_eligible: "neutral",
  defer: "warning",
  already_screened: "info",
};

const reviewSchema = z.object({
  decision: z.enum([
    "proceed_to_screen",
    "not_eligible",
    "defer",
    "already_screened",
  ]),
  review_notes: z.string().optional(),
});

type ReviewFormValues = z.infer<typeof reviewSchema>;

const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border";
const labelClass = "mb-1 block text-sm font-medium text-foreground";

/** Colour a score bar by how strong the match is. */
function scoreTone(score: number): string {
  if (score >= 0.75) return "bg-emerald-500";
  if (score >= 0.5) return "bg-amber-500";
  return "bg-red-500";
}

/**
 * AI eligibility screening worklist for one trial.
 *
 * Screenings are decision support only: every row needs an investigator
 * decision before any clinical action is taken.
 *
 * @param trialId - Trial whose screenings are shown
 * @returns AI screening panel
 */
export function AIScreeningPanel({ trialId }: { trialId: string }) {
  const t = useTranslations("trials");
  const tc = useTranslations("common");
  const [unreviewedOnly, setUnreviewedOnly] = useState(false);
  const [showRun, setShowRun] = useState(false);
  const [patientQuery, setPatientQuery] = useState("");
  const [patientId, setPatientId] = useState("");
  const [reviewTarget, setReviewTarget] = useState<AIScreeningResponse | null>(
    null,
  );

  const { data, isLoading } = useAIScreenings(trialId, unreviewedOnly);
  const { data: patients, isFetching: patientsFetching } =
    usePatientSearch(patientQuery);
  const runScreening = useRunAIScreening(trialId);
  const reviewScreening = useReviewAIScreening(
    trialId,
    reviewTarget?.id ?? "",
  );

  const reviewForm = useForm<ReviewFormValues>({
    resolver: zodResolver(reviewSchema),
    defaultValues: { decision: "proceed_to_screen", review_notes: "" },
  });

  const onSubmitRun = () => {
    if (!patientId) return;
    runScreening.mutate(
      { patient_id: patientId },
      {
        onSuccess: () => {
          setShowRun(false);
          setPatientId("");
          setPatientQuery("");
        },
      },
    );
  };

  const onSubmitReview = (values: ReviewFormValues) => {
    reviewScreening.mutate(
      {
        decision: values.decision,
        review_notes: values.review_notes || null,
      },
      {
        onSuccess: () => {
          setReviewTarget(null);
          reviewForm.reset();
        },
      },
    );
  };

  const rows = data?.items ?? [];
  const searchResults = patients?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Brain className="h-5 w-5 text-cyan-500" />
          <h2 className="text-lg font-semibold text-foreground">
            {t("tab.ai_screening")}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={unreviewedOnly}
              onChange={(event) => setUnreviewedOnly(event.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            {t("unreviewedOnly")}
          </label>
          <button
            type="button"
            onClick={() => setShowRun(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Sparkles className="h-4 w-4" />
            {t("runScreening")}
          </button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        {t("aiScreeningDescription")}
      </p>
      <p className="text-xs text-amber-600 dark:text-amber-400">
        {t("aiDisclaimer")}
      </p>

      {isLoading ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {t("loading")}
        </p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Brain}
          title={t("noScreenings")}
          description={t("noScreeningsHint")}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("candidate")}</th>
                <th className="px-4 py-3">{t("eligibilityScore")}</th>
                <th className="px-4 py-3">{t("criteriaMet")}</th>
                <th className="px-4 py-3">{t("criteriaNotMet")}</th>
                <th className="px-4 py-3">{t("criteriaUnknown")}</th>
                <th className="px-4 py-3">{t("reviewStatus")}</th>
                <th className="px-4 py-3">{tc("actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((screening) => {
                const score = Math.round(screening.eligibility_score * 100);
                const met = Object.keys(screening.criteria_met ?? {}).length;
                const notMet = Object.keys(
                  screening.criteria_not_met ?? {},
                ).length;
                const unknown = Object.keys(
                  screening.criteria_unknown ?? {},
                ).length;
                return (
                  <tr key={screening.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {screening.patient_name ?? screening.patient_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                          <div
                            className={cn("h-full rounded-full", scoreTone(screening.eligibility_score))}
                            style={{ width: `${score}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-foreground">
                          {score}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{met}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {notMet}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {unknown}
                    </td>
                    <td className="px-4 py-3">
                      {screening.investigator_reviewed &&
                      screening.investigator_decision ? (
                        <StatusBadge
                          variant={
                            DECISION_VARIANT[
                              screening.investigator_decision as ScreeningDecision
                            ] ?? "neutral"
                          }
                        >
                          {t(
                            `screeningDecision.${screening.investigator_decision}`,
                          )}
                        </StatusBadge>
                      ) : (
                        <StatusBadge variant="warning">
                          {t("pendingReview")}
                        </StatusBadge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => {
                          setReviewTarget(screening);
                          reviewForm.reset({
                            decision: "proceed_to_screen",
                            review_notes: screening.review_notes ?? "",
                          });
                        }}
                        className="rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                      >
                        {screening.investigator_reviewed
                          ? t("updateReview")
                          : t("reviewNow")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showRun && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setShowRun(false)}
          role="presentation"
        >
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-card p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="run-screening-title"
          >
            <div className="mb-4 flex items-start justify-between">
              <h2
                id="run-screening-title"
                className="text-lg font-bold text-foreground"
              >
                {t("runScreening")}
              </h2>
              <button
                type="button"
                onClick={() => setShowRun(false)}
                aria-label={tc("close")}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-3 text-sm text-muted-foreground">
              {t("runScreeningHint")}
            </p>

            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
                placeholder={t("patientSearchPlaceholder")}
                className={cn(inputClass, "pl-10")}
              />
            </div>

            <div className="mt-3 max-h-56 overflow-y-auto rounded-lg border border-border">
              {patientsFetching ? (
                <p className="p-3 text-sm text-muted-foreground">
                  {t("loading")}
                </p>
              ) : searchResults.length === 0 ? (
                <p className="p-3 text-sm text-muted-foreground">
                  {t("noPatientsFound")}
                </p>
              ) : (
                searchResults.map((patient) => (
                  <button
                    key={patient.id}
                    type="button"
                    onClick={() => setPatientId(patient.id)}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-muted",
                      patientId === patient.id && "bg-primary/10",
                    )}
                  >
                    <span className="font-medium text-foreground">
                      {patient.first_name} {patient.last_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {patient.mrn}
                    </span>
                  </button>
                ))
              )}
            </div>

            {runScreening.isError && (
              <p className="mt-3 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                {t("runScreeningFailed")}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-4">
              <button
                type="button"
                onClick={() => setShowRun(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                {tc("cancel")}
              </button>
              <button
                type="button"
                onClick={onSubmitRun}
                disabled={!patientId || runScreening.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
              >
                {runScreening.isPending && (
                  <span
                    aria-hidden
                    className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                  />
                )}
                {t("runScreening")}
              </button>
            </div>
          </div>
        </div>
      )}

      {reviewTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setReviewTarget(null)}
          role="presentation"
        >
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-card p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="review-screening-title"
          >
            <div className="mb-1 flex items-start justify-between">
              <h2
                id="review-screening-title"
                className="text-lg font-bold text-foreground"
              >
                {t("reviewScreening")}
              </h2>
              <button
                type="button"
                onClick={() => setReviewTarget(null)}
                aria-label={tc("close")}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              {reviewTarget.patient_name ?? reviewTarget.patient_id.slice(0, 8)}
            </p>

            {reviewTarget.ai_reasoning && (
              <div className="mb-4 rounded-lg bg-muted/50 p-3">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  {t("aiReasoning")}
                </p>
                <p className="text-sm text-foreground">
                  {reviewTarget.ai_reasoning}
                </p>
              </div>
            )}

            <details className="mb-4 rounded-lg border border-border p-3">
              <summary className="cursor-pointer text-sm font-medium text-foreground">
                {t("criteriaBreakdown")}
              </summary>
              <dl className="mt-2 space-y-1 text-xs">
                <dt className="font-medium text-emerald-600 dark:text-emerald-400">
                  {t("criteriaMet")}
                </dt>
                {Object.entries(reviewTarget.criteria_met ?? {}).map(
                  ([key, value]) => (
                    <dd key={key} className="text-muted-foreground">
                      {key} - {String(value)}
                    </dd>
                  ),
                )}
                <dt className="pt-1 font-medium text-red-600 dark:text-red-400">
                  {t("criteriaNotMet")}
                </dt>
                {Object.entries(reviewTarget.criteria_not_met ?? {}).map(
                  ([key, value]) => (
                    <dd key={key} className="text-muted-foreground">
                      {key} - {String(value)}
                    </dd>
                  ),
                )}
                <dt className="pt-1 font-medium text-amber-600 dark:text-amber-400">
                  {t("criteriaUnknown")}
                </dt>
                {Object.entries(reviewTarget.criteria_unknown ?? {}).map(
                  ([key, value]) => (
                    <dd key={key} className="text-muted-foreground">
                      {key} - {String(value)}
                    </dd>
                  ),
                )}
              </dl>
            </details>

            {reviewScreening.isError && (
              <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                {t("reviewFailed")}
              </p>
            )}

            <form
              onSubmit={reviewForm.handleSubmit(onSubmitReview)}
              className="space-y-3"
            >
              <div>
                <label htmlFor="review-decision" className={labelClass}>
                  {t("decision")} *
                </label>
                <select
                  id="review-decision"
                  {...reviewForm.register("decision")}
                  className={inputClass}
                >
                  {DECISIONS.map((decision) => (
                    <option key={decision} value={decision}>
                      {t(`screeningDecision.${decision}`)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="review-notes" className={labelClass}>
                  {tc("notes")}
                </label>
                <textarea
                  id="review-notes"
                  rows={3}
                  {...reviewForm.register("review_notes")}
                  className={inputClass}
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setReviewTarget(null)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={reviewScreening.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
                >
                  {reviewScreening.isPending && (
                    <span
                      aria-hidden
                      className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                    />
                  )}
                  {tc("save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}