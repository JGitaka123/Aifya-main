"use client";

import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  BedDouble,
  Baby,
  CalendarClock,
  FlaskConical,
  Pill,
  Siren,
  Stethoscope,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useAppointmentSummary } from "@/hooks/useAppointments";
import { useOPDQueue } from "@/hooks/useEncounters";
import { useLabWorklist } from "@/hooks/useLaboratory";
import { usePharmacyQueue, useStockAlerts } from "@/hooks/usePharmacy";
import { DrugStockBadge } from "@/components/pharmacy/DrugStockBadge";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { HomeHeader, QuickAction } from "@/components/home/shared";

/**
 * Panel wrapper with a title and "view all" link.
 *
 * @param title - Panel heading
 * @param href - Destination of the view-all link
 * @param viewAllLabel - Localized view-all label
 * @param children - Panel content
 * @returns Card panel
 */
function Panel({
  title,
  href,
  viewAllLabel,
  children,
}: {
  title: string;
  href: string;
  viewAllLabel: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <Link
          href={href}
          className="text-xs font-medium text-primary hover:underline"
        >
          {viewAllLabel}
        </Link>
      </div>
      {children}
    </div>
  );
}

/**
 * Front-office home: registration and appointment shortcuts plus
 * today's appointment load and the live OPD queue length.
 *
 * @param name - Signed-in user's display name
 * @returns Reception home screen
 */
