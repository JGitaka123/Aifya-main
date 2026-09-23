"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Heart,
  Thermometer,
  Wind,
  Plus,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useEncounterVitals, useRecordVitals } from "@/hooks/useEncounters";
import { useEvaluateVitals } from "@/hooks/useCDS";
import { CDSAlertBanner } from "@/components/opd/CDSAlertBanner";
import type { CDSAlert, VitalSignCreate } from "@aifya/shared";

const vitalsSchema = z.object({
  systolic_bp: z.coerce.number().min(40).max(300).nullable().optional(),
  diastolic_bp: z.coerce.number().min(20).max(200).nullable().optional(),
  heart_rate: z.coerce.number().min(20).max(300).nullable().optional(),
  temperature: z.coerce.number().min(25).max(45).nullable().optional(),
  temperature_site: z.string().nullable().optional(),
  respiratory_rate: z.coerce.number().min(4).max(80).nullable().optional(),
  oxygen_saturation: z.coerce.number().min(0).max(100).nullable().optional(),
  on_supplemental_o2: z.boolean().optional(),
  o2_flow_rate: z.coerce.number().min(0).max(60).nullable().optional(),
  weight_kg: z.coerce.number().min(0.1).max(500).nullable().optional(),
  height_cm: z.coerce.number().min(20).max(300).nullable().optional(),
  pain_score: z.coerce.number().min(0).max(10).nullable().optional(),
  blood_glucose: z.coerce.number().min(0).max(50).nullable().optional(),
  glucose_timing: z.string().nullable().optional(),
  gcs_eye: z.coerce.number().min(1).max(4).nullable().optional(),
  gcs_verbal: z.coerce.number().min(1).max(5).nullable().optional(),
  gcs_motor: z.coerce.number().min(1).max(6).nullable().optional(),
});

type VitalsFormData = z.infer<typeof vitalsSchema>;

interface VitalsPanelProps {
  encounterId: string;
  patientId: string;
}

/**
 * Vitals recording and display panel for the consultation page.
 * Critical values trigger immediate visual alerts per CLAUDE.md: Clinical Safety.
 * After recording, CDS evaluation provides richer alerts (sepsis risk, age-adjusted thresholds).
 *
 * @param props - encounterId and patientId
 * @returns Vitals panel component
 */
