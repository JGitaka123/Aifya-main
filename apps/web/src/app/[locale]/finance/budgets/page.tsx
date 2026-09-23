"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { PiggyBank, Plus, X, AlertTriangle } from "lucide-react";
import {
  useBudgets,
  useCreateBudget,
  useBudgetVsActual,
  useAccounts,
  usePeriods,
} from "@/hooks/useFinance";
import { useDepartments } from "@/hooks/usePayroll";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { AccountSelect } from "@/components/finance/AccountSelect";
import { PeriodSelect } from "@/components/finance/PeriodSelect";
import { cn } from "@/lib/utils";

const budgetSchema = z.object({
  account_id: z.string().min(1),
  period_id: z.string().min(1),
  department_id: z.string().nullable().optional(),
  budgeted_amount: z.coerce.number().min(0.01),
  notes: z.string().max(2000).optional(),
});

type BudgetForm = z.infer<typeof budgetSchema>;

function asNumber(v: string | number | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : 0;
}

/**
 * Budgets page — list, add, with quick variance view.
 *
 * @returns Budgets page
 */
export default function BudgetsPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");
  const { data: budgets, isLoading } = useBudgets();
  const { data: accounts } = useAccounts();
  const { data: periods } = usePeriods();
  const { data: departments } = useDepartments();
  const createBudget = useCreateBudget();
  const accountMap = new Map((accounts ?? []).map((a) => [a.id, a]));
  const periodMap = new Map((periods ?? []).map((p) => [p.id, p]));
  const departmentMap = new Map((departments ?? []).map((d) => [d.id, d]));

  const [showDialog, setShowDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accountId, setAccountId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [varianceForPeriod, setVarianceForPeriod] = useState("");

  const { data: variance } = useBudgetVsActual(varianceForPeriod);
  const varianceMap = new Map(
    (variance?.rows ?? []).map((r) => [r.account_id + (r.department_id ?? ""), r]),
  );

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors: formErrors },
  } = useForm<BudgetForm>({
    resolver: zodResolver(budgetSchema),
  });

  const onSubmit = (form: BudgetForm) => {
    setError(null);
    createBudget.mutate(
      { ...form, department_id: form.department_id || null },
      {
        onSuccess: () => {
          setShowDialog(false);
          reset();
          setAccountId("");
          setPeriodId("");
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={PiggyBank}
        title={t("budgets")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("budgets") },
        ]}
        actions={
          <button
            onClick={() => setShowDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("addBudget")}
          </button>
        }
      />

      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-foreground">
          {t("varianceFor")}
        </label>
        <div className="w-60">
          <PeriodSelect value={varianceForPeriod} onChange={setVarianceForPeriod} />
        </div>
      </div>

      <DataTable
        headers={[
          { label: t("account") },
          { label: t("department") },
          { label: t("period") },
          { label: t("budget"), className: "text-right" },
          { label: t("actual"), className: "text-right" },
          { label: t("variance"), className: "text-right" },
        ]}
        isLoading={isLoading}
        isEmpty={!isLoading && !(budgets?.length ?? 0)}
        emptyMessage={t("noBudgets")}
      >
        {(budgets ?? []).map((b) => {
          const va = varianceMap.get(b.account_id + (b.department_id ?? ""));
          const overBudget = va && asNumber(va.variance) < 0;
          return (
            <tr key={b.id}>
              <td className="px-4 py-3 text-foreground">
                <span className="font-mono text-xs text-muted-foreground">
                  {accountMap.get(b.account_id)?.code ?? b.account_code}
                </span>{" "}
                {accountMap.get(b.account_id)?.name ?? b.account_name}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {departmentMap.get(b.department_id ?? "")?.name ??
                  b.department_name ??
                  "—"}
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                {periodMap.get(b.period_id)?.name ?? b.period_id}
              </td>
              <td className="px-4 py-3 text-right">
                <MoneyDisplay value={b.budgeted_amount} colorize={false} />
              </td>
              <td className="px-4 py-3 text-right">
                {va ? (
                  <MoneyDisplay value={va.actual} colorize={false} />
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
              <td
                className={cn(
                  "px-4 py-3 text-right",
                  overBudget && "bg-red-50 dark:bg-red-950/30",
                )}
              >
                {va ? (
                  <MoneyDisplay value={va.variance} bold />
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          );
        })}
      </DataTable>

      {showDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowDialog(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <h2 className="text-lg font-bold text-foreground">{t("addBudget")}</h2>
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
                  {t("account")} *
                </label>
                <AccountSelect
                  value={accountId}
                  onChange={(id) => {
                    setAccountId(id);
                    setValue("account_id", id, { shouldValidate: true });
                  }}
                />
                <input type="hidden" {...register("account_id")} />
                {formErrors.account_id && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.account_id.message}</p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("period")} *
                </label>
                <PeriodSelect
                  value={periodId}
                  onChange={(id) => {
                    setPeriodId(id);
                    setValue("period_id", id, { shouldValidate: true });
                  }}
                />
                <input type="hidden" {...register("period_id")} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("departmentId")}
                </label>
                <select
                  {...register("department_id")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                >
                  <option value="">— {tc("none")} —</option>
                  {(departments ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("budgetedAmount")} *
                </label>
                <input
                  type="number"
                  step="0.01"
                  {...register("budgeted_amount")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
                {formErrors.budgeted_amount && (
                  <p className="mt-1 text-xs text-red-500">
                    {formErrors.budgeted_amount.message}
                  </p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {tc("notes")}
                </label>
                <textarea
                  rows={2}
                  {...register("notes")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
              </div>
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
                  disabled={createBudget.isPending}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {tc("save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