export function ReceptionHome({ name }: { name: string | null | undefined }) {
  const t = useTranslations("home");
  const tn = useTranslations("nav");
  const { data: appts, isLoading: apptsLoading } = useAppointmentSummary();
  const { data: queue, isLoading: queueLoading } = useOPDQueue("waiting");

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-8 p-6 lg:p-8">
      <HomeHeader name={name} subtitle={t("receptionSubtitle")} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <QuickAction href="/patients/register" icon={Users} label={t("registerPatient")} color="bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" />
        <QuickAction href="/appointments/new" icon={CalendarClock} label={t("newAppointment")} color="bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400" />
        <QuickAction href="/patients" icon={Users} label={tn("patients")} color="bg-teal-50 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400" />
        <QuickAction href="/opd" icon={Stethoscope} label={t("opdQueue")} color="bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400" />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {apptsLoading || queueLoading ? (
          <StatCardSkeleton count={4} />
        ) : (
          <>
            <StatCard icon={CalendarClock} label={t("appointmentsToday")} value={appts?.total_today ?? 0} color="indigo" />
            <StatCard icon={Users} label={t("checkedIn")} value={appts?.checked_in ?? 0} color="green" />
            <StatCard icon={Stethoscope} label={t("waitingInQueue")} value={queue?.total ?? 0} color="orange" />
            <StatCard icon={CalendarClock} label={t("completedToday")} value={appts?.completed_today ?? 0} color="teal" />
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Clinician home: the live OPD queue with direct links into each
 * consultation, plus clinical module shortcuts.
 *
 * @param name - Signed-in user's display name
 * @returns Clinician home screen
 */
export function ClinicianHome({ name }: { name: string | null | undefined }) {
  const t = useTranslations("home");
  const tn = useTranslations("nav");
  const { data: queue, isLoading } = useOPDQueue();

  const items = queue?.items ?? [];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-8 p-6 lg:p-8">
      <HomeHeader name={name} subtitle={t("clinicianSubtitle")} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <QuickAction href="/opd" icon={Stethoscope} label={t("opdQueue")} color="bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400" />
        <QuickAction href="/emergency" icon={Siren} label={tn("emergency")} color="bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400" />
        <QuickAction href="/laboratory" icon={FlaskConical} label={tn("laboratory")} color="bg-teal-50 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400" />
        <QuickAction href="/ipd" icon={BedDouble} label={tn("ipd")} color="bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400" />
      </div>

      <Panel title={t("opdQueueTitle", { count: queue?.total ?? 0 })} href="/opd" viewAllLabel={t("viewAll")}>
        {isLoading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <StatCardSkeleton count={2} />
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon={Stethoscope} title={t("emptyQueueTitle")} description={t("emptyQueueDescription")} />
        ) : (
          <ul className="divide-y divide-border">
            {items.slice(0, 8).map((e) => (
              <li key={e.id}>
                <Link
                  href={`/opd/${e.id}`}
                  className="flex items-center justify-between gap-3 py-3 transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {e.patient_name ?? e.patient_id}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {e.chief_complaint ?? ""}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
                    #{e.queue_number ?? "—"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

/**
 * Pharmacy home: pending dispense queue and stock alerts.
 *
 * @param name - Signed-in user's display name
 * @returns Pharmacy home screen
 */
export function PharmacyHome({ name }: { name: string | null | undefined }) {
  const t = useTranslations("home");
  const tn = useTranslations("nav");
  const { data: queue, isLoading: queueLoading } = usePharmacyQueue();
  const { data: alerts, isLoading: alertsLoading } = useStockAlerts();

  const queueItems = queue?.items ?? [];
  const alertItems = alerts ?? [];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-8 p-6 lg:p-8">
      <HomeHeader name={name} subtitle={t("pharmacySubtitle")} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <QuickAction href="/pharmacy" icon={Pill} label={t("dispenseQueue")} color="bg-orange-50 text-orange-600 dark:bg-orange-950/50 dark:text-orange-400" />
        <QuickAction href="/pharmacy/inventory" icon={Pill} label={tn("inventory")} color="bg-teal-50 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400" />
        <QuickAction href="/patients" icon={Users} label={tn("patients")} color="bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" />
        <QuickAction href="/opd" icon={Stethoscope} label={t("opdQueue")} color="bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title={t("pendingDispense", { count: queue?.total ?? 0 })} href="/pharmacy" viewAllLabel={t("viewAll")}>
          {queueLoading ? (
            <StatCardSkeleton count={2} />
          ) : queueItems.length === 0 ? (
            <EmptyState icon={Pill} title={t("emptyDispenseTitle")} description={t("emptyDispenseDescription")} />
          ) : (
            <ul className="divide-y divide-border">
              {queueItems.slice(0, 8).map((p) => (
                <li key={p.prescription_id}>
                  <Link
                    href={`/pharmacy/dispense/${p.prescription_id}`}
                    className="flex items-center justify-between gap-3 py-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{p.drug_name}</p>
                      <p className="truncate text-xs text-muted-foreground">{p.patient_name ?? ""}</p>
                    </div>
                    <DrugStockBadge
                      className="shrink-0 text-right"
                      drugName={p.drug_name}
                      genericName={p.generic_name}
                      requiredQuantity={p.quantity}
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title={t("stockAlerts", { count: alertItems.length })} href="/pharmacy/inventory" viewAllLabel={t("viewAll")}>
          {alertsLoading ? (
            <StatCardSkeleton count={2} />
          ) : alertItems.length === 0 ? (
            <EmptyState icon={AlertTriangle} title={t("emptyAlertsTitle")} description={t("emptyAlertsDescription")} />
          ) : (
            <ul className="divide-y divide-border">
              {alertItems.slice(0, 8).map((a) => (
                <li key={`${a.item_id}-${a.alert_type}`} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{a.drug_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {t(`alert_${a.alert_type}`)}
                    </p>
                  </div>
                  <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
                    {a.current_quantity}/{a.reorder_level}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

/**
 * Laboratory home: worklist summary with direct links into orders.
 *
 * @param name - Signed-in user's display name
 * @returns Lab home screen
 */
export function LabHome({ name }: { name: string | null | undefined }) {
  const t = useTranslations("home");
  const tn = useTranslations("nav");
  const { data: worklist, isLoading } = useLabWorklist();

  const items = worklist?.items ?? [];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-8 p-6 lg:p-8">
      <HomeHeader name={name} subtitle={t("labSubtitle")} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <QuickAction href="/laboratory" icon={FlaskConical} label={t("labWorklist")} color="bg-teal-50 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400" />
        <QuickAction href="/patients" icon={Users} label={tn("patients")} color="bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" />
        <QuickAction href="/radiology" icon={Baby} label={tn("radiology")} color="bg-violet-50 text-violet-600 dark:bg-violet-950/50 dark:text-violet-400" />
        <QuickAction href="/opd" icon={Stethoscope} label={t("opdQueue")} color="bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400" />
      </div>

      <Panel title={t("labWorklistTitle", { count: worklist?.total ?? 0 })} href="/laboratory" viewAllLabel={t("viewAll")}>
        {isLoading ? (
          <StatCardSkeleton count={2} />
        ) : items.length === 0 ? (
          <EmptyState icon={FlaskConical} title={t("emptyWorklistTitle")} description={t("emptyWorklistDescription")} />
        ) : (
          <ul className="divide-y divide-border">
            {items.slice(0, 8).map((o) => (
              <li key={o.id}>
                <Link
                  href={`/laboratory/${o.id}`}
                  className="flex items-center justify-between gap-3 py-3 transition-colors hover:bg-muted/50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {o.patient_name ?? o.order_number}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {o.order_number} · {t("testCount", { count: o.test_count })}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {o.priority}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
