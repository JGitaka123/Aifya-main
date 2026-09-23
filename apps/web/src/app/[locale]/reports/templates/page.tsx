"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, Play } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useReportTemplates, useGenerateReport } from "@/hooks/useReports";
import { cn } from "@/lib/utils";

/** Category badge styling. */
const CATEGORY_STYLES: Record<string, string> = {
  operational: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  clinical: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  financial: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  compliance: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  moh: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/**
 * Report Templates page — list and run report templates.
 *
 * @returns Report templates page
 */
export default function ReportTemplatesPage() {
  const t = useTranslations("reports");
  const tc = useTranslations("common");

  const [categoryFilter, setCategoryFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");

  const { data: templates, isLoading } = useReportTemplates(
    categoryFilter || undefined,
    departmentFilter || undefined
  );

  const generateMutation = useGenerateReport();

  // Generate form state
  const [generateTemplateId, setGenerateTemplateId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d.toISOString().split("T")[0] ?? "";
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split("T")[0] ?? "");

  /**
   * Handle report generation.
   *
   * @param templateId - Template UUID
   */
  async function handleGenerate(templateId: string) {
    await generateMutation.mutateAsync({
      template_id: templateId,
      date_from: dateFrom,
      date_to: dateTo,
    });
    setGenerateTemplateId(null);
  }

  return (
    <div className="space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">
          {t("reportTemplates")}
        </h1>
        <Link
          href="/reports"
          className="text-sm text-primary hover:underline"
        >
          {t("backToDashboard")}
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="">{t("allCategories")}</option>
          <option value="operational">{t("catOperational")}</option>
          <option value="clinical">{t("catClinical")}</option>
          <option value="financial">{t("catFinancial")}</option>
          <option value="compliance">{t("catCompliance")}</option>
          <option value="moh">{t("catMOH")}</option>
        </select>
        <select
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="">{t("allDepartments")}</option>
          <option value="opd">OPD</option>
          <option value="ipd">IPD</option>
          <option value="lab">{t("deptLab")}</option>
          <option value="pharmacy">{t("deptPharmacy")}</option>
          <option value="radiology">{t("deptRadiology")}</option>
          <option value="mch">MCH</option>
          <option value="billing">{t("deptBilling")}</option>
          <option value="appointments">{t("deptAppointments")}</option>
          <option value="all">{t("deptAll")}</option>
        </select>
      </div>

      {/* Templates Grid */}
      {isLoading ? (
        <div className="p-8 text-center text-muted-foreground">
          {tc("loading")}
        </div>
      ) : !templates?.length ? (
        <div className="p-8 text-center text-muted-foreground">
          {t("noTemplates")}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((tmpl) => (
            <div
              key={tmpl.id}
              className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-muted-foreground/70" />
                  <h3 className="font-medium text-foreground">
                    {tmpl.name}
                  </h3>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    CATEGORY_STYLES[tmpl.category] ?? CATEGORY_STYLES.operational
                  )}
                >
                  {t(`cat_${tmpl.category}`)}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>{tmpl.code}</span>
                {tmpl.department && <span>&middot; {tmpl.department.toUpperCase()}</span>}
                {tmpl.moh_form_number && (
                  <span className="font-medium text-red-600 dark:text-red-400">
                    {tmpl.moh_form_number}
                  </span>
                )}
                {tmpl.reporting_period && <span>&middot; {tmpl.reporting_period}</span>}
              </div>

              {/* Quick generate */}
              {generateTemplateId === tmpl.id ? (
                <div className="mt-4 space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-muted-foreground">
                        {t("dateFrom")}
                      </label>
                      <input
                        type="date"
                        value={dateFrom}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className="w-full rounded border border-input bg-background px-2 py-1 text-sm text-foreground"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">
                        {t("dateTo")}
                      </label>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="w-full rounded border border-input bg-background px-2 py-1 text-sm text-foreground"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleGenerate(tmpl.id)}
                      disabled={generateMutation.isPending}
                      className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500"
                    >
                      {t("generate")}
                    </button>
                    <button
                      onClick={() => setGenerateTemplateId(null)}
                      className="rounded-lg border border-input px-3 py-1.5 text-sm text-foreground hover:bg-muted/50"
                    >
                      {tc("cancel")}
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setGenerateTemplateId(tmpl.id)}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80"
                >
                  <Play className="h-3.5 w-3.5" />
                  {t("runReport")}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
