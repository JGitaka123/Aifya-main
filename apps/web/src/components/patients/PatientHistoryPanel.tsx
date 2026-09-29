"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Droplet,
  History,
  Pill,
  Stethoscope,
} from "lucide-react";
import { cn, formatDateTime } from "@/lib/utils";
import { usePatientHistory } from "@/hooks/usePatients";

/**
 * Clinical history panel shown at the point of care.
 *
 * Surfaces the safety-critical patient-level fields (allergies, chronic
 * conditions, blood group) together with previous visits and what was
 * diagnosed or prescribed, so a clinician who has just been handed a
 * redirected patient can see prior care without leaving the consultation.
 *
 * @param props.patientId - Patient UUID
 * @param props.excludeEncounterId - Encounter to omit (the visit being worked on)
 * @returns Collapsible patient history panel
 */
export function PatientHistoryPanel({
  patientId,
  excludeEncounterId,
}: {
  patientId: string;
  excludeEncounterId?: string;
}) {
  const t = useTranslations("patients.history");
  const [open, setOpen] = useState(true);

  const { data, isLoading } = usePatientHistory(patientId, excludeEncounterId);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
        {t("loading")}
      </div>
    );
  }

  if (!data) return null;

  const allergies = data.allergies ?? [];
  const chronicConditions = data.chronic_conditions ?? [];
  const hasAllergies = allergies.length > 0;

  return (
    <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <span className="flex flex-wrap items-center gap-2">
          <History className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">
            {t("title")}
          </span>
          <span className="text-xs text-muted-foreground">
            {t("previousVisits")}: {data.visit_count}
          </span>
        </span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {open ? t("hide") : t("show")}
          {open ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-5 py-4">
          {/* Safety-critical fields come first. */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div
              className={cn(
                "rounded-lg border px-3 py-2",
                hasAllergies
                  ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950"
                  : "border-border bg-muted/40"
              )}
            >
              <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <AlertTriangle className="h-3.5 w-3.5" />
                {t("allergies")}
              </p>
              <p
                className={cn(
                  "mt-1 text-sm font-semibold",
                  hasAllergies
                    ? "text-red-700 dark:text-red-300"
                    : "text-muted-foreground"
                )}
              >
                {hasAllergies ? allergies.join(", ") : t("noAllergies")}
              </p>
            </div>

            <div className="rounded-lg border border-border bg-muted/40 px-3 py-2">
              <p className="text-xs font-semibold text-muted-foreground">
                {t("chronicConditions")}
              </p>
              <p className="mt-1 text-sm font-medium text-foreground">
                {chronicConditions.length > 0
                  ? chronicConditions.join(", ")
                  : t("noneRecorded")}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
            {data.age_years !== null && (
              <span>
                {t("age")}:{" "}
                <span className="text-foreground">{data.age_years}</span>
              </span>
            )}
            {data.blood_group && (
              <span className="flex items-center gap-1">
                <Droplet className="h-3 w-3" />
                {t("bloodGroup")}:{" "}
                <span className="text-foreground">{data.blood_group}</span>
              </span>
            )}
            <span>
              MRN: <span className="font-mono text-foreground">{data.mrn}</span>
            </span>
            {data.last_visit_date && (
              <span>
                {t("lastVisit")}:{" "}
                <span className="text-foreground">
                  {formatDateTime(data.last_visit_date)}
                </span>
              </span>
            )}
          </div>

          {data.visits.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("noPreviousVisits")}
            </p>
          ) : (
            <ul className="space-y-3">
              {data.visits.map((visit) => (
                <li
                  key={visit.encounter_id}
                  className="rounded-lg border border-border bg-background p-3"
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                      <Stethoscope className="h-3.5 w-3.5 text-muted-foreground" />
                      {formatDateTime(visit.encounter_date)}
                    </span>
                    <span className="text-xs uppercase tracking-wide text-muted-foreground">
                      {visit.encounter_type}
                    </span>
                    {visit.department_name && (
                      <span className="text-xs text-muted-foreground">
                        {visit.department_name}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {visit.attending_doctor_name
                        ? t("seenBy", { name: visit.attending_doctor_name })
                        : t("unassigned")}
                    </span>
                  </div>

                  {visit.chief_complaint && (
                    <p className="mt-2 text-sm text-foreground">
                      {visit.chief_complaint}
                    </p>
                  )}

                  {visit.diagnoses.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs font-semibold text-muted-foreground">
                        {t("diagnoses")}
                      </p>
                      <ul className="mt-0.5 space-y-0.5">
                        {visit.diagnoses.map((diagnosis, index) => (
                          <li
                            key={`${visit.encounter_id}-dx-${index}`}
                            className="text-xs text-foreground"
                          >
                            <span className="font-mono text-muted-foreground">
                              {diagnosis.icd10_code}
                            </span>{" "}
                            {diagnosis.icd10_description}
                            {diagnosis.is_chronic && (
                              <span className="ml-1 text-amber-600 dark:text-amber-400">
                                ({t("chronicConditions")})
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {visit.prescriptions.length > 0 && (
                    <div className="mt-2">
                      <p className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                        <Pill className="h-3 w-3" />
                        {t("prescriptions")}
                      </p>
                      <ul className="mt-0.5 space-y-0.5">
                        {visit.prescriptions.map((prescription, index) => (
                          <li
                            key={`${visit.encounter_id}-rx-${index}`}
                            className="text-xs text-foreground"
                          >
                            {prescription.drug_name} &mdash;{" "}
                            {prescription.dosage}, {prescription.frequency}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
