"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X } from "lucide-react";
import { useCreateTrial } from "@/hooks/useClinicalTrials";
import { cn } from "@/lib/utils";
import type { TrialPhase, TrialStudyType } from "@aifya/shared";

const PHASES: TrialPhase[] = [
  "I",
  "II",
  "III",
  "IV",
  "observational",
  "registry",
];

const STUDY_TYPES: TrialStudyType[] = [
  "interventional",
  "observational",
  "registry",
  "diagnostic",
  "pragmatic",
  "adaptive",
];

const trialSchema = z.object({
  title: z.string().trim().min(1),
  short_title: z.string().optional(),
  phase: z.string().optional(),
  study_type: z.string().min(1),
  therapeutic_area: z.string().optional(),
  sponsor: z.string().trim().min(1),
  protocol_version: z.string().trim().min(1),
  protocol_date: z.string().min(1),
  target_enrollment: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  irb_approval_number: z.string().optional(),
  ethics_committee: z.string().optional(),
  age_min: z.string().optional(),
  age_max: z.string().optional(),
  conditions: z.string().optional(),
  inclusion_criteria: z.string().optional(),
  exclusion_criteria: z.string().optional(),
});

type TrialFormValues = z.infer<typeof trialSchema>;

const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border";
const labelClass = "mb-1 block text-sm font-medium text-foreground";

