"use client";

import { useTranslations } from "next-intl";
import { X, Download } from "lucide-react";
import { usePayslipPDF } from "@/hooks/usePayroll";

/**
 * Modal that previews a payslip PDF inline using an object URL and iframe.
 *
 * @param runId - Payroll run UUID
 * @param employeeId - Employee UUID
 * @param employeeName - Employee display name
 * @param onClose - Callback to close the modal
 * @returns Modal payslip preview
 */
export function PayslipPreview({
  runId,
  employeeId,
  employeeName,
  onClose,
}: {
  runId: string;
  employeeId: string;
  employeeName: string;
  onClose: () => void;
}) {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const { objectUrl, isLoading, error } = usePayslipPDF(runId, employeeId);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-border bg-card shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {t("payslipFor", { name: employeeName })}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {objectUrl && (
              <a
                href={objectUrl}
                download={`payslip-${employeeName.replace(/\s+/g, "-")}.pdf`}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                <Download className="h-4 w-4" />
                {t("download")}
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              aria-label={tc("close")}
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center overflow-hidden bg-muted/20">
          {isLoading && (
            <div className="text-muted-foreground">{tc("loading")}</div>
          )}
          {error && (
            <div className="text-red-600 dark:text-red-400">
              {t("payslipError")}
            </div>
          )}
          {objectUrl && (
            <iframe
              src={objectUrl}
              title={t("payslipFor", { name: employeeName })}
              className="h-full w-full bg-white"
            />
          )}
        </div>
      </div>
    </div>
  );
}
