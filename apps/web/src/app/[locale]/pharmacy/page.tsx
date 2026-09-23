"use client";

import { useTranslations } from "next-intl";
import {
  Pill,
  Clock,
  AlertTriangle,
  Package,
  ShieldCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { usePharmacyQueue, useStockAlerts } from "@/hooks/usePharmacy";
import { formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { DrugStockBadge } from "@/components/pharmacy/DrugStockBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";

/**
 * Pharmacy queue page -- shows pending prescriptions awaiting dispensing.
 * Auto-refreshes every 15 seconds. Shows stock alerts banner.
 *
 * @returns Pharmacy queue page
 */
export default function PharmacyQueuePage() {
  const t = useTranslations("pharmacy");

  const { data: queue, isLoading } = usePharmacyQueue();
  const { data: alerts } = useStockAlerts();

  const criticalAlerts = alerts?.filter(
    (a) => a.alert_type === "out_of_stock" || a.alert_type === "expired"
  );

  // Group queue items by patient
  const groupedByPatient = new Map<
    string,
    { name: string; mrn: string | null; items: NonNullable<typeof queue>["items"] }
  >();

  if (queue?.items) {
    for (const item of queue.items) {
      const key = item.patient_id;
      if (!groupedByPatient.has(key)) {
        groupedByPatient.set(key, {
          name: item.patient_name ?? "\u2014",
          mrn: item.patient_mrn,
          items: [],
        });
      }
      groupedByPatient.get(key)!.items.push(item);
    }
  }

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={Pill}
        title={t("queue")}
        badge={queue?.total}
        breadcrumbs={[{ label: t("queue") }]}
        actions={
          <Link
            href="/pharmacy/inventory"
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
          >
            <Package className="h-4 w-4" />
            {t("inventory")}
          </Link>
        }
      />

      {/* Critical alerts banner */}
      {criticalAlerts && criticalAlerts.length > 0 && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
          <div className="flex items-center gap-2 text-sm font-medium text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {t("stockAlerts")} ({criticalAlerts.length})
          </div>
          <div className="mt-1 flex flex-wrap gap-2">
            {criticalAlerts.slice(0, 5).map((alert) => (
              <StatusBadge
                key={`${alert.item_id}-${alert.alert_type}`}
                variant={alert.alert_type === "out_of_stock" ? "error" : "orange"}
                size="xs"
              >
                {alert.drug_name}: {t(alert.alert_type === "out_of_stock" ? "outOfStock" : "expired")}
              </StatusBadge>
            ))}
          </div>
        </div>
      )}

      {/* Queue */}
      {isLoading ? (
        <PageSkeleton />
      ) : groupedByPatient.size === 0 ? (
        <EmptyState icon={Pill} title={t("queueEmpty")} />
      ) : (
        <div className="space-y-4">
          {Array.from(groupedByPatient.entries()).map(([patientId, group]) => (
            <div
              key={patientId}
              className="rounded-lg border border-border bg-card shadow-[var(--shadow-card)]"
            >
              {/* Patient header */}
              <div className="flex items-center gap-3 border-b border-border px-4 py-3">
                <Avatar name={group.name} size="sm" />
                <span className="font-semibold text-foreground">
                  {group.name}
                </span>
                {group.mrn && (
                  <span className="font-mono text-xs text-muted-foreground">
                    {group.mrn}
                  </span>
                )}
                <StatusBadge variant="warning" size="xs">
                  {group.items.length} {group.items.length === 1 ? t("rxSymbol") : `${t("rxSymbol")}'s`}
                </StatusBadge>
              </div>

              {/* Prescription rows */}
              <div className="divide-y divide-border">
                {group.items.map((rx) => (
                  <Link
                    key={rx.prescription_id}
                    href={`/pharmacy/dispense/${rx.prescription_id}`}
                    className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/30"
                  >
                    <Pill className="h-4 w-4 flex-shrink-0 text-green-500" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium text-foreground">
                          {rx.drug_name}
                        </span>
                        {rx.is_keml && (
                          <StatusBadge variant="emerald" size="xs">
                            <ShieldCheck className="h-3 w-3" />
                            {t("keml")}
                          </StatusBadge>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {rx.dosage} — {rx.route} — {rx.frequency}
                        {rx.duration_days ? ` — ${rx.duration_days}d` : ""}
                        {rx.quantity ? ` — Qty: ${rx.quantity}` : ""}
                      </p>
                      <DrugStockBadge
                        className="mt-1"
                        drugName={rx.drug_name}
                        genericName={rx.generic_name}
                        requiredQuantity={rx.quantity}
                      />
                    </div>
                    <div className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                      <Clock className="h-3 w-3" />
                      {formatDateTime(rx.created_at)}
                    </div>
                    <StatusBadge
                      variant={rx.status === "partially_dispensed" ? "info" : "warning"}
                    >
                      {rx.status === "partially_dispensed" ? t("partiallyDispensed") : t("dispense")}
                    </StatusBadge>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
