"use client";

import { useState } from "react";

interface ExportButtonProps {
  /** Data to export */
  data: Record<string, any>[];
  /** Filename without extension */
  filename: string;
  /** Column definitions: { key, label } */
  columns: { key: string; label: string }[];
  /** Button label */
  label?: string;
  /** Extra CSS classes */
  className?: string;
}

/**
 * Exports tabular data as CSV download.
 * Handles special characters, commas in values, and date formatting.
 */
export default function ExportButton({
  data,
  filename,
  columns,
  label = "Export CSV",
  className = "",
}: ExportButtonProps) {
  const [exporting, setExporting] = useState(false);

  const escapeCsvValue = (value: any): string => {
    if (value === null || value === undefined) return "";
    const str = String(value);
    // Wrap in quotes if contains comma, newline, or quote
    if (str.includes(",") || str.includes("\n") || str.includes('"')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const exportCsv = () => {
    setExporting(true);

    try {
      // Header row
      const header = columns.map((c) => escapeCsvValue(c.label)).join(",");

      // Data rows
      const rows = data.map((row) =>
        columns
          .map((col) => {
            let value = row[col.key];
            // Format dates
            if (value && typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) {
              try {
                value = new Date(value).toLocaleString();
              } catch {}
            }
            // Format objects/arrays as JSON
            if (typeof value === "object" && value !== null) {
              value = JSON.stringify(value);
            }
            return escapeCsvValue(value);
          })
          .join(",")
      );

      const csv = [header, ...rows].join("\n");

      // BOM for Excel compatibility
      const bom = "\uFEFF";
      const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  if (data.length === 0) return null;

  return (
    <button
      onClick={exportCsv}
      disabled={exporting}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-slate-300 rounded-md text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50 ${className}`}
      aria-label={`Export ${data.length} rows as CSV`}
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      {exporting ? "Exporting..." : label}
    </button>
  );
}
