"use client";

import { useTranslations } from "next-intl";
import { Printer, Download } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Wrapper that styles a report for clean print output.
 * Provides Print and CSV export buttons in the header.
 *
 * @param title - Report title
 * @param subtitle - Optional subtitle (e.g. period range)
 * @param children - Report body
 * @param onExportCsv - Optional CSV export handler
 * @param className - Extra classes
 * @returns Printable report wrapper
 */
export function PrintableReport({
  title,
  subtitle,
  children,
  onExportCsv,
  className,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onExportCsv?: () => void;
  className?: string;
}) {
  const t = useTranslations("finance");

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] print:border-0 print:shadow-none",
        className,
      )}
    >
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-3 print:mb-6">
        <div>
          <h2 className="text-xl font-bold text-foreground print:text-2xl">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2 print:hidden">
          {onExportCsv && (
            <button
              type="button"
              onClick={onExportCsv}
              className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
            >
              <Download className="h-3.5 w-3.5" />
              {t("exportCsv")}
            </button>
          )}
          <button
            type="button"
            onClick={handlePrint}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
          >
            <Printer className="h-3.5 w-3.5" />
            {t("exportPdf")}
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="finance-print-body">{children}</div>
    </div>
  );
}

/**
 * Helper: trigger CSV download from rows of records.
 *
 * @param filename - Output filename
 * @param rows - Array of objects (keys become headers)
 */
export function downloadCsv(filename: string, rows: Record<string, unknown>[]): void {
  const first = rows[0];
  if (!first) return;
  const headers = Object.keys(first);
  const escape = (v: unknown): string => {
    const s = v == null ? "" : String(v);
    if (s.includes(",") || s.includes("\"") || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const csv = [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => escape(r[h])).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