/** Split a textarea into trimmed, non-empty lines. */
function toLines(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

/** Split a comma separated list into trimmed, non-empty values. */
function toList(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

/**
 * Create-trial dialog for the clinical trial registry.
 *
 * @param onClose - Called when the dialog should close
 * @returns New trial dialog
 */
export function NewTrialDialog({ onClose }: { onClose: () => void }) {
  const t = useTranslations("trials");
  const tc = useTranslations("common");
  const createTrial = useCreateTrial();

  const form = useForm<TrialFormValues>({
    resolver: zodResolver(trialSchema),
    defaultValues: {
      title: "",
      short_title: "",
      phase: "",
      study_type: "interventional",
      therapeutic_area: "",
      sponsor: "",
      protocol_version: "1.0",
      protocol_date: "",
      target_enrollment: "",
      start_date: "",
      end_date: "",
      irb_approval_number: "",
      ethics_committee: "",
      age_min: "",
      age_max: "",
      conditions: "",
      inclusion_criteria: "",
      exclusion_criteria: "",
    },
  });

  const onSubmit = (values: TrialFormValues) => {
    const inclusion: Record<string, unknown> = {
      criteria: toLines(values.inclusion_criteria),
    };
    if (values.age_min) inclusion["age_min"] = Number(values.age_min);
    if (values.age_max) inclusion["age_max"] = Number(values.age_max);
    const conditions = toList(values.conditions);
    if (conditions.length) inclusion["conditions"] = conditions;

    createTrial.mutate(
      {
        title: values.title,
        short_title: values.short_title || null,
        phase: (values.phase || null) as TrialPhase | null,
        study_type: values.study_type as TrialStudyType,
        therapeutic_area: values.therapeutic_area || null,
        sponsor: values.sponsor,
        protocol_version: values.protocol_version,
        protocol_date: values.protocol_date,
        target_enrollment: values.target_enrollment
          ? Number(values.target_enrollment)
          : null,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
        irb_approval_number: values.irb_approval_number || null,
        ethics_committee: values.ethics_committee || null,
        inclusion_criteria: inclusion,
        exclusion_criteria: { criteria: toLines(values.exclusion_criteria) },
      },
      { onSuccess: () => onClose() },
    );
  };

  const errors = form.formState.errors;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-card p-6 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-trial-title"
      >
        <div className="mb-4 flex items-start justify-between">
          <h2 id="new-trial-title" className="text-lg font-bold text-foreground">
            {t("createTrial")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={tc("close")}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {createTrial.isError && (
          <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
            {t("createTrialFailed")}
          </p>
        )}

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
          <div>
            <label htmlFor="trial-title" className={labelClass}>
              {t("fieldTitle")} *
            </label>
            <textarea
              id="trial-title"
              rows={2}
              {...form.register("title")}
              className={cn(inputClass, errors.title && "border-red-500")}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="trial-short-title" className={labelClass}>
                {t("fieldShortTitle")}
              </label>
              <input
                id="trial-short-title"
                {...form.register("short_title")}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="trial-sponsor" className={labelClass}>
                {t("sponsor")} *
              </label>
              <input
                id="trial-sponsor"
                {...form.register("sponsor")}
                className={cn(inputClass, errors.sponsor && "border-red-500")}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="trial-phase" className={labelClass}>
                {t("phaseHeader")}
              </label>
              <select
                id="trial-phase"
                {...form.register("phase")}
                className={inputClass}
              >
                <option value="">{tc("none")}</option>
                {PHASES.map((phase) => (
                  <option key={phase} value={phase}>
                    {t(`phase.${phase}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="trial-study-type" className={labelClass}>
                {t("studyTypeLabel")} *
              </label>
              <select
                id="trial-study-type"
                {...form.register("study_type")}
                className={inputClass}
              >
                {STUDY_TYPES.map((studyType) => (
                  <option key={studyType} value={studyType}>
                    {t(`studyType.${studyType}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="trial-area" className={labelClass}>
                {t("therapeuticArea")}
              </label>
              <input
                id="trial-area"
                {...form.register("therapeutic_area")}
                className={inputClass}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="trial-protocol-version" className={labelClass}>
                {t("protocolVersion")} *
              </label>
              <input
                id="trial-protocol-version"
                {...form.register("protocol_version")}
                className={cn(
                  inputClass,
                  errors.protocol_version && "border-red-500",
                )}
              />
            </div>
            <div>
              <label htmlFor="trial-protocol-date" className={labelClass}>
                {t("protocolDate")} *
              </label>
              <input
                id="trial-protocol-date"
                type="date"
                {...form.register("protocol_date")}
                className={cn(
                  inputClass,
                  errors.protocol_date && "border-red-500",
                )}
              />
            </div>
            <div>
              <label htmlFor="trial-target" className={labelClass}>
                {t("targetEnrollment")}
              </label>
              <input
                id="trial-target"
                type="number"
                min={1}
                {...form.register("target_enrollment")}
                className={inputClass}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="trial-start" className={labelClass}>
                {t("startDate")}
              </label>
              <input
                id="trial-start"
                type="date"
                {...form.register("start_date")}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="trial-end" className={labelClass}>
                {t("endDate")}
              </label>
              <input
                id="trial-end"
                type="date"
                {...form.register("end_date")}
                className={inputClass}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="trial-irb" className={labelClass}>
                {t("irbNumber")}
              </label>
              <input
                id="trial-irb"
                {...form.register("irb_approval_number")}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="trial-ethics" className={labelClass}>
                {t("ethicsCommittee")}
              </label>
              <input
                id="trial-ethics"
                {...form.register("ethics_committee")}
                className={inputClass}
              />
            </div>
          </div>

          <fieldset className="rounded-lg border border-border p-3">
            <legend className="px-1 text-sm font-medium text-foreground">
              {t("inclusionCriteria")}
            </legend>
            <p className="mb-2 text-xs text-muted-foreground">
              {t("criteriaHint")}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="trial-age-min" className={labelClass}>
                  {t("ageMin")}
                </label>
                <input
                  id="trial-age-min"
                  type="number"
                  min={0}
                  {...form.register("age_min")}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="trial-age-max" className={labelClass}>
                  {t("ageMax")}
                </label>
                <input
                  id="trial-age-max"
                  type="number"
                  min={0}
                  {...form.register("age_max")}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="mt-3">
              <label htmlFor="trial-conditions" className={labelClass}>
                {t("conditionsLabel")}
              </label>
              <input
                id="trial-conditions"
                {...form.register("conditions")}
                placeholder={t("conditionsPlaceholder")}
                className={inputClass}
              />
            </div>
            <div className="mt-3">
              <label htmlFor="trial-inclusion" className={labelClass}>
                {t("criteriaLabel")}
              </label>
              <textarea
                id="trial-inclusion"
                rows={3}
                {...form.register("inclusion_criteria")}
                className={inputClass}
              />
            </div>
          </fieldset>

          <fieldset className="rounded-lg border border-border p-3">
            <legend className="px-1 text-sm font-medium text-foreground">
              {t("exclusionCriteria")}
            </legend>
            <textarea
              rows={3}
              {...form.register("exclusion_criteria")}
              className={cn(inputClass, "mt-2")}
              aria-label={t("exclusionCriteria")}
            />
          </fieldset>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={createTrial.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
            >
              {createTrial.isPending && (
                <span
                  aria-hidden
                  className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                />
              )}
              {t("createTrial")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}