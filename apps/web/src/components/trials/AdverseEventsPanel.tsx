"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, Plus, ShieldAlert, X } from "lucide-react";
import {
  useAdverseEvents,
  useReportAdverseEvent,
  useSubmitSAEReport,
  useTrialParticipants,
} from "@/hooks/useClinicalTrials";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type {
  AdverseEventListItem,
  AERelatedness,
  AESeverity,
} from "@aifya/shared";

/** Badge colour per AE severity. */
const SEVERITY_VARIANT: Record<AESeverity, "success" | "warning" | "error"> = {
  mild: "success",
  moderate: "warning",
  severe: "error",
};

const SEVERITIES: AESeverity[] = ["mild", "moderate", "severe"];
const RELATEDNESS: AERelatedness[] = [
  "unrelated",
  "unlikely",
  "possible",
  "probable",
  "definite",
];

const aeFormSchema = z.object({
  participant_id: z.string().min(1),
  ae_term: z.string().trim().min(1).max(5000),
  severity: z.enum(["mild", "moderate", "severe"]),
  ctcae_grade: z.string().optional(),
  relatedness: z.string().optional(),
  onset_date: z.string().min(1),
  resolution_date: z.string().optional(),
  outcome: z.string().optional(),
  action_taken: z.string().optional(),
  is_serious: z.boolean(),
});

type AeFormValues = z.infer<typeof aeFormSchema>;

const saeFormSchema = z.object({
  sae_aware_date: z.string().min(1),
  sae_report_document_url: z.string().optional(),
  reported_to_sponsor: z.boolean(),
  reported_to_irb: z.boolean(),
});

type SaeFormValues = z.infer<typeof saeFormSchema>;

const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border";
const labelClass = "mb-1 block text-sm font-medium text-foreground";

/**
 * Adverse event register for one trial, with ICH-GCP SAE reporting.
 *
 * @param trialId - Trial whose adverse events are shown
 * @returns Adverse events panel
 */
