"use client";

import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  Stethoscope,
  Pill,
  FlaskConical,
  Scissors,
  Lightbulb,
  ArrowRight,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ClinicalExtraction } from "@aifya/shared";

interface ScribeExtractionPanelProps {
  /** The AI-extracted clinical data for review. */
  extraction: ClinicalExtraction;
  /** Callback when clinician signs off on the extraction. */
  onSignOff: (extraction: ClinicalExtraction) => void;
  /** Callback when clinician discards the extraction. */
  onDiscard: () => void;
}

/**
 * Renders a confidence badge with color coding.
 * >=0.9 green, >=0.7 amber, <0.7 red.
 *
 * @param props - confidence value (0-1), label text
 * @returns Confidence badge element
 */
function ConfidenceBadge({
  confidence,
  label,
}: {
  confidence: number;
  label: string;
}) {
  const colorClass =
    confidence >= 0.9
      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      : confidence >= 0.7
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
        : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        colorClass
      )}
    >
      {label} {Math.round(confidence * 100)}%
    </span>
  );
}

/**
 * Section wrapper with title for extraction panels.
 *
 * @param props - title, icon, children
 * @returns Section wrapper element
 */
function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

/**
 * Display panel for AI-extracted clinical data from ScribeAI.
 * Renders extraction results in organized sections for clinician review.
 * AI NEVER auto-commits — clinician must explicitly sign off.
 *
 * @param props - extraction data, sign-off and discard callbacks
 * @returns ScribeExtractionPanel component
 */
