"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  Ambulance,
  Clock,
  Heart,
  Plus,
  ShieldAlert,
  Siren,
  Stethoscope,
  UserCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useEmergencySummary,
  useEmergencyQueue,
  useDoctorsOnDuty,
} from "@/hooks/useEmergency";
import { DutyRosterManager } from "@/components/emergency/DutyRosterManager";
import { useAuth } from "@/components/providers/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FilterChips } from "@/components/ui/TabGroup";
import { DataTable } from "@/components/ui/DataTable";
import { Avatar } from "@/components/ui/Avatar";

/** Maps triage color to StatusBadge solid variant. */
const TRIAGE_VARIANT: Record<string, "red-solid" | "orange-solid" | "yellow-solid" | "green-solid" | "blue-solid"> = {
  red: "red-solid",
  orange: "orange-solid",
  yellow: "yellow-solid",
  green: "green-solid",
  blue: "blue-solid",
};

/** Maps queue status to StatusBadge variant. */
const STATUS_VARIANT: Record<string, "slate" | "info" | "purple" | "warning" | "indigo" | "success" | "cyan" | "default" | "error"> = {
  arrived: "slate",
  triaged: "info",
  in_treatment: "purple",
  observation: "warning",
  admitted: "indigo",
  discharged: "success",
  transferred: "cyan",
  deceased: "default",
  left_against_advice: "error",
};

/** Maps arrival mode key to display label translation key. */
const ARRIVAL_MODE_KEYS: Record<string, string> = {
  walk_in: "mode.walk_in",
  ambulance: "mode.ambulance",
  referral: "mode.referral",
  police: "mode.police",
  other: "mode.other",
};

/**
 * Emergency department dashboard page.
 * Displays summary stats, status filters, and the live patient queue.
 *
 * @returns Emergency page component
 */