export function AdverseEventsPanel({ trialId }: { trialId: string }) {
  const t = useTranslations("trials");
  const tc = useTranslations("common");
  const [seriousOnly, setSeriousOnly] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [saeTarget, setSaeTarget] = useState<AdverseEventListItem | null>(null);

  const { data, isLoading } = useAdverseEvents(trialId, seriousOnly);
  const { data: participants } = useTrialParticipants(trialId);
  const reportAe = useReportAdverseEvent(trialId);
  const submitSae = useSubmitSAEReport(trialId, saeTarget?.id ?? "");

  const aeForm = useForm<AeFormValues>({
    resolver: zodResolver(aeFormSchema),
    defaultValues: {
      participant_id: "",
      ae_term: "",
      severity: "mild",
      ctcae_grade: "",
      relatedness: "",
      onset_date: "",
      resolution_date: "",
      outcome: "",
      action_taken: "",
      is_serious: false,
    },
  });

  const saeForm = useForm<SaeFormValues>({
    resolver: zodResolver(saeFormSchema),
    defaultValues: {
      sae_aware_date: "",
      sae_report_document_url: "",
      reported_to_sponsor: false,
      reported_to_irb: false,
    },
  });

  const onSubmitAe = (values: AeFormValues) => {
    reportAe.mutate(
      {
        participant_id: values.participant_id,
        ae_term: values.ae_term,
        severity: values.severity,
        ctcae_grade: values.ctcae_grade ? Number(values.ctcae_grade) : null,
        relatedness: values.relatedness
          ? (values.relatedness as AERelatedness)
          : null,
        onset_date: values.onset_date,
        resolution_date: values.resolution_date || null,
        outcome: values.outcome || null,
        action_taken: values.action_taken || null,
        is_serious: values.is_serious,
      },
      {
        onSuccess: () => {
          setShowReport(false);
          aeForm.reset();
        },
      },
    );
  };

  const onSubmitSae = (values: SaeFormValues) => {
    submitSae.mutate(
      {
        sae_aware_date: new Date(values.sae_aware_date).toISOString(),
        sae_report_document_url: values.sae_report_document_url || null,
        reported_to_sponsor: values.reported_to_sponsor,
        reported_to_irb: values.reported_to_irb,
      },
      {
        onSuccess: () => {
          setSaeTarget(null);
          saeForm.reset();
        },
      },
    );
  };

  const rows = data?.items ?? [];
  const hasParticipants = (participants?.items.length ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <h2 className="text-lg font-semibold text-foreground">
            {t("tab.adverse_events")}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={seriousOnly}
              onChange={(event) => setSeriousOnly(event.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            {t("seriousOnly")}
          </label>
          <button
            type="button"
            onClick={() => setShowReport(true)}
            disabled={!hasParticipants}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {t("reportAe")}
          </button>
        </div>
      </div>

      <p className="text-xs text-red-600 dark:text-red-400">{t("saeWarning")}</p>

      {!hasParticipants && (
        <p className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
          {t("noParticipants")}
        </p>
      )}

      {isLoading ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          {t("loading")}
        </p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title={t("noAdverseEvents")}
          description={t("noAdverseEventsHint")}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("participant")}</th>
                <th className="px-4 py-3">{t("aeTerm")}</th>
                <th className="px-4 py-3">{t("severityLabel")}</th>
                <th className="px-4 py-3">{t("ctcaeGrade")}</th>
                <th className="px-4 py-3">{t("relatednessLabel")}</th>
                <th className="px-4 py-3">{t("onsetDate")}</th>
                <th className="px-4 py-3">{t("outcome")}</th>
                <th className="px-4 py-3">{t("dates")}</th>
                <th className="px-4 py-3">{tc("actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((ae) => (
                <tr key={ae.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-medium text-foreground">
                    {ae.participant_number ?? "-"}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 text-foreground">
                    {ae.ae_term}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge
                        variant={SEVERITY_VARIANT[ae.severity as AESeverity] ?? "neutral"}
                      >
                        {t(`severity.${ae.severity}`)}
                      </StatusBadge>
                      {ae.is_serious && (
                        <StatusBadge variant="red-solid">
                          {t("saeBadge")}
                        </StatusBadge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {ae.ctcae_grade ?? "-"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {ae.relatedness ? t(`relatedness.${ae.relatedness}`) : "-"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {new Date(ae.onset_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {ae.outcome || "-"}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {ae.resolution_date
                      ? new Date(ae.resolution_date).toLocaleDateString()
                      : t("ongoing")}
                  </td>
                  <td className="px-4 py-3">
                    {ae.is_serious ? (
                      <button
                        type="button"
                        onClick={() => setSaeTarget(ae)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                      >
                        <ShieldAlert className="h-3.5 w-3.5" />
                        {t("submitSae")}
                      </button>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {t("notSerious")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showReport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setShowReport(false)}
          role="presentation"
        >
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-card p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-ae-title"
          >
            <div className="mb-4 flex items-start justify-between">
              <h2
                id="report-ae-title"
                className="text-lg font-bold text-foreground"
              >
                {t("reportAe")}
              </h2>
              <button
                type="button"
                onClick={() => setShowReport(false)}
                aria-label={tc("close")}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {reportAe.isError && (
              <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                {t("reportAeFailed")}
              </p>
            )}

            <form
              onSubmit={aeForm.handleSubmit(onSubmitAe)}
              className="space-y-3"
            >
              <div>
                <label htmlFor="ae-participant" className={labelClass}>
                  {t("participant")} *
                </label>
                <select
                  id="ae-participant"
                  {...aeForm.register("participant_id")}
                  className={inputClass}
                >
                  <option value="">{tc("select")}</option>
                  {participants?.items.map((participant) => (
                    <option key={participant.id} value={participant.id}>
                      {participant.participant_number}
                      {participant.patient_name
                        ? ` - ${participant.patient_name}`
                        : ""}
                    </option>
                  ))}
                </select>
                {aeForm.formState.errors.participant_id && (
                  <p className="mt-1 text-xs text-red-500">
                    {tc("required")}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="ae-term" className={labelClass}>
                  {t("aeTerm")} *
                </label>
                <input
                  id="ae-term"
                  {...aeForm.register("ae_term")}
                  placeholder={t("aeTermPlaceholder")}
                  className={inputClass}
                />
                {aeForm.formState.errors.ae_term && (
                  <p className="mt-1 text-xs text-red-500">{tc("required")}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="ae-severity" className={labelClass}>
                    {t("severityLabel")} *
                  </label>
                  <select
                    id="ae-severity"
                    {...aeForm.register("severity")}
                    className={inputClass}
                  >
                    {SEVERITIES.map((severity) => (
                      <option key={severity} value={severity}>
                        {t(`severity.${severity}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="ae-grade" className={labelClass}>
                    {t("ctcaeGrade")}
                  </label>
                  <select
                    id="ae-grade"
                    {...aeForm.register("ctcae_grade")}
                    className={inputClass}
                  >
                    <option value="">{tc("none")}</option>
                    {[1, 2, 3, 4, 5].map((grade) => (
                      <option key={grade} value={String(grade)}>
                        {t("gradeValue", { grade })}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="ae-relatedness" className={labelClass}>
                  {t("relatednessLabel")}
                </label>
                <select
                  id="ae-relatedness"
                  {...aeForm.register("relatedness")}
                  className={inputClass}
                >
                  <option value="">{tc("none")}</option>
                  {RELATEDNESS.map((value) => (
                    <option key={value} value={value}>
                      {t(`relatedness.${value}`)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="ae-onset" className={labelClass}>
                    {t("onsetDate")} *
                  </label>
                  <input
                    id="ae-onset"
                    type="date"
                    {...aeForm.register("onset_date")}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="ae-resolution" className={labelClass}>
                    {t("resolutionDate")}
                  </label>
                  <input
                    id="ae-resolution"
                    type="date"
                    {...aeForm.register("resolution_date")}
                    className={inputClass}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="ae-outcome" className={labelClass}>
                    {t("outcome")}
                  </label>
                  <input
                    id="ae-outcome"
                    {...aeForm.register("outcome")}
                    placeholder={t("outcomePlaceholder")}
                    maxLength={30}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="ae-action" className={labelClass}>
                    {t("actionTaken")}
                  </label>
                  <input
                    id="ae-action"
                    {...aeForm.register("action_taken")}
                    placeholder={t("actionTakenPlaceholder")}
                    maxLength={30}
                    className={inputClass}
                  />
                </div>
              </div>

              <label className="flex items-start gap-2 rounded-lg bg-amber-50 p-2.5 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                <input
                  type="checkbox"
                  {...aeForm.register("is_serious")}
                  className="mt-0.5 h-4 w-4 rounded border-border"
                />
                <span>{t("isSerious")}</span>
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReport(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={reportAe.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
                >
                  {reportAe.isPending && (
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

      {saeTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setSaeTarget(null)}
          role="presentation"
        >
          <div
            className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="sae-report-title"
          >
            <div className="mb-1 flex items-start justify-between">
              <h2
                id="sae-report-title"
                className="text-lg font-bold text-foreground"
              >
                {t("saeReport")}
              </h2>
              <button
                type="button"
                onClick={() => setSaeTarget(null)}
                aria-label={tc("close")}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              {saeTarget.ae_term}
            </p>

            {submitSae.isError && (
              <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                {t("saeReportFailed")}
              </p>
            )}

            <form
              onSubmit={saeForm.handleSubmit(onSubmitSae)}
              className="space-y-3"
            >
              <div>
                <label htmlFor="sae-aware" className={labelClass}>
                  {t("saeAwareDate")} *
                </label>
                <input
                  id="sae-aware"
                  type="datetime-local"
                  {...saeForm.register("sae_aware_date")}
                  className={inputClass}
                />
                {saeForm.formState.errors.sae_aware_date && (
                  <p className="mt-1 text-xs text-red-500">{tc("required")}</p>
                )}
              </div>

              <div>
                <label htmlFor="sae-document" className={labelClass}>
                  {t("saeDocumentUrl")}
                </label>
                <input
                  id="sae-document"
                  {...saeForm.register("sae_report_document_url")}
                  placeholder="https://"
                  className={inputClass}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  {...saeForm.register("reported_to_sponsor")}
                  className="h-4 w-4 rounded border-border"
                />
                {t("reportedToSponsor")}
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  {...saeForm.register("reported_to_irb")}
                  className="h-4 w-4 rounded border-border"
                />
                {t("reportedToIrb")}
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSaeTarget(null)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={submitSae.isPending}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
                >
                  {submitSae.isPending && (
                    <span
                      aria-hidden
                      className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                    />
                  )}
                  {tc("submit")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}