"use client";

import { useState, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Pill,
  Plus,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
} from "lucide-react";
import {
  useEncounterPrescriptions,
  useCreatePrescription,
} from "@/hooks/useEncounters";
import { useEvaluatePrescription } from "@/hooks/useCDS";
import { CDSAlertBanner } from "@/components/opd/CDSAlertBanner";
import { DrugAutocomplete } from "@/components/opd/DrugAutocomplete";
import type { CDSAlert } from "@aifya/shared";

const createPrescriptionSchema = (drugNameRequired: string, dosageRequired: string) => z.object({
  drug_name: z.string().min(1, drugNameRequired),
  generic_name: z.string().nullable().optional(),
  is_keml: z.boolean().optional(),
  dosage: z.string().min(1, dosageRequired),
  route: z.enum([
    "oral", "iv", "im", "sc", "topical", "inhaled", "rectal", "sublingual", "ophthalmic", "otic", "nasal",
  ]),
  frequency: z.enum(["od", "bd", "tds", "qds", "prn", "stat", "nocte", "weekly", "monthly"]),
  duration_days: z.coerce.number().min(1).max(365).nullable().optional(),
  quantity: z.coerce.number().min(1).nullable().optional(),
  instructions: z.string().nullable().optional(),
});

type PrescriptionFormData = z.infer<ReturnType<typeof createPrescriptionSchema>>;

interface PrescriptionPanelProps {
  encounterId: string;
  patientId: string;
}

/**
 * Prescription panel with drug autocomplete, KEML tagging, and CDS alerts.
 * Drug interaction checks and CDS evaluation run before save per CLAUDE.md: Clinical Safety.
 *
 * @param props - encounterId and patientId
 * @returns Prescription panel component
 */