export function ScribeExtractionPanel({
  extraction,
  onSignOff,
  onDiscard,
}: ScribeExtractionPanelProps) {
  const t = useTranslations("scribe");

  return (
    <div className="mt-4 space-y-4 rounded-lg border border-border bg-card p-4 dark:bg-card">
      {/* Warnings banner */}
      {extraction.warnings.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600 dark:text-amber-400" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
              {t("warnings")}
            </p>
            <ul className="list-disc pl-4 text-xs text-amber-700 dark:text-amber-400">
              {extraction.warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Chief Complaint */}
      {extraction.chief_complaint && (
        <Section
          title={t("chiefComplaint")}
          icon={<Stethoscope className="h-4 w-4 text-primary" />}
        >
          <p className="text-sm text-foreground dark:text-foreground">
            {extraction.chief_complaint}
          </p>
        </Section>
      )}

      {/* HPI */}
      {extraction.hpi && (
        <Section
          title={t("hpi")}
          icon={<Stethoscope className="h-4 w-4 text-primary" />}
        >
          <p className="text-sm text-foreground dark:text-foreground">
            {extraction.hpi}
          </p>
        </Section>
      )}

      {/* Vitals */}
      {extraction.vitals.length > 0 && (
        <Section
          title={t("vitals")}
          icon={<Stethoscope className="h-4 w-4 text-primary" />}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-1 pr-4">{t("vitals")}</th>
                  <th className="pb-1 pr-4">{t("confidence")}</th>
                  <th className="pb-1">{t("loincCode")}</th>
                </tr>
              </thead>
              <tbody>
                {extraction.vitals.map((vital, idx) => (
                  <tr key={idx} className="border-b border-border/50">
                    <td className="py-1.5 pr-4 text-foreground">
                      <span className="font-medium">{vital.name}:</span>{" "}
                      {vital.value}
                    </td>
                    <td className="py-1.5 pr-4">
                      <ConfidenceBadge
                        confidence={vital.confidence}
                        label={t("confidence")}
                      />
                    </td>
                    <td className="py-1.5 font-mono text-xs text-muted-foreground">
                      {vital.loinc_code ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Physical Exam */}
      {extraction.physical_exam && (
        <Section
          title={t("physicalExam")}
          icon={<Stethoscope className="h-4 w-4 text-primary" />}
        >
          <p className="text-sm text-foreground dark:text-foreground">
            {extraction.physical_exam}
          </p>
        </Section>
      )}

      {/* Diagnoses */}
      {extraction.diagnoses.length > 0 && (
        <Section
          title={t("diagnoses")}
          icon={<Stethoscope className="h-4 w-4 text-primary" />}
        >
          <div className="grid gap-2">
            {extraction.diagnoses.map((dx, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-md border border-border bg-muted/50 p-2 dark:bg-muted/20"
              >
                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-foreground">
                    {dx.name}
                  </p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {t("icd11")}: {dx.icd11_validated ?? dx.icd11_suggested ?? "—"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {dx.is_primary && (
                    <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {t("primary")}
                    </span>
                  )}
                  <ConfidenceBadge
                    confidence={dx.confidence}
                    label={t("confidence")}
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Medications */}
      {extraction.medications.length > 0 && (
        <Section
          title={t("medications")}
          icon={<Pill className="h-4 w-4 text-primary" />}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-1 pr-3">{t("medications")}</th>
                  <th className="pb-1 pr-3">{t("dose")}</th>
                  <th className="pb-1 pr-3">{t("route")}</th>
                  <th className="pb-1 pr-3">{t("frequency")}</th>
                  <th className="pb-1">{t("duration")}</th>
                </tr>
              </thead>
              <tbody>
                {extraction.medications.map((med, idx) => (
                  <tr key={idx} className="border-b border-border/50">
                    <td className="py-1.5 pr-3 text-foreground">
                      <span className="font-medium">{med.name}</span>
                      {med.is_new && (
                        <span className="ml-2 inline-flex items-center rounded-full bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                          {t("new")}
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-foreground">
                      {med.dose ?? "—"}
                    </td>
                    <td className="py-1.5 pr-3 text-foreground">
                      {med.route ?? "—"}
                    </td>
                    <td className="py-1.5 pr-3 text-foreground">
                      {med.frequency ?? "—"}
                    </td>
                    <td className="py-1.5 text-foreground">
                      {med.duration ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {/* Lab Orders */}
      {extraction.lab_orders.length > 0 && (
        <Section
          title={t("labOrders")}
          icon={<FlaskConical className="h-4 w-4 text-primary" />}
        >
          <div className="space-y-1">
            {extraction.lab_orders.map((lab, idx) => {
              const urgencyClass =
                lab.urgency === "stat"
                  ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                  : lab.urgency === "urgent"
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
                    : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";

              return (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-md border border-border/50 px-3 py-1.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-foreground">{lab.test_name}</span>
                    {lab.loinc_code && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {lab.loinc_code}
                      </span>
                    )}
                  </div>
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                      urgencyClass
                    )}
                  >
                    {t(lab.urgency)}
                  </span>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Procedures */}
      {extraction.procedures.length > 0 && (
        <Section
          title={t("procedures")}
          icon={<Scissors className="h-4 w-4 text-primary" />}
        >
          <div className="space-y-1">
            {extraction.procedures.map((proc, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-md border border-border/50 px-3 py-1.5"
              >
                <span className="text-sm text-foreground">{proc.name}</span>
                <div className="flex items-center gap-2">
                  {proc.ichi_code && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {proc.ichi_code}
                    </span>
                  )}
                  {proc.requires_preauth && (
                    <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900/30 dark:text-orange-400">
                      {t("preAuthorization")}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Suggested Tests */}
      {extraction.suggested_tests.length > 0 && (
        <Section
          title={t("suggestedTests")}
          icon={<Lightbulb className="h-4 w-4 text-primary" />}
        >
          <div className="flex flex-wrap gap-2">
            {extraction.suggested_tests.map((test, idx) => (
              <span
                key={idx}
                className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/20 dark:text-blue-400"
              >
                {test}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Disposition & Follow-up */}
      {(extraction.disposition || extraction.follow_up) && (
        <Section
          title={t("disposition")}
          icon={<ArrowRight className="h-4 w-4 text-primary" />}
        >
          {extraction.disposition && (
            <p className="text-sm text-foreground">
              <span className="font-medium">{t("disposition")}:</span>{" "}
              {extraction.disposition}
            </p>
          )}
          {extraction.follow_up && (
            <p className="text-sm text-foreground">
              <span className="font-medium">{t("followUp")}:</span>{" "}
              {extraction.follow_up}
            </p>
          )}
        </Section>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <div className="text-xs text-muted-foreground">
          {t("signOffDescription")}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onDiscard}
            className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground dark:hover:bg-muted/50"
          >
            <Trash2 className="h-4 w-4" />
            {t("discard")}
          </button>
          <button
            onClick={() => onSignOff(extraction)}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <CheckCircle2 className="h-4 w-4" />
            {t("signOff")}
          </button>
        </div>
      </div>
    </div>
  );
}