export function VitalsPanel({ encounterId, patientId }: VitalsPanelProps) {
  const t = useTranslations("vitals");
  const tc = useTranslations("common");
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [cdsAlerts, setCdsAlerts] = useState<CDSAlert[]>([]);

  const { data: vitals, isLoading } = useEncounterVitals(encounterId);
  const recordVitals = useRecordVitals(encounterId);
  const evaluateVitals = useEvaluateVitals();

  const { register, handleSubmit, reset } = useForm<VitalsFormData>({
    resolver: zodResolver(vitalsSchema),
  });

  const onSubmit = (data: VitalsFormData) => {
    const cleaned: VitalSignCreate = {
      encounter_id: encounterId,
      patient_id: patientId,
      ...Object.fromEntries(
        Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== "")
      ),
    };

    recordVitals.mutate(cleaned, {
      onSuccess: () => {
        setShowForm(false);
        reset();

        // Trigger CDS evaluation for detailed alerts (sepsis risk, age-adjusted, trending)
        const vitalsDict: Record<string, number | string | null> = {};
        if (data.systolic_bp != null) vitalsDict.systolic_bp = data.systolic_bp;
        if (data.diastolic_bp != null) vitalsDict.diastolic_bp = data.diastolic_bp;
        if (data.heart_rate != null) vitalsDict.heart_rate = data.heart_rate;
        if (data.temperature != null) vitalsDict.temperature = data.temperature;
        if (data.respiratory_rate != null) vitalsDict.respiratory_rate = data.respiratory_rate;
        if (data.oxygen_saturation != null) vitalsDict.oxygen_saturation = data.oxygen_saturation;
        if (data.blood_glucose != null) vitalsDict.blood_glucose = data.blood_glucose;
        if (data.pain_score != null) vitalsDict.pain_score = data.pain_score;
        if (data.gcs_eye != null && data.gcs_verbal != null && data.gcs_motor != null) {
          vitalsDict.gcs_total = data.gcs_eye + data.gcs_verbal + data.gcs_motor;
        }

        evaluateVitals.mutate(
          {
            patient_id: patientId,
            vitals: vitalsDict,
          },
          {
            onSuccess: (cdsResult) => {
              if (cdsResult.alerts.length > 0) {
                setCdsAlerts(cdsResult.alerts);
              }
            },
          }
        );
      },
    });
  };

  const latestVital = vitals?.[0];

  return (
    <div className="rounded-lg border border-border bg-card dark:bg-card">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <Heart className="h-5 w-5 text-red-500" />
          <h3 className="font-semibold text-foreground">{t("title")}</h3>
          {latestVital?.is_critical && (
            <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700 dark:bg-red-950 dark:text-red-300">
              <AlertTriangle className="h-3 w-3" />
              {t("critical")}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          {/* Critical alert banner from backend response */}
          {latestVital?.is_critical && latestVital.critical_alerts && (
            <div className="mb-3 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <p className="font-bold">{t("criticalAlert")}</p>
                <p className="mt-1">{latestVital.critical_alerts}</p>
              </div>
            </div>
          )}

          {/* CDS Alert Banner — richer alerts from CDS evaluation */}
          {cdsAlerts.length > 0 && (
            <div className="mb-3">
              <CDSAlertBanner
                alerts={cdsAlerts}
                onDismiss={() => setCdsAlerts([])}
              />
            </div>
          )}

          {/* Latest vitals display */}
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{tc("loading")}</p>
          ) : latestVital ? (
            <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {latestVital.systolic_bp != null && (
                <VitalCard
                  icon={<Heart className="h-4 w-4" />}
                  label={t("bloodPressure")}
                  value={`${latestVital.systolic_bp}/${latestVital.diastolic_bp ?? "—"}`}
                  unit="mmHg"
                />
              )}
              {latestVital.heart_rate != null && (
                <VitalCard
                  icon={<Heart className="h-4 w-4" />}
                  label={t("heartRate")}
                  value={String(latestVital.heart_rate)}
                  unit="bpm"
                />
              )}
              {latestVital.temperature != null && (
                <VitalCard
                  icon={<Thermometer className="h-4 w-4" />}
                  label={t("temperature")}
                  value={String(latestVital.temperature)}
                  unit="°C"
                />
              )}
              {latestVital.oxygen_saturation != null && (
                <VitalCard
                  icon={<Wind className="h-4 w-4" />}
                  label={t("oxygenSaturation")}
                  value={String(latestVital.oxygen_saturation)}
                  unit="%"
                />
              )}
              {latestVital.respiratory_rate != null && (
                <VitalCard
                  icon={<Wind className="h-4 w-4" />}
                  label={t("respiratoryRate")}
                  value={String(latestVital.respiratory_rate)}
                  unit="/min"
                />
              )}
              {latestVital.bmi != null && (
                <VitalCard
                  icon={null}
                  label={t("bmi")}
                  value={String(latestVital.bmi)}
                  unit=""
                />
              )}
              {latestVital.pain_score != null && (
                <VitalCard
                  icon={null}
                  label={t("painScore")}
                  value={`${latestVital.pain_score}/10`}
                  unit=""
                />
              )}
              {latestVital.blood_glucose != null && (
                <VitalCard
                  icon={null}
                  label={t("bloodGlucose")}
                  value={String(latestVital.blood_glucose)}
                  unit="mmol/L"
                />
              )}
            </div>
          ) : (
            <p className="mb-3 text-sm text-muted-foreground">{t("noVitals")}</p>
          )}

          {/* Add vitals button / form */}
          {!showForm ? (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              {t("record")}
            </button>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <VitalInput label={t("systolic")} {...register("systolic_bp")} type="number" />
                <VitalInput label={t("diastolic")} {...register("diastolic_bp")} type="number" />
                <VitalInput label={t("heartRate")} {...register("heart_rate")} type="number" />
                <VitalInput label={t("temperature")} {...register("temperature")} type="number" step="0.1" />
                <VitalInput label={t("respiratoryRate")} {...register("respiratory_rate")} type="number" />
                <VitalInput label={t("oxygenSaturation")} {...register("oxygen_saturation")} type="number" step="0.1" />
                <VitalInput label={t("weight")} {...register("weight_kg")} type="number" step="0.1" />
                <VitalInput label={t("height")} {...register("height_cm")} type="number" step="0.1" />
                <VitalInput label={t("painScore")} {...register("pain_score")} type="number" />
                <VitalInput label={t("bloodGlucose")} {...register("blood_glucose")} type="number" step="0.1" />
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={recordVitals.isPending}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {recordVitals.isPending ? t("recording") : t("record")}
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

/**
 * Card component displaying a single vital sign value.
 *
 * @param props - icon, label, value, and unit to display
 * @returns Vital sign card element
 */
function VitalCard({ icon, label, value, unit }: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-2 dark:bg-muted/10">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-0.5 text-lg font-semibold text-foreground">
        {value}
        <span className="ml-0.5 text-xs font-normal text-muted-foreground">{unit}</span>
      </div>
    </div>
  );
}

/**
 * Input field for a vital sign value with label.
 *
 * @param props - label and standard HTML input attributes
 * @returns Labeled input element
 */
function VitalInput({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label>
      <input
        {...props}
        className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring dark:border-border dark:bg-background"
      />
    </div>
  );
}
