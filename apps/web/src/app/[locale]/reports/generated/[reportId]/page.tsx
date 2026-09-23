"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useGeneratedReport } from "@/hooks/useReports";

/**
 * Generated Report Detail — displays full report data with summary.
 *
 * @returns Report detail page
 */
export default function GeneratedReportDetailPage() {
  const t = useTranslations("reports");
  const tc = useTranslations("common");
  const params = useParams();
  const reportId = params.reportId as string;

  const { data: report, isLoading } = useGeneratedReport(reportId);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("reportNotFound")}
      </div>
    );
  }

  const rows = (report.result_data as Record<string, unknown>)?.rows as
    | Record<string, unknown>[]
    | undefined;
  const summaryEntries = report.summary_data
    ? Object.entries(report.summary_data)
    : [];

  return (
    <div className="space-y-6 animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/reports/generated"
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {report.title}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {report.report_number} &middot; {report.date_from} — {report.date_to}
            &middot; {report.row_count} {t("rows")}
          </p>
        </div>
      </div>

      {/* Summary */}
      {summaryEntries.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("summary")}
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {summaryEntries.map(([key, val]) => (
              <div key={key}>
                <p className="text-2xl font-bold text-foreground">
                  {typeof val === "number" ? val.toLocaleString() : String(val)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Table */}
      {rows && rows.length > 0 && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  {Object.keys(rows[0] ?? {}).map((col) => (
                    <th key={col} className="px-4 py-3">
                      {col.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((row, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-muted/50"
                  >
                    {Object.values(row).map((val, colIdx) => (
                      <td
                        key={colIdx}
                        className="px-4 py-3 text-foreground"
                      >
                        {val == null ? "-" : String(val)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Non-tabular data */}
      {report.result_data && !rows && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("reportData")}
          </h2>
          <pre className="overflow-x-auto rounded-lg bg-muted/30 p-4 text-xs text-foreground">
            {JSON.stringify(report.result_data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