export default function EmergencyPage() {
  const t = useTranslations("emergency");
  const { user } = useAuth();
  const canManage =
    !!user &&
    user.roles.some((role) => role === "admin" || role === "facility_admin");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: summary, isLoading: summaryLoading } = useEmergencySummary();
  const { data: queue, isLoading: queueLoading } = useEmergencyQueue(statusFilter || undefined);
  const { data: onDutyDoctors, isLoading: onDutyLoading } = useDoctorsOnDuty();

  const summaryCards: {
    label: string;
    value: number;
    icon: React.ComponentType<{ className?: string }>;
    color: "blue" | "amber" | "purple" | "cyan" | "red" | "orange" | "green" | "rose";
  }[] = [
    { label: t("totalToday"), value: summary?.total_today ?? 0, icon: Activity, color: "blue" },
    { label: t("awaitingTriage"), value: summary?.awaiting_triage ?? 0, icon: Clock, color: "amber" },
    { label: t("inTreatment"), value: summary?.in_treatment ?? 0, icon: Heart, color: "purple" },
    { label: t("inObservation"), value: summary?.in_observation ?? 0, icon: UserCheck, color: "cyan" },
    { label: t("criticalRed"), value: summary?.critical_red ?? 0, icon: Siren, color: "red" },
    { label: t("urgentOrange"), value: summary?.urgent_orange ?? 0, icon: AlertTriangle, color: "orange" },
    { label: t("dischargedToday"), value: summary?.discharged_today ?? 0, icon: ShieldAlert, color: "green" },
    { label: t("traumaCases"), value: summary?.trauma_cases ?? 0, icon: Ambulance, color: "rose" },
  ];

  const statusOptions = [
    { value: "", label: t("allActive") },
    { value: "arrived", label: t("status.arrived") },
    { value: "triaged", label: t("status.triaged") },
    { value: "in_treatment", label: t("status.in_treatment") },
    { value: "observation", label: t("status.observation") },
    { value: "admitted", label: t("status.admitted") },
    { value: "discharged", label: t("status.discharged") },
  ];

  const tableHeaders = [
    { label: t("visitNumber") },
    { label: t("patient") },
    { label: t("arrival") },
    { label: t("chiefComplaint"), className: "max-w-[200px]" },
    { label: t("triage") },
    { label: t("areaLabel") },
    { label: t("doctor") },
    { label: t("statusLabel") },
    { label: t("flags") },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={Siren}
        title={t("title")}
        subtitle={t("subtitle")}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <Link
            href="/emergency/register"
            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-700"
          >
            <Plus className="h-4 w-4" />
            {t("registerVisit")}
          </Link>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-4 xl:grid-cols-8">
        {summaryLoading ? (
          <StatCardSkeleton count={8} />
        ) : (
          summaryCards.map((card) => (
            <StatCard
              key={card.label}
              icon={card.icon}
              label={card.label}
              value={card.value}
              color={card.color}
            />
          ))
        )}
      </div>

      {/* Doctors on Duty */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Stethoscope className="h-4 w-4 text-red-600 dark:text-red-400" />
            {t("doctorsOnDuty")}
            {onDutyDoctors && onDutyDoctors.length > 0 && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                {onDutyDoctors.length}
              </span>
            )}
          </h2>
        </div>
        {onDutyLoading ? (
          <div className="py-3 text-sm text-muted-foreground">{t("loading")}</div>
        ) : !onDutyDoctors || onDutyDoctors.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noDoctorsOnDuty")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {onDutyDoctors.map((doc) => (
              <span
                key={doc.id}
                className="inline-flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-300"
              >
                <Stethoscope className="h-3.5 w-3.5" />
                {doc.title ? doc.title + " " : ""}
                {doc.first_name} {doc.last_name}
                {doc.specialization ? "\u00B7 " + doc.specialization : ""}
                {doc.shift_name ? (
                  <span className="ml-1 rounded-sm bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-700 dark:bg-green-900 dark:text-green-200">
                    {doc.shift_name}
                  </span>
                ) : null}
              </span>
            ))}
          </div>
        )}
      </div>

      {canManage && <DutyRosterManager />}

      {/* Status Filter */}
      <FilterChips
        options={statusOptions}
        selected={statusFilter}
        onSelect={setStatusFilter}
        accentColor="red"
      />

      {/* Queue Table */}
      <DataTable
        headers={tableHeaders}
        isLoading={queueLoading}
       isEmpty={!queue?.items?.length}
          emptyMessage={t("emptyQueue")}
          totalCount={queue?.items?.length}
      >
        {queue?.items.map((item) => (
          <tr
            key={item.id}
            className="bg-card transition-colors hover:bg-muted/50"
          >
            <td className="px-4 py-3">
              <Link
                href={`/emergency/${item.id}`}
                className="font-medium text-red-600 hover:underline dark:text-red-400"
              >
                {item.visit_number}
              </Link>
            </td>
            <td className="px-4 py-3">
              <div className="flex items-center gap-2.5">
                <Avatar name={item.patient_name || "?"} size="sm" />
                <div>
                  <div className="font-medium text-foreground">
                    {item.patient_name || "\u2014"}
                  </div>
                  {item.patient_mrn && (
                    <div className="text-xs text-muted-foreground">{item.patient_mrn}</div>
                  )}
                </div>
              </div>
            </td>
            <td className="whitespace-nowrap px-4 py-3">
              <div className="flex flex-col gap-1">
                <StatusBadge variant="slate" size="xs">
                  {t(ARRIVAL_MODE_KEYS[item.arrival_mode] || "mode.other")}
                </StatusBadge>
                <span className="text-xs text-muted-foreground">
                  {new Date(item.arrival_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </td>
            <td className="max-w-[200px] truncate px-4 py-3 text-muted-foreground">
              {item.chief_complaint}
            </td>
            <td className="px-4 py-3">
              <div className="flex items-center gap-1.5">
                {item.triage_color && (
                  <StatusBadge
                    variant={TRIAGE_VARIANT[item.triage_color] || "default"}
                    size="xs"
                  >
                    {item.triage_category}
                  </StatusBadge>
                )}
                {item.triage_score != null && (
                  <span className="text-xs text-muted-foreground">({item.triage_score})</span>
                )}
              </div>
            </td>
            <td className="px-4 py-3 text-xs text-muted-foreground">
              {item.treatment_area ? t(`area.${item.treatment_area}`) : "\u2014"}
            </td>
            <td className="px-4 py-3 text-sm text-foreground">
              {item.assigned_doctor_name || "\u2014"}
            </td>
            <td className="px-4 py-3">
              <StatusBadge
                variant={STATUS_VARIANT[item.status] || "default"}
                size="xs"
                dot
              >
                {t(`status.${item.status}`)}
              </StatusBadge>
            </td>
            <td className="px-4 py-3">
              <div className="flex gap-1">
                {item.referral_id && (
                  <StatusBadge variant="info" size="xs">
                    {t("referredIn")}
                  </StatusBadge>
                )}
                {item.is_trauma && (
                  <StatusBadge variant="error" size="xs">
                    {t("trauma")}
                  </StatusBadge>
                )}
                {item.is_resuscitation && (
                  <StatusBadge variant="rose" size="xs">
                    {t("resus")}
                  </StatusBadge>
                )}
              </div>
            </td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}
