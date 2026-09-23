"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Receipt, Search, X } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { ConsultationFeePanel } from "@/components/billing/ConsultationFeePanel";
import { ServiceChargeRow } from "@/components/billing/ServiceChargeRow";
import { useInvoiceList, usePatientServiceCharges } from "@/hooks/useBilling";
import { usePatientSearch } from "@/hooks/usePatients";
import { formatKES } from "@/lib/utils";
import type { Patient, ServiceCharge } from "@aifya/shared";

/** Invoice states that can no longer take money. */
const CLOSED_INVOICE_STATUSES: readonly string[] = ["cancelled", "waived"];

interface PatientConsultationFeesProps {
  patientId: string;
}

/**
 * Consultation fees the patient still owes before seeing a clinician.
 *
 * The consultation fee is raised on the visit's own invoice when the patient
 * is routed at reception, so it is not one of the ordered services the point
 * of sale lists. It is found here through those open invoices, and every visit
 * gets its own panel so the desk can correct the amount, take the money and
 * print the receipt the patient shows the clinician.
 *
 * @param props - Patient being served
 * @returns Consultation fee panels, or nothing when the patient owes none
 */
function PatientConsultationFees({ patientId }: PatientConsultationFeesProps) {
  const t = useTranslations("billing");
  const { data } = useInvoiceList(undefined, 1, 100, patientId);

  const encounterIds = useMemo(() => {
    const ids = new Set<string>();
    for (const invoice of data?.items ?? []) {
      if (invoice.balance_cents <= 0) continue;
      if (CLOSED_INVOICE_STATUSES.includes(invoice.status)) continue;
      ids.add(invoice.encounter_id);
    }
    return Array.from(ids);
  }, [data]);

  if (encounterIds.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-foreground">
        {t("pos.consultationFees")}
      </h2>
      {encounterIds.map((encounterId) => (
        <ConsultationFeePanel key={encounterId} encounterId={encounterId} />
      ))}
    </div>
  );
}

/**
 * Front-desk point of sale for ordered services.
 *
 * A patient walks up with a lab slip, an imaging request or a prescription.
 * The cashier finds the patient, sees every unpaid ordered service, takes the
 * money and hands over the service receipt that the lab, x-ray or pharmacy
 * desk asks for before releasing the service.
 *
 * @returns Point-of-sale page
 */
export default function PointOfSalePage() {
  const t = useTranslations("billing");
  const tc = useTranslations("common");

  const [query, setQuery] = useState("");
  const [patient, setPatient] = useState<Patient | null>(null);

  const { data: results, isFetching } = usePatientSearch(
    query || undefined,
    1,
    8,
  );
  const {
    data: chargeData,
    isLoading,
    refetch,
  } = usePatientServiceCharges(patient?.id ?? "");

  const charges: ServiceCharge[] = chargeData?.items ?? [];

  // Group the outstanding requests by visit, so a patient paying for two
  // visits sees them separately. Depends on the query result, not on the
  // `?? []` fallback, which is a fresh array on every render.
  const visits = useMemo(() => {
    const groups = new Map<string, ServiceCharge[]>();
    for (const charge of chargeData?.items ?? []) {
      const bucket = groups.get(charge.encounter_id);
      if (bucket) {
        bucket.push(charge);
      } else {
        groups.set(charge.encounter_id, [charge]);
      }
    }
    return Array.from(groups.entries());
  }, [chargeData]);

  const candidates = patient ? [] : (results?.items ?? []);

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={Receipt}
        title={t("pos.title")}
        subtitle={t("pos.description")}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          { label: t("pos.title") },
        ]}
      />

      {/* Patient search */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <label
          htmlFor="pos-patient-search"
          className="text-sm font-medium text-foreground"
        >
          {t("pos.searchLabel")}
        </label>
        <div className="mt-2 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              id="pos-patient-search"
              value={patient ? patient.first_name + " " + patient.last_name : query}
              onChange={(event) => {
                setPatient(null);
                setQuery(event.target.value);
              }}
              placeholder={t("pos.searchPlaceholder")}
              className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm text-foreground shadow-sm"
            />
          </div>
          {patient && (
            <button
              type="button"
              aria-label={tc("close")}
              onClick={() => {
                setPatient(null);
                setQuery("");
              }}
              className="rounded-lg border border-border bg-card p-2 text-muted-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {isFetching && query.length > 0 && !patient && (
          <p className="mt-2 text-xs text-muted-foreground">
            {t("pos.searching")}
          </p>
        )}

        {candidates.length > 0 && (
          <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
            {candidates.map((candidate) => (
              <li key={candidate.id}>
                <button
                  type="button"
                  onClick={() => {
                    setPatient(candidate);
                    setQuery("");
                  }}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted"
                >
                  <Avatar
                    name={candidate.first_name + " " + candidate.last_name}
                    size="sm"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-foreground">
                      {candidate.first_name + " " + candidate.last_name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {candidate.mrn} &middot; {candidate.phone_number}
                    </span>
                  </span>
                  <span className="text-xs font-semibold text-primary">
                    {tc("select")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {query.length > 1 && !isFetching && candidates.length === 0 && !patient && (
          <p className="mt-2 text-sm text-muted-foreground">
            {tc("noResults")}
          </p>
        )}
      </div>

      {/* Outstanding services */}
      {!patient ? (
        <EmptyState
          icon={Receipt}
          title={t("pos.noPatient")}
          description={t("pos.noPatientHint")}
        />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-3">
              <Avatar
                name={patient.first_name + " " + patient.last_name}
                size="lg"
              />
              <div>
                <p className="font-semibold text-foreground">
                  {patient.first_name + " " + patient.last_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {patient.mrn} &middot; {patient.phone_number}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">
                {t("pos.servicesOutstanding")}
              </p>
              <p className="text-xl font-bold text-foreground">
                {formatKES(chargeData?.total_outstanding_cents ?? 0)}
              </p>
            </div>
          </div>

          {isLoading ? (
            <PageSkeleton />
          ) : (
            <>
              <PatientConsultationFees patientId={patient.id} />

              {charges.length === 0 ? (
                <EmptyState
                  icon={Receipt}
                  title={t("pos.noCharges")}
                  description={t("pos.noChargesHint")}
                />
              ) : (
                visits.map(([encounterId, visitCharges]) => (
                  <div key={encounterId} className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h2 className="text-sm font-semibold text-foreground">
                        {t("pos.encounter")}
                      </h2>
                      <span className="text-xs text-muted-foreground">
                        {formatKES(
                          visitCharges.reduce(
                            (total, charge) => total + charge.balance_cents,
                            0,
                          ),
                        )}
                      </span>
                    </div>
                    {visitCharges.map((charge) => (
                      <ServiceChargeRow
                        key={charge.reference_id}
                        charge={charge}
                        onCollected={() => {
                          void refetch();
                        }}
                      />
                    ))}
                  </div>
                ))
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}