"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CalendarRange,
  Plus,
  Lock,
  X,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import {
  usePeriods,
  useCreatePeriod,
  useClosePeriod,
  useYearEndClose,
  type Period,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatDateTime } from "@/lib/utils";

const periodSchema = z.object({
  name: z.string().min(2),
  start_date: z.string().min(1),
  end_date: z.string().min(1),
  year_end: z.boolean().optional(),
});

type PeriodForm = z.infer<typeof periodSchema>;

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "error" | "info" | "purple"> = {
  open: "success",
  closed: "warning",
  locked: "error",
  year_end: "purple",
};

/**
 * Period management page — list periods, create, close, year-end close.
 *
 * @returns Periods page
 */
export default function PeriodsPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");
  const { data: periods, isLoading } = usePeriods();
  const createPeriod = useCreatePeriod();
  const closePeriod = useClosePeriod();
  const yearEndClose = useYearEndClose();

  const [showDialog, setShowDialog] = useState(false);
  const [closingId, setClosingId] = useState<string | null>(null);
  const [closeReason, setCloseReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors: formErrors },
  } = useForm<PeriodForm>({
    resolver: zodResolver(periodSchema),
  });

  const onSubmit = (form: PeriodForm) => {
    setError(null);
    createPeriod.mutate(form, {
      onSuccess: () => {
        setShowDialog(false);
        reset();
      },
      onError: (err) => setError(err.message),
    });
  };

  const handleClose = () => {
    if (!closingId || closeReason.trim().length < 5) return;
    setError(null);
    closePeriod.mutate(
      { id: closingId, reason: closeReason },
      {
        onSuccess: () => {
          setClosingId(null);
          setCloseReason("");
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  const handleYearEnd = (p: Period) => {
    if (!confirm(t("confirmYearEnd", { name: p.name }))) return;
    yearEndClose.mutate({ id: p.id });
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={CalendarRange}
        title={t("periods")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("periods") },
        ]}
        actions={
          <button
            onClick={() => setShowDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("createPeriod")}
          </button>
        }
      />

      <DataTable
        headers={[
          { label: t("name") },
          { label: t("start") },
          { label: t("end") },
          { label: t("status") },
          { label: t("closedBy") },
          { label: tc("actions"), className: "text-right" },
        ]}
        isLoading={isLoading}
        isEmpty={!isLoading && !(periods?.length ?? 0)}
        emptyMessage={t("noPeriods")}
      >
        {(periods ?? []).map((p) => (
          <tr key={p.id}>
            <td className="px-4 py-3 text-foreground">{p.name}</td>
            <td className="px-4 py-3 text-muted-foreground">{formatDate(p.start_date)}</td>
            <td className="px-4 py-3 text-muted-foreground">{formatDate(p.end_date)}</td>
            <td className="px-4 py-3">
              <StatusBadge variant={STATUS_VARIANT[p.status] ?? "default"}>
                {t(`periodStatus.${p.status}`)}
              </StatusBadge>
            </td>
            <td className="px-4 py-3 text-xs text-muted-foreground">
              {p.closed_by ?? "—"}
              {p.closed_at && (
                <span className="block">{formatDateTime(p.closed_at)}</span>
              )}
            </td>
            <td className="px-4 py-3 text-right">
              <div className="inline-flex items-center gap-2">
                {p.status === "open" && (
                  <button
                    onClick={() => setClosingId(p.id)}
                    className="inline-flex items-center gap-1 rounded-md border border-input px-2 py-1 text-xs text-foreground hover:bg-muted"
                  >
                    <Lock className="h-3 w-3" />
                    {t("close")}
                  </button>
                )}
                {p.year_end && p.status === "closed" && (
                  <button
                    onClick={() => handleYearEnd(p)}
                    className="inline-flex items-center gap-1 rounded-md border border-purple-400/40 px-2 py-1 text-xs text-purple-700 hover:bg-purple-50 dark:text-purple-400 dark:hover:bg-purple-950/30"
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    {t("yearEndClose")}
                  </button>
                )}
              </div>
            </td>
          </tr>
        ))}
      </DataTable>

      {/* Create dialog */}
      {showDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setShowDialog(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <h2 className="text-lg font-bold text-foreground">{t("createPeriod")}</h2>
              <button
                onClick={() => setShowDialog(false)}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <p>{error}</p>
              </div>
            )}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("name")} *
                </label>
                <input
                  {...register("name")}
                  placeholder="e.g. Q2 2026"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
                {formErrors.name && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.name.message}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("start")} *
                  </label>
                  <input
                    type="date"
                    {...register("start_date")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("end")} *
                  </label>
                  <input
                    type="date"
                    {...register("end_date")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input type="checkbox" {...register("year_end")} />
                {t("isYearEnd")}
              </label>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowDialog(false)}
                  className="rounded-md border border-input px-3 py-1.5 text-sm text-foreground hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={createPeriod.isPending}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {tc("save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Close period dialog */}
      {closingId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setClosingId(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-3 text-lg font-bold text-foreground">{t("closePeriod")}</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              {t("closeReasonHint")}
            </p>
            <textarea
              value={closeReason}
              onChange={(e) => setCloseReason(e.target.value)}
              rows={3}
              placeholder={t("closeReasonPlaceholder")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                onClick={() => setClosingId(null)}
                className="rounded-md border border-input px-3 py-1.5 text-sm text-foreground hover:bg-muted"
              >
                {tc("cancel")}
              </button>
              <button
                onClick={handleClose}
                disabled={closeReason.trim().length < 5 || closePeriod.isPending}
                className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {closePeriod.isPending ? tc("loading") : t("close")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
