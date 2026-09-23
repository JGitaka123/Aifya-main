"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ListChecks, Plus, X } from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  usePayrollRuns,
  useCreatePayrollRun,
  type PayrollRunStatus,
} from "@/hooks/usePayroll";
import { PageHeader } from "@/components/ui/PageHeader";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { formatKES, formatDate } from "@/lib/utils";

const MONTHS_EN = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const STATUSES: PayrollRunStatus[] = ["draft", "approved", "posted", "locked"];

/**
 * Payroll runs list page — searchable, filterable, with new run modal.
 *
 * @returns Payroll runs list page
 */
export default function PayrollRunsListPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");

  const now = useMemo(() => new Date(), []);
  const [yearFilter, setYearFilter] = useState<number | undefined>(
    now.getFullYear(),
  );
  const [statusFilter, setStatusFilter] = useState<PayrollRunStatus | "">("");
  const [showNew, setShowNew] = useState(false);
  const [newMonth, setNewMonth] = useState(now.getMonth() + 1);
  const [newYear, setNewYear] = useState(now.getFullYear());

  const { data, isLoading } = usePayrollRuns({ year: yearFilter });
  const createRun = useCreatePayrollRun();

  const filtered = useMemo(() => {
    if (!data?.items) return [];
    let items = [...data.items];
    if (statusFilter) items = items.filter((r) => r.status === statusFilter);
    items.sort((a, b) =>
      b.year !== a.year ? b.year - a.year : b.month - a.month,
    );
    return items;
  }, [data, statusFilter]);

  const yearOptions = useMemo(() => {
    const out: number[] = [];
    for (let y = now.getFullYear(); y >= now.getFullYear() - 5; y -= 1) {
      out.push(y);
    }
    return out;
  }, [now]);

  const handleCreate = () => {
    createRun.mutate(
      { month: newMonth, year: newYear },
      {
        onSuccess: () => {
          setShowNew(false);
        },
      },
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={ListChecks}
        title={t("runsTitle")}
        subtitle={t("runsSubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("payroll"), href: "/hr/payroll" },
          { label: t("runs") },
        ]}
        actions={
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            {t("newRun")}
          </button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={yearFilter ?? ""}
          onChange={(e) =>
            setYearFilter(e.target.value ? Number(e.target.value) : undefined)
          }
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          <option value="">{t("allYears")}</option>
          {yearOptions.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value as PayrollRunStatus | "")
          }
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          <option value="">{t("allStatuses")}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`runStatus_${s}`)}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noRuns")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("period")}</th>
                  <th className="px-4 py-3">{t("runDate")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3 text-right">{t("totalGross")}</th>
                  <th className="px-4 py-3 text-right">{t("totalNet")}</th>
                  <th className="px-4 py-3">{t("approvedBy")}</th>
                  <th className="px-4 py-3 text-right">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((run) => (
                  <tr key={run.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {MONTHS_EN[run.month - 1]} {run.year}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(run.run_date)}
                    </td>
                    <td className="px-4 py-3">
                      <PayrollStatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(run.total_gross * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(run.total_net * 100)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {run.approved_by ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/hr/payroll/runs/${run.id}`}
                        className="text-xs font-medium text-primary hover:underline"
                      >
                        {tc("view")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New run modal */}
      {showNew && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowNew(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                {t("newRun")}
              </h2>
              <button
                type="button"
                onClick={() => setShowNew(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
                aria-label={tc("close")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("month")}
                </span>
                <select
                  value={newMonth}
                  onChange={(e) => setNewMonth(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                >
                  {MONTHS_EN.map((name, idx) => (
                    <option key={name} value={idx + 1}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("year")}
                </span>
                <select
                  value={newYear}
                  onChange={(e) => setNewYear(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                >
                  {yearOptions.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowNew(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={createRun.isPending}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {t("createDraft")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
