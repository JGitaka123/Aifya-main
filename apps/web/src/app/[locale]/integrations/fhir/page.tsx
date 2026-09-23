"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Plug,
  Server,
  Search,
  FileJson,
  ChevronDown,
  ChevronRight,
  Activity,
  Users,
  Stethoscope,
  Pill,
  FlaskConical,
  HeartPulse,
} from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useFHIRCapability, useFHIRPatients, useFHIREncounters, useFHIRObservations } from "@/hooks/useFHIR";
import type { FHIRResourceType } from "@aifya/shared";

/** Resource type display config. */
const RESOURCE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Patient: Users,
  Encounter: Stethoscope,
  Observation: HeartPulse,
  MedicationRequest: Pill,
  Condition: Activity,
  DiagnosticReport: FlaskConical,
};

/**
 * FHIR R4 Interoperability Gateway explorer page.
 * Shows server capability statement and allows resource browsing.
 *
 * @returns FHIR explorer page component
 */
export default function FHIRExplorerPage() {
  const t = useTranslations("fhir");
  const tc = useTranslations("common");

  const capabilityQuery = useFHIRCapability();
  const capability = capabilityQuery.data;

  const [selectedResource, setSelectedResource] = useState<FHIRResourceType | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [expandedResource, setExpandedResource] = useState<string | null>(null);

  // Resource search queries — only fire when user searches
  const [searchParams, setSearchParams] = useState<{ type: string; query: string } | null>(null);

  const patientSearch = useFHIRPatients(
    searchParams?.type === "Patient" ? { name: searchParams.query } : undefined,
  );
  const encounterSearch = useFHIREncounters(
    searchParams?.type === "Encounter" ? { patient: searchParams.query } : undefined,
  );
  const observationSearch = useFHIRObservations(
    searchParams?.type === "Observation" ? { patient: searchParams.query } : undefined,
  );

  const activeSearch =
    searchParams?.type === "Patient"
      ? patientSearch
      : searchParams?.type === "Encounter"
        ? encounterSearch
        : searchParams?.type === "Observation"
          ? observationSearch
          : null;

  const handleSearch = () => {
    if (selectedResource && searchInput.trim()) {
      setSearchParams({ type: selectedResource, query: searchInput.trim() });
    }
  };

  const resources = capability?.rest?.[0]?.resource ?? [];

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        icon={Plug}
      />

      {/* Server Info */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Server className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold text-foreground">
              {capability?.title ?? t("serverTitle")}
            </h2>
            <p className="text-xs text-muted-foreground">
              {capability?.description ?? t("serverDescription")}
            </p>
          </div>
          {capability && (
            <StatusBadge variant="success" className="ml-auto">
              {t("online")}
            </StatusBadge>
          )}
          {capabilityQuery.isLoading && (
            <Skeleton className="ml-auto h-6 w-16 rounded-full" />
          )}
        </div>

        {capability && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <span className="text-xs text-muted-foreground">{t("fhirVersion")}</span>
              <p className="text-sm font-medium">{capability.fhirVersion}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">{t("format")}</span>
              <p className="text-sm font-medium">{capability.format?.join(", ")}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">{t("status")}</span>
              <p className="text-sm font-medium capitalize">{capability.status}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">{t("resources")}</span>
              <p className="text-sm font-medium">{resources.length} {t("resourceTypes")}</p>
            </div>
          </div>
        )}
      </div>

      {/* Supported Resources */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">{t("supportedResources")}</h2>

        {capabilityQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {resources.map((res) => {
              const Icon = RESOURCE_ICONS[res.type] ?? FileJson;
              const isExpanded = expandedResource === res.type;
              const interactions = res.interaction?.map((i: { code: string }) => i.code) ?? [];
              const params = res.searchParam ?? [];

              return (
                <div
                  key={res.type}
                  className="rounded-xl border border-border bg-card shadow-sm overflow-hidden"
                >
                  <button
                    onClick={() => setExpandedResource(isExpanded ? null : res.type)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/20"
                  >
                    <Icon className="h-5 w-5 text-primary" />
                    <span className="font-medium text-foreground">{res.type}</span>
                    <div className="ml-auto flex items-center gap-2">
                      {interactions.map((code: string) => (
                        <span
                          key={code}
                          className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {code}
                        </span>
                      ))}
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </button>

                  {isExpanded && params.length > 0 && (
                    <div className="border-t border-border bg-muted/10 px-4 py-3">
                      <span className="mb-2 block text-xs font-medium text-muted-foreground">
                        {t("searchParameters")}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {params.map((p: { name: string; type: string }) => (
                          <span
                            key={p.name}
                            className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1 text-xs"
                          >
                            <span className="font-medium">{p.name}</span>
                            <span className="text-muted-foreground">({p.type})</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Resource Explorer */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">{t("explorer")}</h2>

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("resourceType")}
            </label>
            <select
              value={selectedResource ?? ""}
              onChange={(e) => setSelectedResource((e.target.value || null) as FHIRResourceType | null)}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
            >
              <option value="">{t("selectResource")}</option>
              <option value="Patient">Patient</option>
              <option value="Encounter">Encounter</option>
              <option value="Observation">Observation</option>
              <option value="MedicationRequest">MedicationRequest</option>
              <option value="Condition">Condition</option>
              <option value="DiagnosticReport">DiagnosticReport</option>
            </select>
          </div>

          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("searchQuery")}
            </label>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder={
                selectedResource === "Patient"
                  ? t("searchByName")
                  : t("searchByPatientId")
              }
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm"
            />
          </div>

          <button
            onClick={handleSearch}
            disabled={!selectedResource || !searchInput.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            <Search className="h-4 w-4" />
            {tc("search")}
          </button>
        </div>

        {/* Search Results */}
        {activeSearch && (
          <div className="rounded-xl border border-border bg-card shadow-sm">
            <div className="border-b border-border px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {searchParams?.type} {t("searchResults")}
                </span>
                {activeSearch.data && (
                  <span className="text-xs text-muted-foreground">
                    {activeSearch.data.total ?? activeSearch.data.entry?.length ?? 0} {t("found")}
                  </span>
                )}
              </div>
            </div>

            <div className="max-h-[500px] overflow-y-auto p-4">
              {activeSearch.isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 rounded-lg" />
                  ))}
                </div>
              ) : activeSearch.data?.entry?.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  {tc("noResults")}
                </p>
              ) : (
                <div className="space-y-3">
                  {activeSearch.data?.entry?.map((entry, idx) => (
                    <div
                      key={entry.fullUrl ?? idx}
                      className="rounded-lg border border-border bg-muted/10 p-3"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <FileJson className="h-4 w-4 text-primary" />
                        <span className="text-xs font-medium text-primary">
                          {entry.fullUrl ?? `Entry ${idx + 1}`}
                        </span>
                      </div>
                      <pre className="max-h-48 overflow-auto rounded-lg bg-background p-3 text-xs text-muted-foreground">
                        {JSON.stringify(entry.resource, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
