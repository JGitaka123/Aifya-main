"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  ArrowLeft,
  Wallet,
  Receipt,
  Banknote,
  Shield,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  FileDown,
  Lock,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  usePayrollRun,
  useApprovePayrollRun,
  useRecalculatePayrollRun,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { PayslipPreview } from "@/components/payroll/PayslipPreview";
import { formatKES, formatDate } from "@/lib/utils";
import { centsToUnits, sumCents } from "@/lib/money";

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

/**
 * Payroll Run detail — header, summary cards, line items table, approve/recalculate.
 *
 * @returns Run detail page
 */
export default function PayrollRunDetailPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const params = useParams();
  const runId = params.runId as string;
  const { user } = useAuth();

  const { data: run, isLoading } = usePayrollRun(runId);
  const approve = useApprovePayrollRun(runId);
  const recalc = useRecalculatePayrollRun(runId);

  const [confirmApprove, setConfirmApprove] = useState(false);
  const [previewEmployee, setPreviewEmployee] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const isFinanceAdmin = true;

  const totalStatutory = centsToUnits(
    sumCents([run?.total_nssf, run?.total_shif, run?.total_hl]),
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("runNotFound")}
      </div>
    );
  }

  const handleApprove = () => {
    if (!user) return;
    approve.mutate(
      { approved_by: user.id },
      { onSuccess: () => setConfirmApprove(false) },
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <div className="flex items-center gap-4">
        <Link
          href="/hr/payroll/runs"
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {MONTHS_EN[run.month - 1]} {run.year}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("runDate")}: {run.run_date ? formatDate(run.run_date) : "—"}
          </p>
        </div>
        <PayrollStatusBadge status={run.status} />
      </div>

      <PageHeader
        title=""
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("payroll"), href: "/hr/payroll" },
          { label: t("runs"), href: "/hr/payroll/runs" },
          { label: `${MONTHS_EN[run.month - 1]} ${run.year}` },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            {run.status === "draft" && (
              <>
                <button
                  type="button"
                  onClick={() => recalc.mutate()}
                  disabled={recalc.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50 disabled:opacity-50"
                >
                  <RefreshCw className="h-4 w-4" />
                  {t("recalculate")}
                </button>
                {isFinanceAdmin && (
                  <button
                    type="button"
                    onClick={() => setConfirmApprove(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    {t("approve")}
                  </button>
                )}
              </>
            )}
          </div>
        }
      />

      {/* Status alerts */}
      {run.status === "draft" && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <AlertTriangle className="h-5 w-5 text-amber-700 dark:text-amber-400" />
          <p className="text-sm text-amber-900 dark:text-amber-200">
            {t("draftWarning")}
          </p>
        </div>
      )}
      {run.status === "posted" && run.gl_transaction_id && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/30">
          <CheckCircle2 className="h-5 w-5 text-emerald-700 dark:text-emerald-400" />
          <p className="text-sm text-emerald-900 dark:text-emerald-200">
            {t("postedToGL", { txId: run.gl_transaction_id })}
          </p>
        </div>
      )}
      {run.status === "locked" && (
        <div className="flex items-center gap-3 rounded-xl border border-purple-200 bg-purple-50 p-4 dark:border-purple-900 dark:bg-purple-950/30">
          <Lock className="h-5 w-5 text-purple-700 dark:text-purple-400" />
          <p className="text-sm text-purple-900 dark:text-purple-200">
            {t("lockedNotice")}
          </p>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={Wallet}
          label={t("totalGross")}
          value={formatKES(run.total_gross * 100)}
          color="emerald"
        />
        <StatCard
          icon={Receipt}
          label={t("totalPaye")}
          value={formatKES(run.total_paye * 100)}
          color="orange"
        />
        <StatCard
          icon={Shield}
          label={t("totalStatutory")}
          value={formatKES(totalStatutory * 100)}
          subtitle={t("nssfShifHl")}
          color="blue"
        />
        <StatCard
          icon={Banknote}
          label={t("totalNet")}
          value={formatKES(run.total_net * 100)}
          color="green"
        />
      </div>

      {/* Line items */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">
            {t("lineItems")}{" "}
            <span className="ml-1 text-muted-foreground">
              ({run.line_items?.length ?? 0})
            </span>
          </h2>
        </div>
        {!run.line_items?.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noLineItems")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("staffId")}</th>
                  <th className="px-4 py-3">{t("department")}</th>
                  <th className="px-4 py-3 text-right">{t("gross")}</th>
                  <th className="px-4 py-3 text-right">{t("paye")}</th>
                  <th className="px-4 py-3 text-right">{t("nssf")}</th>
                  <th className="px-4 py-3 text-right">{t("shif")}</th>
                  <th className="px-4 py-3 text-right">{t("hl")}</th>
                  <th className="px-4 py-3 text-right">{t("net")}</th>
                  <th className="px-4 py-3 text-right">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {run.line_items.map((item) => (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      {item.employee_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {item.staff_id ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {item.department_name ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(item.gross_salary * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(item.paye * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(item.nssf_employee * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(item.shif * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(item.housing_levy * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-semibold text-foreground">
                      {formatKES(item.net_salary * 100)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={run.status === "draft"}
                        onClick={() =>
                          setPreviewEmployee({
                            id: item.employee_id,
                            name: item.employee_name,
                          })
                        }
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline disabled:cursor-not-allowed disabled:text-muted-foreground disabled:hover:no-underline"
                      >
                        <FileDown className="h-3.5 w-3.5" />
                        {t("payslip")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Approve confirm dialog */}
      {confirmApprove && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setConfirmApprove(false)}
        >
          <div
            className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-2 text-lg font-semibold text-foreground">
              {t("confirmApproveTitle")}
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              {t("confirmApproveBody", {
                month: MONTHS_EN[run.month - 1],
                year: run.year,
              })}
            </p>
            <dl className="mb-6 space-y-2 rounded-lg bg-muted/30 p-4 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("totalGross")}</dt>
                <dd className="font-medium tabular-nums">
                  {formatKES(run.total_gross * 100)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("totalPaye")}</dt>
                <dd className="font-medium tabular-nums">
                  {formatKES(run.total_paye * 100)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">
                  {t("totalStatutory")}
                </dt>
                <dd className="font-medium tabular-nums">
                  {formatKES(totalStatutory * 100)}
                </dd>
              </div>
              <div className="flex justify-between border-t border-border pt-2">
                <dt className="font-semibold">{t("totalNet")}</dt>
                <dd className="font-semibold tabular-nums">
                  {formatKES(run.total_net * 100)}
                </dd>
              </div>
            </dl>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmApprove(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={approve.isPending}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {t("approve")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payslip preview */}
      {previewEmployee && (
        <PayslipPreview
          runId={runId}
          employeeId={previewEmployee.id}
          employeeName={previewEmployee.name}
          onClose={() => setPreviewEmployee(null)}
        />
      )}
    </div>
  );
}
