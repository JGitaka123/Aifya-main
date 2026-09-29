"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CalendarClock,
  ChevronRight,
  Droplet,
  Phone,
  Search,
  Stethoscope,
  X,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { usePatientHistory, usePatientSearch } from "@/hooks/usePatients";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTime } from "@/lib/utils";
import type { Patient } from "@aifya/shared";

/** Encounter status -> badge tone, matching the OPD queue. */
const STATUS_BADGE: Record<
  string,
  "warning" | "info" | "success" | "purple" | "default" | "error"
> = {
  waiting: "warning",
  in_consultation: "info",
  completed: "success",
  admitted: "purple",
  discharged: "default",
  cancelled: "error",
};

/**
 * Find any patient, not only today's queue.
 *
 * The room's own list only holds the patients assessed today. A doctor who is
 * handed a name at the door needs the whole record instead: what the patient
 * came with, what the nurse found last time, and where they were sent - which
 * is what decides the department they should go to now.
 *
 * @returns Patient search with the selected patient's problem and history
 */
export function ConsultationPatientLookup() {
  const t = useTranslations("consultationRoom");
  const tq = useTranslations("opd");
  const tp = useTranslations("patients.history");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Patient | null>(null);

  const term = query.trim();
  const searching = term.length >= 2;

  const { data, isFetching } = usePatientSearch(term, 1, 8, {
    enabled: searching,
  });
  const { data: history, isLoading: historyLoading } = usePatientHistory(
    selected?.id ?? "",
  );

  const results = searching ? data?.items ?? [] : [];
  const latest = history?.visits?.[0];
  const allergies = history?.allergies ?? [];
  const bloodGroup = history?.blood_group ?? selected?.blood_group ?? null;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <label
          htmlFor="consultation-patient-search"
          className="text-sm font-semibold text-foreground"
        >
          {t("searchTitle")}
        </label>
        <p className="mt-0.5 text-xs text-muted-foreground">{t("searchHint")}</p>
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="consultation-patient-search"
            type="text"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelected(null);
            }}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded-lg border border-border bg-background py-2.5 pl-10 pr-4 text-sm text-foreground shadow-sm transition-colors focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {searching && !selected && (
          <ul className="mt-2 max-h-64 divide-y divide-border overflow-y-auto rounded-lg border border-border">
            {results.length === 0 ? (
              <li className="px-4 py-3 text-sm text-muted-foreground">
                {isFetching ? t("searching") : t("searchNoResults")}
              </li>
            ) : (
              results.map((patient) => (
                <li key={patient.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(patient)}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/40"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-foreground">
                        {patient.first_name} {patient.last_name}
                      </span>
                      <span className="block font-mono text-xs text-muted-foreground">
                        {patient.mrn}
                        {patient.phone_number ? ` \u00b7 ${patient.phone_number}` : ""}
                      </span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>

      {selected && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-bold text-foreground">
                  {history?.full_name ??
                    `${selected.first_name} ${selected.last_name}`}
                </h3>
                <span className="font-mono text-xs text-muted-foreground">
                  {history?.mrn ?? selected.mrn}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {history?.age_years !== null &&
                  history?.age_years !== undefined && (
                    <span>
                      {tp("age")}:{" "}
                      <span className="text-foreground">{history.age_years}</span>
                    </span>
                  )}
                <span className="capitalize">{selected.gender}</span>
                {selected.phone_number && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3 w-3" />
                    {selected.phone_number}
                  </span>
                )}
                {bloodGroup && (
                  <span className="flex items-center gap-1">
                    <Droplet className="h-3 w-3" />
                    {tp("bloodGroup")}:{" "}
                    <span className="text-foreground">{bloodGroup}</span>
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="rounded-lg border border-border bg-card p-1.5 text-muted-foreground transition-colors hover:bg-muted"
              aria-label={t("close")}
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-4 px-5 py-4">
            {allergies.length > 0 && (
              <p className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {tp("allergies")}: {allergies.join(", ")}
              </p>
            )}

            {/* What the patient came with, so the doctor can hear the problem. */}
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Stethoscope className="h-3.5 w-3.5" />
                {t("problemTitle")}
              </p>
              {historyLoading ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("loadingRecord")}
                </p>
              ) : latest?.chief_complaint ? (
                <p className="mt-2 text-sm text-foreground">
                  {latest.chief_complaint}
                </p>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("problemNone")}
                </p>
              )}
              {latest && (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CalendarClock className="h-3 w-3" />
                    {t("latestVisit")}: {formatDateTime(latest.encounter_date)}
                  </span>
                  <span className="uppercase tracking-wide">
                    {latest.encounter_type}
                  </span>
                  <span>{latest.department_name ?? t("unassigned")}</span>
                  <StatusBadge
                    variant={STATUS_BADGE[latest.status] ?? "default"}
                    size="xs"
                  >
                    {tq(`status.${latest.status}`)}
                  </StatusBadge>
                </div>
              )}
            </div>

            <div>
              <div className="flex flex-wrap gap-2">
                {latest && (
                  <Link
                    href={`/opd/${latest.encounter_id}?tab=consultation`}
                    className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-colors hover:bg-primary/90"
                  >
                    <Stethoscope className="h-4 w-4" />
                    {t("openConsultation")}
                  </Link>
                )}
                <Link
                  href={`/patients/${selected.id}`}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
                >
                  {t("openRecord")}
                </Link>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {t("routeHint")}
              </p>
            </div>

            {history && history.visits.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("previousServices", { count: history.visit_count })}
                </p>
                <ul className="mt-2 space-y-2">
                  {history.visits.slice(0, 5).map((visit) => (
                    <li
                      key={visit.encounter_id}
                      className="rounded-lg border border-border bg-background p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">
                          {formatDateTime(visit.encounter_date)}
                        </span>
                        <span className="uppercase tracking-wide">
                          {visit.encounter_type}
                        </span>
                        {visit.department_name && (
                          <span>{visit.department_name}</span>
                        )}
                        <StatusBadge
                          variant={STATUS_BADGE[visit.status] ?? "default"}
                          size="xs"
                        >
                          {tq(`status.${visit.status}`)}
                        </StatusBadge>
                      </div>
                      {visit.chief_complaint && (
                        <p className="mt-1 text-sm text-foreground">
                          {visit.chief_complaint}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
