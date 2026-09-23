"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Building2,
  Plus,
  X,
  Calculator,
  AlertTriangle,
} from "lucide-react";
import {
  useFixedAssets,
  useCreateFixedAsset,
  useRunDepreciation,
  useAccounts,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { AccountSelect } from "@/components/finance/AccountSelect";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils";

const assetSchema = z.object({
  name: z.string().min(2),
  account_id: z.string().min(1),
  purchase_date: z.string().min(1),
  purchase_cost: z.coerce.number().min(0.01),
  salvage_value: z.coerce.number().min(0),
  useful_life_months: z.coerce.number().int().min(1),
  depreciation_method: z.enum(["straight_line", "declining_balance"]),
});

type AssetForm = z.infer<typeof assetSchema>;

/**
 * Fixed Assets & Depreciation page.
 *
 * @returns Assets page
 */
export default function FixedAssetsPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");
  const { data: assets, isLoading } = useFixedAssets();
  const { data: accounts } = useAccounts();
  const createAsset = useCreateFixedAsset();
  const runDepreciation = useRunDepreciation();
  const accountMap = new Map((accounts ?? []).map((a) => [a.id, a]));

  const [showDialog, setShowDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accountId, setAccountId] = useState("");

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors: formErrors },
  } = useForm<AssetForm>({
    resolver: zodResolver(assetSchema),
    defaultValues: {
      purchase_date: new Date().toISOString().slice(0, 10),
      salvage_value: 0,
      depreciation_method: "straight_line",
    },
  });

  const onSubmit = (form: AssetForm) => {
    setError(null);
    createAsset.mutate(form, {
      onSuccess: () => {
        setShowDialog(false);
        reset();
        setAccountId("");
      },
      onError: (err) => setError(err.message),
    });
  };

  const handleRunDep = () => {
    if (!confirm(t("confirmRunDepreciation"))) return;
    runDepreciation.mutate({});
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={Building2}
        title={t("fixedAssets")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("fixedAssets") },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunDep}
              disabled={runDepreciation.isPending}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
            >
              <Calculator className="h-4 w-4" />
              {t("runDepreciation")}
            </button>
            <button
              onClick={() => setShowDialog(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              {t("addAsset")}
            </button>
          </div>
        }
      />

      <DataTable
        headers={[
          { label: t("assetName") },
          { label: t("account") },
          { label: t("purchaseDate") },
          { label: t("cost"), className: "text-right" },
          { label: t("usefulLifeMonths"), className: "text-right" },
          { label: t("accumulatedDepreciation"), className: "text-right" },
          { label: t("netBookValue"), className: "text-right" },
          { label: t("status") },
        ]}
        isLoading={isLoading}
        isEmpty={!isLoading && !(assets?.length ?? 0)}
        emptyMessage={t("noFixedAssets")}
      >
        {(assets ?? []).map((a) => (
          <tr key={a.id}>
            <td className="px-4 py-3 text-foreground">{a.name}</td>
            <td className="px-4 py-3 text-xs text-muted-foreground">
              {accountMap.get(a.account_id)?.code ?? a.account_code}{" "}
              {accountMap.get(a.account_id)?.name ?? a.account_name}
            </td>
            <td className="px-4 py-3 text-muted-foreground">{formatDate(a.purchase_date)}</td>
            <td className="px-4 py-3 text-right">
              <MoneyDisplay value={a.purchase_cost} colorize={false} />
            </td>
            <td className="px-4 py-3 text-right tabular-nums text-foreground">
              {a.useful_life_months}
            </td>
            <td className="px-4 py-3 text-right">
              <MoneyDisplay value={a.accumulated_depreciation} colorize={false} />
            </td>
            <td className="px-4 py-3 text-right">
              <MoneyDisplay
                value={Number(a.purchase_cost) - Number(a.accumulated_depreciation)}
                colorize={false}
                bold
              />
            </td>
            <td className="px-4 py-3">
              <StatusBadge variant={a.is_active ? "success" : "default"}>
                {a.is_active ? t("active") : t("retired")}
              </StatusBadge>
            </td>
          </tr>
        ))}
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
              <h2 className="text-lg font-bold text-foreground">{t("addAsset")}</h2>
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
                  {t("assetName")} *
                </label>
                <input
                  {...register("name")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
                {formErrors.name && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.name.message}</p>
                )}
              </div>
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
                  typeFilter={["asset"]}
                />
                <input type="hidden" {...register("account_id")} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("purchaseDate")} *
                  </label>
                  <input
                    type="date"
                    {...register("purchase_date")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("purchaseCost")} *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("purchase_cost")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                  {formErrors.purchase_cost && (
                    <p className="mt-1 text-xs text-red-500">
                      {formErrors.purchase_cost.message}
                    </p>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("usefulLifeMonths")} *
                  </label>
                  <input
                    type="number"
                    {...register("useful_life_months")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                  {formErrors.useful_life_months && (
                    <p className="mt-1 text-xs text-red-500">
                      {formErrors.useful_life_months.message}
                    </p>
                  )}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("salvageValue")}
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    {...register("salvage_value")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("depreciationMethod")}
                </label>
                <select
                  {...register("depreciation_method")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                >
                  <option value="straight_line">{t("straightLine")}</option>
                  <option value="declining_balance">{t("decliningBalance")}</option>
                </select>
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
                  disabled={createAsset.isPending}
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