export function PrescriptionPanel({ encounterId, patientId }: PrescriptionPanelProps) {
  const t = useTranslations("prescription");
  const tc = useTranslations("common");
  const prescriptionSchema = createPrescriptionSchema(t("drugNameRequired"), t("dosageRequired"));
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [cdsAlerts, setCdsAlerts] = useState<CDSAlert[]>([]);

  const { data: prescriptions, isLoading } = useEncounterPrescriptions(encounterId);
  const createPrescription = useCreatePrescription(encounterId);
  const evaluatePrescription = useEvaluatePrescription();

  const { register, handleSubmit, reset, setValue, watch, formState: { errors } } = useForm<PrescriptionFormData>({
    resolver: zodResolver(prescriptionSchema),
    defaultValues: {
      route: "oral",
      frequency: "od",
      is_keml: false,
    },
  });

  const isKeml = watch("is_keml");
  const watchedFreq = watch("frequency");
  const watchedDuration = watch("duration_days");

  // Auto-calculate quantity: frequency x duration_days
  useEffect(() => {
    if (watchedFreq && watchedDuration) {
      const fm: Record<string, number> = { od:1, bd:2, tds:3, qds:4, prn:1, stat:1, nocte:1, weekly:0.143, monthly:0.033 };
      const freq = fm[watchedFreq] ?? 1;
      const qty = Math.ceil(freq * Number(watchedDuration));
      if (qty > 0) setValue("quantity", qty);
    }
  }, [watchedFreq, watchedDuration, setValue]);

  /**
   * Maps interaction data from the prescription response into CDSAlert objects.
   *
   * @param result - The prescription response with interaction data
   * @returns Array of CDSAlert objects derived from interactions
   */
  const mapInteractionsToCDSAlerts = useCallback(
    (result: {
      blocked: boolean;
      interactions?: Array<{
        drug_a?: string;
        drug_b?: string;
        drug_name?: string;
        interacting_drug?: string;
        severity: string;
        description: string;
      }>;
    }): CDSAlert[] => {
      if (!result.interactions || result.interactions.length === 0) {
        return [];
      }

      return result.interactions.map((interaction, index) => {
        const drugA = interaction.drug_a ?? interaction.drug_name ?? "Prescribed drug";
        const drugB = interaction.drug_b ?? interaction.interacting_drug ?? "Interacting drug";

        return {
          alert_id: `interaction-${index}-${Date.now()}`,
          severity: result.blocked ? "critical" as const : "high" as const,
          category: "drug_interaction" as const,
          action: result.blocked ? "block" as const : "warn" as const,
          title: t("drugInteraction"),
          message: interaction.description,
          source_rule: "drug_interaction_check",
          affected_items: [drugA, drugB],
          evidence: { severity: interaction.severity },
          overridable: !result.blocked,
          requires_reason: !result.blocked,
        };
      });
    },
    [t]
  );

  /**
   * Handles override of a CDS alert by removing it from the displayed alerts.
   *
   * @param alertId - The ID of the alert to override
   * @param alertId - The ID of the alert to override
   */
  const handleOverride = useCallback(
    (alertId: string) => {
      setCdsAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
    },
    []
  );

  const onSubmit = (data: PrescriptionFormData) => {
    setCdsAlerts([]);

    createPrescription.mutate(
      {
        encounter_id: encounterId,
        patient_id: patientId,
        ...data,
      },
      {
        onSuccess: (result) => {
          // Map backend interaction data to CDS alerts
          const interactionAlerts = mapInteractionsToCDSAlerts(result);

          if (result.blocked) {
            // Show blocking CDS alerts — do not clear form
            setCdsAlerts(interactionAlerts);
          } else if (interactionAlerts.length > 0) {
            // Non-blocking warnings from interactions
            setCdsAlerts(interactionAlerts);
            setShowForm(false);
            reset();
          } else {
            // Also trigger CDS evaluation for additional rules (dose range, allergy, etc.)
            evaluatePrescription.mutate(
              {
                patient_id: patientId,
                drug_name: data.drug_name,
                encounter_id: encounterId,
              },
              {
                onSuccess: (cdsResult) => {
                  if (cdsResult.alerts.length > 0) {
                    setCdsAlerts(cdsResult.alerts);
                  }
                },
              }
            );
            setShowForm(false);
            reset();
          }
        },
      }
    );
  };

  const routeOptions = [
    "oral", "iv", "im", "sc", "topical", "inhaled", "rectal", "sublingual",
  ] as const;

  const frequencyOptions = [
    "od", "bd", "tds", "qds", "prn", "stat", "nocte",
  ] as const;

  return (
    <div className="rounded-lg border border-border bg-card dark:bg-card">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <Pill className="h-5 w-5 text-green-500" />
          <h3 className="font-semibold text-foreground">{t("title")}</h3>
          {prescriptions && prescriptions.length > 0 && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {prescriptions.length}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          {/* Existing prescriptions */}
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{tc("loading")}</p>
          ) : prescriptions && prescriptions.length > 0 ? (
            <div className="mb-3 space-y-2">
              {prescriptions.map((rx) => (
                <div
                  key={rx.id}
                  className="flex items-start gap-3 rounded-lg border border-border p-3"
                >
                  <Pill className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{rx.drug_name}</span>
                      {rx.is_keml && (
                        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
                          {t("keml")}
                        </span>
                      )}
                      {rx.interaction_checked && (
                        <ShieldCheck className="h-3.5 w-3.5 text-green-500" />
                      )}
                    </div>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {rx.dosage} — {rx.route} — {rx.frequency}
                      {rx.duration_days ? ` — ${rx.duration_days}d` : ""}
                    </p>
                    {rx.instructions && (
                      <p className="mt-1 text-xs text-muted-foreground italic">{rx.instructions}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mb-3 text-sm text-muted-foreground">{t("noPrescriptions")}</p>
          )}

          {/* CDS Alert Banner */}
          {cdsAlerts.length > 0 && (
            <div className="mb-3">
              <CDSAlertBanner
                alerts={cdsAlerts}
                onDismiss={() => setCdsAlerts([])}
                onOverride={handleOverride}
              />
            </div>
          )}

          {/* Add prescription form */}
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
              {/* Drug autocomplete */}
              <DrugAutocomplete
                onSelect={(drugName, genericName, isKeml) => {
                  setValue("drug_name", drugName);
                  if (genericName) setValue("generic_name", genericName);
                  setValue("is_keml", isKeml);
                }}
              />
              {errors.drug_name && (
                <p className="text-xs text-red-500">{errors.drug_name.message}</p>
              )}

              {/* KEML indicator */}
              {isKeml && (
                <div className="flex items-center gap-1 text-xs text-green-700 dark:text-green-300">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {t("kemlTag")}
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("dosage")}</label>
                <input
                  {...register("dosage")}
                  placeholder={t("dosagePlaceholder")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
                {errors.dosage && <p className="text-xs text-red-500">{errors.dosage.message}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("route")}</label>
                  <select
                    {...register("route")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    {routeOptions.map((r) => (
                      <option key={r} value={r}>{t(r as Parameters<typeof t>[0])}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("frequency")}</label>
                  <select
                    {...register("frequency")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    {frequencyOptions.map((f) => (
                      <option key={f} value={f}>{t(f as Parameters<typeof t>[0])}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("duration")}</label>
                  <input {...register("duration_days")} type="number" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("quantity")}</label>
                  <input {...register("quantity")} type="number" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background" />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("instructions")}</label>
                <input
                  {...register("instructions")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={createPrescription.isPending}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {createPrescription.isPending ? t("adding") : t("add")}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); reset(); setCdsAlerts([]); }}
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
