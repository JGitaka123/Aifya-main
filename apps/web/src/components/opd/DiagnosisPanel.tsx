"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ClipboardList,
  Plus,
  ChevronDown,
  ChevronUp,
  Tag,
} from "lucide-react";
import { useEncounterDiagnoses, useAddDiagnosis } from "@/hooks/useEncounters";
import { ICD10Autocomplete } from "@/components/opd/ICD10Autocomplete";
import { cn } from "@/lib/utils";

const createDiagnosisSchema = (codeRequired: string, descriptionRequired: string) => z.object({
  icd10_code: z.string().min(3, codeRequired),
  icd10_description: z.string().min(1, descriptionRequired),
  diagnosis_type: z.enum(["primary", "secondary", "differential", "ruled_out"]),
  certainty: z.enum(["confirmed", "provisional", "differential", "refuted"]),
  notes: z.string().nullable().optional(),
  is_chronic: z.boolean().optional(),
});

type DiagnosisFormData = z.infer<ReturnType<typeof createDiagnosisSchema>>;

interface DiagnosisPanelProps {
  encounterId: string;
  patientId: string;
}

/**
 * Diagnosis entry panel with ICD-10 autocomplete.
 *
 * @param props - encounterId and patientId
 * @returns Diagnosis panel component
 */
export function DiagnosisPanel({ encounterId, patientId }: DiagnosisPanelProps) {
  const t = useTranslations("diagnosis");
  const tc = useTranslations("common");
  const diagnosisSchema = createDiagnosisSchema(t("icd10CodeRequired"), t("descriptionRequired"));
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const { data: diagnoses, isLoading } = useEncounterDiagnoses(encounterId);
  const addDiagnosis = useAddDiagnosis(encounterId);

  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm<DiagnosisFormData>({
    resolver: zodResolver(diagnosisSchema),
    defaultValues: {
      diagnosis_type: "primary",
      certainty: "confirmed",
      is_chronic: false,
    },
  });

  const onSubmit = (data: DiagnosisFormData) => {
    addDiagnosis.mutate(
      {
        encounter_id: encounterId,
        patient_id: patientId,
        ...data,
      },
      {
        onSuccess: () => {
          setShowForm(false);
          reset();
        },
      }
    );
  };

  const typeColors: Record<string, string> = {
    primary: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
    secondary: "bg-muted text-foreground",
    differential: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200",
    ruled_out: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  };

  return (
    <div className="rounded-lg border border-border bg-card dark:bg-card">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold text-foreground">{t("title")}</h3>
          {diagnoses && diagnoses.length > 0 && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {diagnoses.length}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          {/* Existing diagnoses */}
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{tc("loading")}</p>
          ) : diagnoses && diagnoses.length > 0 ? (
            <div className="mb-3 space-y-2">
              {diagnoses.map((dx) => (
                <div
                  key={dx.id}
                  className="flex items-start gap-3 rounded-lg border border-border p-3"
                >
                  <Tag className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium text-primary">
                        {dx.icd10_code}
                      </span>
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", typeColors[dx.diagnosis_type])}>
                        {t(dx.diagnosis_type as Parameters<typeof t>[0])}
                      </span>
                      {dx.is_chronic && (
                        <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-800 dark:bg-purple-950 dark:text-purple-200">
                          {t("chronic")}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-sm text-foreground">{dx.icd10_description}</p>
                    {dx.notes && (
                      <p className="mt-1 text-xs text-muted-foreground">{dx.notes}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mb-3 text-sm text-muted-foreground">{t("noDiagnoses")}</p>
          )}

          {/* Add diagnosis */}
          {!showForm ? (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              {t("add")}
            </button>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              {/* ICD-10 autocomplete */}
              <ICD10Autocomplete
                onSelect={(code, description) => {
                  setValue("icd10_code", code);
                  setValue("icd10_description", description);
                }}
              />
              {errors.icd10_code && (
                <p className="text-xs text-red-500">{errors.icd10_code.message}</p>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("diagnosisType")}
                  </label>
                  <select
                    {...register("diagnosis_type")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    <option value="primary">{t("primary")}</option>
                    <option value="secondary">{t("secondary")}</option>
                    <option value="differential">{t("differential")}</option>
                    <option value="ruled_out">{t("ruledOut")}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("certainty")}
                  </label>
                  <select
                    {...register("certainty")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    <option value="confirmed">{t("confirmed")}</option>
                    <option value="provisional">{t("provisional")}</option>
                    <option value="differential">{t("differentialCertainty")}</option>
                    <option value="refuted">{t("refuted")}</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  {t("notes")}
                </label>
                <textarea
                  {...register("notes")}
                  rows={2}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="checkbox" {...register("is_chronic")} className="rounded border-input" />
                {t("chronic")}
              </label>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={addDiagnosis.isPending}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {addDiagnosis.isPending ? t("adding") : t("add")}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); reset(); }}
                  className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
