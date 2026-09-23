"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Search, User, X } from "lucide-react";
import { usePatientSearch } from "@/hooks/usePatients";
import type { Patient } from "@aifya/shared";

interface PatientLookupProps {
  value: Patient | null;
  onSelect: (patient: Patient | null) => void;
  error?: string;
  required?: boolean;
}

/**
 * Searchable patient selector backed by the offline-aware patient index.
 *
 * @param props - Current patient, selection callback, and validation state
 * @returns A patient search field or selected-patient summary
 */
export function PatientLookup({ value, onSelect, error, required = false }: PatientLookupProps) {
  const t = useTranslations("patientLookup");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { data, isLoading } = usePatientSearch(query.length >= 2 ? query : undefined, 1, 8);

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-foreground">
        {t("label")} {required ? "*" : ""}
      </label>
      {value ? (
        <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/5 px-3 py-2.5">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-primary/10 text-primary">
              <User className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-foreground">
                {value.first_name} {value.last_name}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {value.mrn} · {value.phone_number}
              </span>
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              setQuery("");
            }}
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={t("clear")}
            title={t("clear")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <div className="flex items-center gap-2 rounded-lg border border-input bg-background px-3 focus-within:ring-2 focus-within:ring-ring">
            <Search className="h-4 w-4 flex-none text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              placeholder={t("placeholder")}
              autoComplete="off"
              className="h-10 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
            {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          </div>
          {open && query.length >= 2 && (
            <div className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-card py-1 shadow-lg">
              {data?.items.length ? (
                data.items.map((patient) => (
                  <button
                    type="button"
                    key={patient.id}
                    onClick={() => {
                      onSelect(patient);
                      setQuery(`${patient.first_name} ${patient.last_name}`);
                      setOpen(false);
                    }}
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-muted"
                  >
                    <User className="h-4 w-4 flex-none text-muted-foreground" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-foreground">
                        {patient.first_name} {patient.last_name}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {patient.mrn} · {patient.phone_number}
                      </span>
                    </span>
                  </button>
                ))
              ) : (
                <p className="px-3 py-4 text-center text-sm text-muted-foreground">{t("noResults")}</p>
              )}
            </div>
          )}
        </div>
      )}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
