"use client";

import { useState, type ChangeEvent } from "react";
import { Upload, Download, FileSpreadsheet, CheckCircle2, AlertTriangle } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useRegisterPatient } from "@/hooks/usePatients";
import type { PatientCreate } from "@aifya/shared";
import {
  parsePatientCsv,
  patientImportTemplate,
} from "@/lib/patientBulkImport";
import type { PatientCreateFormData } from "@/lib/validations/patient";

/**
 * Bulk patient import (D11). Mirrors the pharmacy inventory bulk import:
 * download a template, upload/paste CSV, preview validated rows, and create
 * each via the existing single-patient API — reporting per-row errors. Reuses
 * `patientCreateSchema` so D7/D8 validation rules apply to every row.
 *
 * @returns Bulk patient import page
 */
export default function PatientImportPage() {
  const registerPatient = useRegisterPatient();
  const [rows, setRows] = useState<PatientCreateFormData[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [pasted, setPasted] = useState("");
  const [successCount, setSuccessCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const downloadTemplate = () => {
    const blob = new Blob([patientImportTemplate()], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "patient_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadCsv = (text: string) => {
    const { rows: parsed, errors: errs } = parsePatientCsv(text);
    setRows(parsed);
    setErrors(errs);
    setSuccessCount(0);
  };

  const handleFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => loadCsv(String(ev.target?.result ?? ""));
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    setLoading(true);
    let ok = 0;
    const errs = [...errors];
    for (const [index, row] of rows.entries()) {
      try {
        await registerPatient.mutateAsync(row as unknown as PatientCreate);
        ok++;
      } catch (error) {
        errs.push(
          `${row.first_name} ${row.last_name} (row ${index + 1}): ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
    }
    setSuccessCount(ok);
    setErrors(errs);
    setRows([]);
    setLoading(false);
  };

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Bulk Patient Import</h1>
        <Link
          href="/patients/register"
          className="text-sm font-medium text-primary hover:underline"
        >
          Single registration →
        </Link>
      </div>

      <div className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <p className="text-sm text-muted-foreground">
          Upload a CSV of patients. Download the template for the required
          columns. Each row is validated with the same rules as the
          registration form; invalid rows are listed and skipped.
        </p>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={downloadTemplate}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            <Download className="h-4 w-4" />
            Download template
          </button>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <Upload className="h-4 w-4" />
            Upload CSV
            <input type="file" accept=".csv" onChange={handleFile} className="hidden" />
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-muted-foreground">
            …or paste CSV
          </label>
          <textarea
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={4}
            placeholder="first_name,last_name,date_of_birth,gender,phone_number&#10;Grace,Achieng,1995-07-01,female,0701234567"
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs text-foreground dark:border-border dark:bg-background"
          />
          {pasted.trim() && (
            <button
              type="button"
              onClick={() => loadCsv(pasted)}
              className="mt-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
            >
              Parse pasted CSV
            </button>
          )}
        </div>

        {rows.length > 0 && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium text-green-800 dark:text-green-200">
              <FileSpreadsheet className="h-4 w-4" />
              {rows.length} valid row{rows.length === 1 ? "" : "s"} ready to import
            </p>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? "Importing…" : `Import ${rows.length} patients`}
            </button>
          </div>
        )}

        {successCount > 0 && (
          <p className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
            <CheckCircle2 className="h-4 w-4" />
            Imported {successCount} patient{successCount === 1 ? "" : "s"}.
          </p>
        )}

        {errors.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
              <AlertTriangle className="h-4 w-4" />
              {errors.length} row{errors.length === 1 ? "" : "s"} skipped
            </p>
            <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-300">
              {errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
