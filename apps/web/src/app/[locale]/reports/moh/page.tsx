"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  FileText,
  Download,
  CheckCircle2,
  Loader2,
  Calendar,
  Wifi,
  WifiOff,
} from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useMOHForms, useGenerateMOHReport, useAllMOHReports, useDHIS2Status } from "@/hooks/useDHIS2";
import type { MOHFormCode, MOHReport } from "@aifya/shared";

/**
 * MOH / DHIS2 Automated Reporting page.
 * Generate Kenya MOH forms and manage DHIS2 integration.
 *
 * @returns MOH reporting page component
 */
export default function MOHReportingPage() {
  const t = useTranslations("dhis2");

  const formsQuery = useMOHForms();
  const dhis2Status = useDHIS2Status();
  const generateReport = useGenerateMOHReport();

  // Date range defaults to previous month
  const now = new Date();
  const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastOfPrevMonth = new Date(firstOfMonth.getTime() - 86400000);
  const firstOfPrevMonth = new Date(lastOfPrevMonth.getFullYear(), lastOfPrevMonth.getMonth(), 1);

  const [dateFrom, setDateFrom] = useState(firstOfPrevMonth.toISOString().slice(0, 10));
  const [dateTo, setDateTo] = useState(lastOfPrevMonth.toISOString().slice(0, 10));
  const [fetchAll, setFetchAll] = useState(false);
  const [selectedReport, setSelectedReport] = useState<MOHReport | null>(null);

  const allReports = useAllMOHReports(dateFrom, dateTo, fetchAll);

  const forms = formsQuery.data ?? [];
  const connected = dhis2Status.data?.connected ?? false;

  const handleGenerateOne = (formCode: MOHFormCode) => {
    generateReport.mutate(
      { form_code: formCode, date_from: dateFrom, date_to: dateTo },
      { onSuccess: (data) => setSelectedReport(data) },
    );
  };

  const handleGenerateAll = () => {
    setFetchAll(true);
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        icon={FileText}
        actions={
          <button
            onClick={handleGenerateAll}
            disabled={allReports.isLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {allReports.isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {t("generateAll")}
          </button>
        }
      />

      {/* Status Bar */}
      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card p-4 shadow-sm">
        {/* DHIS2 Connection */}
        <div className="flex items-center gap-2">
          {connected ? (
            <Wifi className="h-4 w-4 text-green-500" />
          ) : (
            <WifiOff className="h-4 w-4 text-red-500" />
          )}
          <span className="text-sm">
            DHIS2: {dhis2Status.isLoading ? (
              <Skeleton className="inline-block h-4 w-20" />
            ) : (
              <StatusBadge variant={connected ? "success" : "danger"}>
                {connected ? t("connected") : t("notConnected")}
              </StatusBadge>
            )}
          </span>
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-2 ml-auto">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setFetchAll(false); }}
            className="rounded-lg border border-input bg-background px-2 py-1 text-sm"
          />
          <span className="text-muted-foreground">-</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setFetchAll(false); }}
            className="rounded-lg border border-input bg-background px-2 py-1 text-sm"
          />
        </div>
      </div>

      {/* MOH Forms Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {formsQuery.isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))
        ) : (
          forms.map((form) => {
            const allReport = allReports.data?.reports?.[form.code];
            const hasData = !!allReport;

            return (
              <div
                key={form.code}
                className="rounded-xl border border-border bg-card p-5 shadow-sm transition-colors hover:bg-muted/20"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground">{form.name}</h3>
                    <p className="text-xs text-muted-foreground">{form.title}</p>
                  </div>
                  {hasData && (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  )}
                </div>

                <div className="mb-3 text-xs text-muted-foreground">
                  <span className="rounded-md bg-muted px-2 py-0.5">{form.period}</span>
                </div>

                {hasData && allReport?.summary && (
                  <div className="mb-3 space-y-1 text-xs">
                    {Object.entries(allReport.summary).slice(0, 3).map(([key, val]) => (
                      <div key={key} className="flex justify-between">
                        <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
                        <span className="font-medium">{String(val)}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={() => handleGenerateOne(form.code)}
                    disabled={generateReport.isPending}
                    className="flex-1 rounded-lg border border-input px-3 py-1.5 text-xs transition-colors hover:bg-muted disabled:opacity-50"
                  >
                    {generateReport.isPending ? t("generating") : t("generate")}
                  </button>
                  {hasData && (
                    <button
                      onClick={() => setSelectedReport(allReport)}
                      className="rounded-lg border border-input px-3 py-1.5 text-xs transition-colors hover:bg-muted"
                    >
                      {t("view")}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Report Detail View */}
      {selectedReport && (
        <div className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <div>
              <h3 className="font-semibold text-foreground">{selectedReport.form} - {selectedReport.title}</h3>
              <span className="text-xs text-muted-foreground">
                {selectedReport.period.from} - {selectedReport.period.to}
              </span>
            </div>
            <button
              onClick={() => setSelectedReport(null)}
              className="rounded-lg border border-input px-3 py-1 text-xs transition-colors hover:bg-muted"
            >
              {t("close")}
            </button>
          </div>

          {/* Summary */}
          {selectedReport.summary && (
            <div className="border-b border-border bg-muted/10 px-5 py-3">
              <span className="mb-2 block text-xs font-medium text-muted-foreground">{t("summary")}</span>
              <div className="flex flex-wrap gap-4">
                {Object.entries(selectedReport.summary).map(([key, val]) => (
                  <div key={key}>
                    <span className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</span>
                    <p className="text-sm font-semibold">{String(val)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Indicators (MOH 711, 718) */}
          {selectedReport.indicators && (
            <div className="border-b border-border px-5 py-3">
              <span className="mb-2 block text-xs font-medium text-muted-foreground">{t("indicators")}</span>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {Object.entries(selectedReport.indicators).map(([key, val]) => (
                  <div key={key} className="rounded-lg border border-border bg-background p-3">
                    <span className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</span>
                    <p className="text-lg font-bold">{val}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rows Table (705A, 705B, 710, 713) */}
          {selectedReport.rows && selectedReport.rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    {Object.keys(selectedReport.rows[0] ?? {}).map((col) => (
                      <th key={col} className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        {col.replace(/_/g, " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {selectedReport.rows.map((row, i) => (
                    <tr key={i} className="border-b border-border transition-colors hover:bg-muted/10">
                      {Object.values(row).map((val, j) => (
                        <td key={j} className="px-3 py-2 text-xs">
                          {String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
