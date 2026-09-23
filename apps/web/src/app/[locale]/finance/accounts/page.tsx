"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Library,
  Plus,
  Search,
  Pencil,
  Trash2,
  X,
  AlertTriangle,
} from "lucide-react";
import {
  useAccounts,
  useCreateAccount,
  useUpdateAccount,
  useDeleteAccount,
  type Account,
  type AccountType,
  type CashflowCategory,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { DataTable } from "@/components/ui/DataTable";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { HelpTooltip } from "@/components/help/HelpTooltip";

const accountSchema = z.object({
  code: z.string().min(1).max(20),
  name: z.string().min(2).max(120),
  type: z.enum(["asset", "liability", "equity", "income", "expense"]),
  cashflow_category: z.enum(["operating", "investing", "financing", "none"]),
  parent_id: z.string().nullable().optional(),
});

type AccountForm = z.infer<typeof accountSchema>;

const TYPE_VARIANT: Record<AccountType, "info" | "purple" | "warning" | "success" | "error"> = {
  asset: "info",
  liability: "warning",
  equity: "purple",
  income: "success",
  expense: "error",
};

const TYPE_TABS: { key: string; type?: AccountType }[] = [
  { key: "all" },
  { key: "asset", type: "asset" },
  { key: "liability", type: "liability" },
  { key: "equity", type: "equity" },
  { key: "income", type: "income" },
  { key: "expense", type: "expense" },
];

/**
 * Chart of Accounts page — list, filter, search, add, edit, soft-delete.
 *
 * @returns Accounts list page
 */
export default function ChartOfAccountsPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");
  const { data: accounts, isLoading } = useAccounts();
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();

  const [activeTab, setActiveTab] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!accounts) return [];
    let list = accounts;
    if (activeTab !== "all") {
      list = list.filter((a) => a.type === activeTab);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (a) =>
          a.code.toLowerCase().includes(q) || a.name.toLowerCase().includes(q),
      );
    }
    return list;
  }, [accounts, activeTab, searchQuery]);

  const tabsForUi = TYPE_TABS.map((tab) => ({
    key: tab.key,
    label: t(`accountTypes.${tab.key}`),
    count:
      tab.key === "all"
        ? accounts?.length
        : accounts?.filter((a) => a.type === tab.type).length,
  }));

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors: formErrors },
  } = useForm<AccountForm>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      type: "asset",
      cashflow_category: "operating",
    },
  });

  const openCreate = () => {
    setEditingAccount(null);
    setError(null);
    reset({ type: "asset", cashflow_category: "operating" });
    setShowDialog(true);
  };

  const openEdit = (acc: Account) => {
    setEditingAccount(acc);
    setError(null);
    reset({
      code: acc.code,
      name: acc.name,
      type: acc.type,
      cashflow_category: acc.cashflow_category,
      parent_id: acc.parent_id ?? undefined,
    });
    setShowDialog(true);
  };

  const onSubmit = (form: AccountForm) => {
    setError(null);
    if (editingAccount) {
      // Editing: only metadata is updatable
      updateAccount.mutate(
        {
          id: editingAccount.id,
          name: form.name,
          cashflow_category: form.cashflow_category,
        },
        {
          onSuccess: () => {
            setShowDialog(false);
            setEditingAccount(null);
            reset();
          },
          onError: (err) => setError(err.message),
        },
      );
    } else {
      createAccount.mutate(form, {
        onSuccess: () => {
          setShowDialog(false);
          reset();
        },
        onError: (err) => setError(err.message),
      });
    }
  };

  const handleDelete = (acc: Account) => {
    if (!confirm(t("confirmDeleteAccount", { name: acc.name }))) return;
    deleteAccount.mutate({ id: acc.id });
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={Library}
        title={t("chartOfAccounts")}
        breadcrumbs={[{ label: t("title"), href: "/finance" }, { label: t("chartOfAccounts") }]}
        actions={
          <button
            onClick={openCreate}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("addAccount")}
          </button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <TabGroup
          tabs={tabsForUi}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          variant="pills"
        />
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t("searchAccounts")}
            className="w-full rounded-md border border-input bg-card px-3 py-2 pl-8 text-sm text-foreground sm:w-64"
          />
        </div>
      </div>

      {/* Table */}
      <DataTable
        headers={[
          { label: t("code") },
          { label: t("name") },
          { label: t("accountType") },
          { label: t("cashflowCategory") },
          { label: t("balance"), className: "text-right" },
          { label: tc("actions"), className: "text-right" },
        ]}
        isLoading={isLoading}
        isEmpty={!isLoading && !filtered.length}
        emptyMessage={t("noAccountsFound")}
      >
        {filtered.map((acc) => (
          <tr key={acc.id} className="hover:bg-muted/30">
            <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
              {acc.code}
            </td>
            <td className="px-4 py-3 text-foreground">{acc.name}</td>
            <td className="px-4 py-3">
              <StatusBadge variant={TYPE_VARIANT[acc.type]}>
                {t(`accountTypes.${acc.type}`)}
              </StatusBadge>
            </td>
            <td className="px-4 py-3 text-muted-foreground">
              {t(`cashflow.${acc.cashflow_category}`)}
            </td>
            <td className="px-4 py-3 text-right">
              <MoneyDisplay value={acc.balance} colorize={false} bold />
            </td>
            <td className="px-4 py-3 text-right">
              <div className="inline-flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => openEdit(acc)}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  title={tc("edit")}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(acc)}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
                  title={tc("delete")}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </td>
          </tr>
        ))}
      </DataTable>

      {/* Dialog */}
      {showDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setShowDialog(false)}
          role="presentation"
        >
          <div
            className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="account-dialog-title"
          >
            <div className="mb-4 flex items-start justify-between">
              <h2 id="account-dialog-title" className="text-lg font-bold text-foreground">
                {editingAccount ? t("editAccount") : t("addAccount")}
              </h2>
              <button
                type="button"
                onClick={() => setShowDialog(false)}
                aria-label={tc("cancel")}
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
                <label htmlFor="account-code" className="mb-1 block text-sm font-medium text-foreground inline-flex items-center">
                  {t("code")} *
                  <HelpTooltip content={t("help.accountCode")} />
                </label>
                <input
                  id="account-code"
                  {...register("code")}
                  disabled={!!editingAccount}
                  aria-invalid={!!formErrors.code}
                  placeholder="1001"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground disabled:opacity-50 dark:border-border"
                />
                {formErrors.code && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.code.message}</p>
                )}
              </div>
              <div>
                <label htmlFor="account-name" className="mb-1 block text-sm font-medium text-foreground">
                  {t("name")} *
                </label>
                <input
                  id="account-name"
                  {...register("name")}
                  aria-invalid={!!formErrors.name}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
                {formErrors.name && (
                  <p className="mt-1 text-xs text-red-500">{formErrors.name.message}</p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="account-type" className="mb-1 block text-sm font-medium text-foreground inline-flex items-center">
                    {t("accountType")} *
                    <HelpTooltip content={t("help.accountType")} />
                  </label>
                  <select
                    id="account-type"
                    {...register("type")}
                    disabled={!!editingAccount}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground disabled:opacity-50 dark:border-border"
                  >
                    {(["asset", "liability", "equity", "income", "expense"] as AccountType[]).map(
                      (typ) => (
                        <option key={typ} value={typ}>
                          {t(`accountTypes.${typ}`)}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <div>
                  <label htmlFor="account-cashflow" className="mb-1 block text-sm font-medium text-foreground inline-flex items-center">
                    {t("cashflowCategory")} *
                    <HelpTooltip content={t("help.cashflowCategory")} />
                  </label>
                  <select
                    id="account-cashflow"
                    {...register("cashflow_category")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  >
                    {(["operating", "investing", "financing", "none"] as CashflowCategory[]).map(
                      (cat) => (
                        <option key={cat} value={cat}>
                          {t(`cashflow.${cat}`)}
                        </option>
                      ),
                    )}
                  </select>
                </div>
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
                  disabled={createAccount.isPending || updateAccount.isPending}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {(createAccount.isPending || updateAccount.isPending) && (
                    <span
                      aria-hidden
                      className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                    />
                  )}
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
