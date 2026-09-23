"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, FileDown } from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useEmployee,
  useEmployeePayslips,
} from "@/hooks/usePayroll";
import { PayslipPreview } from "@/components/payroll/PayslipPreview";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { formatKES } from "@/lib/utils";

const MONTHS_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Employee self-service payslips page — mobile-friendly list with download.
 *
 * @returns Self-service payslips page
 */
export default function EmployeePayslipsPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const params = useParams();
  const employeeId = params.employeeId as string;

  const { data: employee } = useEmployee(employeeId);
  const { data: payslips, isLoading } = useEmployeePayslips(employeeId);

  const [previewRunId, setPreviewRunId] = useState<string | null>(null);

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-4 p-4 md:p-6 lg:p-8">
      <div className="flex items-center gap-3">
        <Link
          href={`/hr/employees/${employeeId}`}
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-foreground sm:text-2xl">
            {t("myPayslips")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {employee?.full_name ?? ""}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          {tc("loading")}
        </div>
      ) : !payslips?.length ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          {t("noPayslips")}
        </div>
      ) : (
        <ul className="space-y-3">
          {payslips.map((p) => (
            <li
              key={p.id}
              className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
            >
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="text-base font-semibold text-foreground">
                    {MONTHS_EN[p.month - 1]} {p.year}
                  </p>
                  <div className="mt-1">
                    <PayrollStatusBadge status={p.status} />
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">
                    {t("gross")}
                  </p>
                  <p className="text-base font-medium tabular-nums text-foreground">
                    {formatKES(p.gross_salary * 100)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">{t("net")}</p>
                  <p className="text-base font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                    {formatKES(p.net_salary * 100)}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={p.status === "draft"}
                  onClick={() => setPreviewRunId(p.run_id)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <FileDown className="h-4 w-4" />
                  {t("downloadPdf")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {previewRunId && employee && (
        <PayslipPreview
          runId={previewRunId}
          employeeId={employeeId}
          employeeName={employee.full_name}
          onClose={() => setPreviewRunId(null)}
        />
      )}
    </div>
  );
}
