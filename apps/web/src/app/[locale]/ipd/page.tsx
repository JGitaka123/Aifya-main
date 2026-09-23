"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  BedDouble,
  Users,
  Clock,
  Activity,
  AlertCircle,
  User,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useWardBoardSummary,
  useWards,
  useAdmissions,
} from "@/hooks/useIPD";
import { formatDateTime, elapsedDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { WardSetup } from "@/components/ipd/WardSetup";
import { StatCard } from "@/components/ui/StatCard";

/** Admission status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  admitted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  on_leave: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  discharged: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  deceased: "bg-muted text-muted-foreground",
};

/**
 * IPD Ward Board — dashboard showing ward occupancy and active admissions.
 * Auto-refreshes for real-time bed management.
 *
 * @returns IPD ward board page
 */
export default function IPDWardBoardPage() {
  const t = useTranslations("ipd");
  const tc = useTranslations("common");
  const [wardFilter, setWardFilter] = useState<string>("");

  const { data: summary } = useWardBoardSummary();
  const { data: wards } = useWards();
  const { data: admissions, isLoading } = useAdmissions(
    undefined,
    wardFilter || undefined
  );

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <BedDouble className="h-7 w-7 text-primary" />
          <h1 className="text-2xl font-bold text-foreground">{t("wardBoard")}</h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Ward filter */}
          <select
            value={wardFilter}
            onChange={(e) => setWardFilter(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          >
            <option value="">{t("filterAll")}</option>
            {wards?.map((ward) => (
              <option key={ward.id} value={ward.id}>
                {ward.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <StatCard
            icon={BedDouble}
            label={t("totalBeds")}
            value={summary.total_beds}
            color="primary"
          />
          <StatCard
            icon={Activity}
            label={t("availableBeds")}
            value={summary.available_beds}
            color="green"
            alert={summary.available_beds <= 5 ? t("lowBeds") : undefined}
          />
          <StatCard
            icon={User}
            label={t("occupiedBeds")}
            value={summary.occupied_beds}
            color="blue"
          />
          <StatCard
            icon={Users}
            label={t("activeAdmissions")}
            value={summary.active_admissions}
            color="primary"
          />
          <StatCard
            icon={AlertCircle}
            label={t("occupancyRate")}
            value={`${summary.occupancy_rate}%`}
            color="amber"
            alert={summary.occupancy_rate >= 90 ? t("highOccupancy") : undefined}
          />
        </div>
      )}

      {/* Ward cards */}
      {wards && wards.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 font-semibold text-foreground">{t("wards")}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {wards.map((ward) => {
              const occupancyPct =
                ward.total_beds > 0
                  ? Math.round((ward.occupied_beds / ward.total_beds) * 100)
                  : 0;
              return (
                <div
                  key={ward.id}
                  className="rounded-lg border border-border bg-card p-3 shadow-[var(--shadow-card)]"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-foreground">{ward.name}</span>
                    <span className="text-xs text-muted-foreground">{ward.code}</span>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="text-green-600 dark:text-green-400">
                      {ward.available_beds} {t("available")}
                    </span>
                    <span className="text-blue-600 dark:text-blue-400">
                      {ward.occupied_beds} {t("occupied")}
                    </span>
                  </div>
                  {/* Occupancy bar */}
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        occupancyPct >= 90
                          ? "bg-red-500"
                          : occupancyPct >= 70
                            ? "bg-amber-500"
                            : "bg-green-500"
                      )}
                      style={{ width: `${occupancyPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Admissions list */}
      <h2 className="mb-3 font-semibold text-foreground">{t("activeAdmissions")}</h2>
      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          {tc("loading")}
        </div>
      ) : !admissions?.items.length ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <BedDouble className="mb-3 h-12 w-12 opacity-40" />
          <p className="text-lg">{t("noAdmissions")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {admissions.items.map((adm) => (
            <Link
              key={adm.id}
              href={`/ipd/${adm.id}`}
              className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:shadow-[var(--shadow-card-hover)]"
            >
              {/* Bed icon */}
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                <BedDouble className="h-5 w-5" />
              </div>

              {/* Patient & admission info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-semibold text-foreground">
                    {adm.patient_name ?? "\u2014"}
                  </span>
                  {adm.patient_mrn && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {adm.patient_mrn}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                  <span className="font-mono">{adm.admission_number}</span>
                  {adm.ward_name && <span>• {adm.ward_name}</span>}
                  {adm.bed_number && (
                    <span>
                      • {t("bedNumber")}: {adm.bed_number}
                    </span>
                  )}
                </div>
                {adm.admission_diagnosis && (
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {adm.admission_diagnosis}
                  </p>
                )}
              </div>

              {/* Length of stay */}
              <LengthOfStayStat admittedAt={adm.admitted_at} />

              {/* Status badge */}
              <span
                className={cn(
                  "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                  STATUS_STYLES[adm.status] ?? STATUS_STYLES.admitted
                )}
              >
                {t(adm.status === "on_leave" ? "onLeave" : adm.status as "admitted" | "discharged")}
              </span>

              {/* Admitted time */}
              <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                <Clock className="h-3 w-3" />
                {formatDateTime(adm.admitted_at)}
              </div>
            </Link>
          ))}
        </div>
      )}
      <WardSetup />
    </div>
  );
}

function LengthOfStayStat({ admittedAt }: { admittedAt?: string | null }) {
  const t = useTranslations("ipd");
  const elapsed = elapsedDuration(admittedAt);
  if (!elapsed) return null;
  return (
    <div className="hidden flex-shrink-0 text-center sm:block">
      <div className="text-lg font-bold text-foreground">{elapsed.count}</div>
      <div className="text-xs text-muted-foreground">
        {t(elapsed.unitKey, { count: elapsed.count })}
      </div>
    </div>
  );
}
