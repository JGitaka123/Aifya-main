"use client";

import { useTranslations } from "next-intl";
import { Receipt } from "lucide-react";
import { useEncounterServiceCharges } from "@/hooks/useBilling";
import { ServiceChargeRow } from "@/components/billing/ServiceChargeRow";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatKES } from "@/lib/utils";

interface EncounterServiceChargesProps {
  encounterId: string;
}

/**
 * Point-of-sale list for a single visit.
 *
 * Shows what a doctor's orders still cost, so the receptionist can take the
 * money before the patient walks to the lab, the x-ray room or the pharmacy.
 *
 * @param props - Encounter to price
 * @returns Charge list with collection controls
 */
export function EncounterServiceCharges({
  encounterId,
}: EncounterServiceChargesProps) {
  const t = useTranslations("billing");
  const { data, isLoading, refetch } = useEncounterServiceCharges(encounterId);
  const charges = data?.items ?? [];

  if (isLoading) {
    return null;
  }

  if (charges.length === 0) {
    return (
      <EmptyState
        icon={Receipt}
        title={t("pos.noCharges")}
        description={t("pos.noChargesHint")}
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{t("pos.service")}</p>
        <p className="text-sm font-semibold text-foreground">
          {t("pos.totalOutstanding")}:{" "}
          {formatKES(data?.total_outstanding_cents ?? 0)}
        </p>
      </div>
      {charges.map((charge) => (
        <ServiceChargeRow
          key={charge.reference_id}
          charge={charge}
          onCollected={() => {
            void refetch();
          }}
        />
      ))}
    </div>
  );
}
