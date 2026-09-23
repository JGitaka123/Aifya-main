"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Receipt,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useBillingSummary, useInvoiceList } from "@/hooks/useBilling";
import { formatKES, formatDateTime } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard, MiniStat } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";

/** Map invoice status to StatusBadge variant. */
const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "error" | "info" | "purple"> = {
  draft: "default",
  finalized: "warning",
  partially_paid: "info",
  paid: "success",
  cancelled: "error",
  waived: "purple",
};

/**
 * Billing dashboard page — summary stats and invoice list.
 * Auto-refreshes for real-time billing updates.
 *
 * @returns Billing dashboard page
 */
export default function BillingDashboardPage() {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const { data: summary } = useBillingSummary();
  const { data: invoices, isLoading } = useInvoiceList(
    statusFilter || undefined,
    page,
  );

  const statusOptions: { value: string; label: string }[] = [
    { value: "", label: t("filterAll") },
    { value: "draft", label: t("draft") },
    { value: "finalized", label: t("finalized") },
    { value: "partially_paid", label: t("partiallyPaid") },
    { value: "paid", label: t("paid") },
    { value: "waived", label: t("waived") },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={Receipt}
        title={t("dashboard")}
        breadcrumbs={[{ label: t("dashboard") }]}
        actions={
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        }
      />

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            icon={FileText}
            label={t("summaryTotalInvoices")}
            value={String(summary.total_invoices)}
            color="blue"
          />
          <StatCard
            icon={DollarSign}
            label={t("summaryTotalBilled")}
            value={formatKES(summary.total_billed_cents)}
            color="primary"
          />
          <StatCard
            icon={CheckCircle2}
            label={t("summaryTotalPaid")}
            value={formatKES(summary.total_paid_cents)}
            color="green"
          />
          <StatCard
            icon={AlertCircle}
            label={t("summaryOutstanding")}
            value={formatKES(summary.total_outstanding_cents)}
            color="red"
            alert={
              summary.total_outstanding_cents > 0
                ? formatKES(summary.total_outstanding_cents)
                : undefined
            }
          />
        </div>
      )}

      {/* Breakdown row */}
      {summary && (
        <div className="flex flex-wrap gap-3">
          <MiniStat label={t("summaryDrafts")} value={summary.draft_count} color="default" />
          <MiniStat label={t("summaryFinalized")} value={summary.finalized_count} color="amber" />
          <MiniStat label={t("summaryPartiallyPaid")} value={summary.partially_paid_count} color="blue" />
          <MiniStat label={t("summaryPaid")} value={summary.paid_count} color="green" />
        </div>
      )}

      {/* Invoice list */}
      {isLoading ? (
        <PageSkeleton />
      ) : !invoices?.items.length ? (
        <EmptyState icon={Receipt} title={t("noInvoices")} />
      ) : (
        <>
          <div className="space-y-3">
            {invoices.items.map((inv) => (
              <Link
                key={inv.id}
                href={`/billing/${inv.id}`}
                className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:shadow-[var(--shadow-card-hover)]"
              >
                {/* Patient avatar */}
                <Avatar name={inv.patient_name ?? "?"} size="md" />

                {/* Patient & invoice info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-semibold text-foreground">
                      {inv.patient_name ?? "\u2014"}
                    </span>
                    {inv.patient_mrn && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {inv.patient_mrn}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                    <span className="font-mono">{inv.invoice_number}</span>
                    <span>
                      {inv.item_count} {t("itemCount")}
                    </span>
                  </div>
                </div>

                {/* Amounts */}
                <div className="hidden flex-shrink-0 text-right sm:block">
                  <div className="font-semibold text-foreground">
                    {formatKES(inv.total_cents)}
                  </div>
                  {inv.balance_cents > 0 && (
                    <div className="text-xs text-amber-600 dark:text-amber-400">
                      {t("balance")}: {formatKES(inv.balance_cents)}
                    </div>
                  )}
                  {inv.paid_cents > 0 && inv.balance_cents > 0 && (
                    <div className="text-xs text-green-600 dark:text-green-400">
                      {t("paidAmount")}: {formatKES(inv.paid_cents)}
                    </div>
                  )}
                </div>

                {/* Status badge */}
                <StatusBadge
                  variant={STATUS_VARIANT[inv.status] ?? "default"}
                >
                  {t(inv.status === "partially_paid" ? "partiallyPaid" : inv.status as "draft" | "finalized" | "paid" | "cancelled" | "waived")}
                </StatusBadge>

                {/* Time */}
                <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(inv.created_at)}
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {invoices.total > invoices.page_size && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:opacity-50"
              >
                {tc("back")}
              </button>
              <span className="text-sm text-muted-foreground">
                {page} / {Math.ceil(invoices.total / invoices.page_size)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(invoices.total / invoices.page_size)}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:opacity-50"
              >
                {tc("next")}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
