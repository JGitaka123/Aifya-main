"use client";

import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  ClipboardCheck,
  Droplets,
  Heart,
  Ruler,
  Scale,
  Thermometer,
  Wind,
  type LucideIcon,
} from "lucide-react";
import { useEncounterTests, useEncounterVitals } from "@/hooks/useEncounters";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn, formatDateTime } from "@/lib/utils";
import type { Encounter } from "@aifya/shared";

/** Triage colour, matching the encounter header's left border. */
const TRIAGE_BADGE: Record<
  string,
  "red-solid" | "orange-solid" | "yellow-solid" | "green-solid" | "blue-solid"
> = {
  emergency: "red-solid",
  urgent: "orange-solid",
  standard: "yellow-solid",
  non_urgent: "green-solid",
  dead: "blue-solid",
};

/** Screening result wording, shared with OpdTestsPanel. */
const INTERPRETATION_LABEL_KEYS = {
  normal: "testsInterpretationNormal",
  abnormal: "testsInterpretationAbnormal",
  positive: "testsInterpretationPositive",
  negative: "testsInterpretationNegative",
  reactive: "testsInterpretationReactive",
  non_reactive: "testsInterpretationNonReactive",
  inconclusive: "testsInterpretationInconclusive",
} as const;

function HandoffVital({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <p className="mt-1 text-lg font-bold text-foreground">
        {value} <span className="text-xs font-normal text-muted-foreground">{unit}</span>
      </p>
    </div>
  );
}

/**
 * Read-only record of what OPD gathered before the doctor's consultation.
 *
 * The nurse's observations and bedside screening are what release a patient to
 * the consultation room, so the doctor opening the record inherits them here
 * instead of having to walk back to the OPD testing tab. Read-only by design:
 * this panel reports the OPD hand-off, it does not add to it.
 *
 * @param props - The encounter whose OPD work is being shown
 * @returns The OPD hand-off summary
 */
export function OpdHandoffPanel({ encounter }: { encounter: Encounter }) {
  const t = useTranslations("opd");
  const { data: vitals } = useEncounterVitals(encounter.id);
  const { data: tests } = useEncounterTests(encounter.id);

  const latest = vitals?.[0];
  const triageCategory = encounter.triage_category ?? "non_urgent";
  const hasTests = Boolean(tests && tests.length > 0);

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <ClipboardCheck className="h-4 w-4 text-primary" />
          {t("handoffTitle")}
        </h3>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <StatusBadge variant={TRIAGE_BADGE[triageCategory] ?? "yellow-solid"} size="xs">
            {t(`triageStatus.${triageCategory}`)}
          </StatusBadge>
          {encounter.triaged_at ? (
            <span>{t("handoffTriagedAt", { date: formatDateTime(encounter.triaged_at) })}</span>
          ) : (
            <span className="font-medium text-amber-600 dark:text-amber-400">
              {t("handoffNotTriaged")}
            </span>
          )}
          {encounter.nurse_name && (
            <span>{t("triagedBy", { name: encounter.nurse_name })}</span>
          )}
        </div>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">{t("handoffHint")}</p>

      {!latest && !hasTests ? (
        <p className="mt-3 rounded-lg border border-dashed border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          {t("handoffEmpty")}
        </p>
      ) : (
        <div className="mt-3 space-y-4">
          {latest && (
            <div>
              {latest.is_critical && (
                <div className="mb-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
                  <p className="flex items-center gap-2 text-xs font-semibold text-red-600 dark:text-red-400">
                    <AlertTriangle className="h-4 w-4" />
                    {t("criticalLabel")} {latest.critical_alerts}
                  </p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {latest.systolic_bp && (
                  <HandoffVital icon={Heart} label={t("bloodPressureShort")} value={`${latest.systolic_bp}/${latest.diastolic_bp}`} unit="mmHg" />
                )}
                {latest.heart_rate && (
                  <HandoffVital icon={Activity} label={t("heartRate")} value={String(latest.heart_rate)} unit="bpm" />
                )}
                {latest.temperature && (
                  <HandoffVital icon={Thermometer} label={t("temperatureShort")} value={String(latest.temperature)} unit="°C" />
                )}
                {latest.respiratory_rate && (
                  <HandoffVital icon={Wind} label={t("respiratoryRateShort")} value={String(latest.respiratory_rate)} unit="/min" />
                )}
                {latest.oxygen_saturation && (
                  <HandoffVital icon={Droplets} label={t("oxygenSaturationShort")} value={String(latest.oxygen_saturation)} unit="%" />
                )}
                {latest.weight_kg && (
                  <HandoffVital icon={Scale} label={t("weight")} value={String(latest.weight_kg)} unit="kg" />
                )}
                {latest.height_cm && (
                  <HandoffVital icon={Ruler} label={t("height")} value={String(latest.height_cm)} unit="cm" />
                )}
                {latest.pain_score !== null && latest.pain_score !== undefined && (
                  <HandoffVital icon={AlertTriangle} label={t("pain")} value={String(latest.pain_score)} unit="/10" />
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {t("recordedAt", { date: formatDateTime(latest.recorded_at) })}
              </p>
            </div>
          )}

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("testsHistoryTitle")}
            </h4>
            {hasTests ? (
              <ul className="mt-2 space-y-2">
                {tests!.map((test) => (
                  <li
                    key={test.id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/40 p-3"
                  >
                    <span className="text-sm font-medium text-foreground">{test.test_name}</span>
                    <span className="text-sm text-muted-foreground">
                      {test.result_value}
                      {test.result_unit ? ` ${test.result_unit}` : ""}
                    </span>
                    {test.interpretation && (
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-semibold",
                          test.is_abnormal
                            ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {t(INTERPRETATION_LABEL_KEYS[test.interpretation])}
                      </span>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatDateTime(test.performed_at)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">{t("testsEmpty")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
