"use client";

import { useTranslations } from "next-intl";
import { Eye } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useGeneratedReports } from "@/hooks/useReports";
import { cn } from "@/lib/utils";

/** Status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  generating: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  expired: "bg-muted text-muted-foreground",
};

/**
 * Generated Reports list page — view previously generated reports.
 *
 * @returns Generated reports page
 */
export default function GeneratedReportsPage() {
  const t = useTranslations("reports");
  const tc = useTranslations("common");

  const { data: reports, isLoading } = useGeneratedReports();

  return (
    <div className="space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">
          {t("generatedReports")}
        </h1>
        <Link
          href="/reports"
          className="text-sm text-primary hover:underline"
        >
          {t("backToDashboard")}
        </Link>
      </div>

      {/* Reports Table */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !reports?.items.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noGeneratedReports")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("reportNumber")}</th>
                  <th className="px-4 py-3">{t("reportTitle")}</th>
                  <th className="px-4 py-3">{t("dateRange")}</th>
                  <th className="px-4 py-3">{t("rows")}</th>
                  <th className="px-4 py-3">{t("format")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3">{t("generatedAt")}</th>
                  <th className="px-4 py-3">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {reports.items.map((rpt) => (
                  <tr
                    key={rpt.id}
                    className="hover:bg-muted/50"
                  >
                    <td className="px-4 py-3 font-medium text-foreground">
                      {rpt.report_number}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {rpt.title}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {rpt.date_from} — {rpt.date_to}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {rpt.row_count}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium uppercase text-muted-foreground">
                        {rpt.format}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          STATUS_STYLES[rpt.status] ?? STATUS_STYLES.generating
                        )}
                      >
                        {t(`reportStatus_${rpt.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(rpt.generated_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/reports/generated/${rpt.id}`}
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        {t("view")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {reports && (
          <div className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
            {t("totalReports", { count: reports.total })}
          </div>
        )}
      </div>
    </div>
  );
}
