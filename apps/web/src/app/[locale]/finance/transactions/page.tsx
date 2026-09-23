"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  useForm,
  useFieldArray,
  type UseFormRegister,
  type UseFormSetValue,
} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ListChecks,
  Plus,
  X,
  AlertTriangle,
  RotateCcw,
  Trash2,
} from "lucide-react";
import {
  useTransactions,
  useTransaction,
  usePostTransaction,
  useReverseTransaction,
  type TransactionFilters,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { DateRangePicker, type DateRange } from "@/components/finance/DateRangePicker";
import { AccountSelect } from "@/components/finance/AccountSelect";
import { formatDate } from "@/lib/utils";

const entrySchema = z.object({
  account_id: z.string().min(1),
  debit: z.coerce.number().min(0),
  credit: z.coerce.number().min(0),
});

const txSchema = z
  .object({
    date: z.string().min(1),
    description: z.string().min(2),
    reference_type: z.string().optional(),
    department_id: z.string().nullable().optional(),
    entries: z.array(entrySchema).min(2),
  })
  .refine(
    (val) => {
      const totalDebit = val.entries.reduce((s, e) => s + (e.debit || 0), 0);
      const totalCredit = val.entries.reduce((s, e) => s + (e.credit || 0), 0);
      return Math.abs(totalDebit - totalCredit) < 0.01;
    },
    { message: "Debits and credits must balance", path: ["entries"] },
  );

type TxForm = z.infer<typeof txSchema>;

/**
 * Single journal-entry row in the manual posting form.
 * Encapsulates the AccountSelect + setValue dance for RHF.
 */
function EntryRow({
  index,
  onRemove,
  register,
  setValue,
  initialAccountId,
  t,
  tc,
}: {
  index: number;
  onRemove: () => void;
  register: UseFormRegister<TxForm>;
  setValue: UseFormSetValue<TxForm>;
  initialAccountId: string;
  t: (k: string) => string;
  tc: (k: string) => string;
}) {
  const [accountId, setAccountId] = useState(initialAccountId);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <AccountSelect
          value={accountId}
          onChange={(id) => {
            setAccountId(id);
            setValue(`entries.${index}.account_id`, id, { shouldValidate: true });
          }}
        />
        <input type="hidden" {...register(`entries.${index}.account_id`)} />
      </div>
      <input
        {...register(`entries.${index}.debit`)}
        type="number"
        step="0.01"
        placeholder={t("debit")}
        className="w-28 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
      />
      <input
        {...register(`entries.${index}.credit`)}
        type="number"
        step="0.01"
        placeholder={t("credit")}
        className="w-28 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
      />
      <button
        type="button"
        onClick={onRemove}
        className="rounded-md p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
        title={tc("delete")}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/**
 * Transactions browser — filter, post manual journals, view detail, reverse.
 *
 * @returns Transactions page
 */
export default function TransactionsPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");

  const [range, setRange] = useState<DateRange>({ start: "", end: "" });
  const [refType, setRefType] = useState<string>("");
  const [departmentId, setDepartmentId] = useState<string>("");
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null);
  const [showPostDialog, setShowPostDialog] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);

  const filters: TransactionFilters = {
    start: range.start || undefined,
    end: range.end || undefined,
    type: refType || undefined,
    department_id: departmentId || undefined,
  };

  const { data: txs, isLoading } = useTransactions(filters);
  const { data: detail } = useTransaction(selectedTxId ?? "");
  const postTx = usePostTransaction();
  const reverseTx = useReverseTransaction();

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    formState: { errors: formErrors },
  } = useForm<TxForm>({
    resolver: zodResolver(txSchema),
    defaultValues: {
      date: new Date().toISOString().slice(0, 10),
      description: "",
      reference_type: "manual",
      entries: [
        { account_id: "", debit: 0, credit: 0 },
        { account_id: "", debit: 0, credit: 0 },
      ],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "entries" });

  const onSubmit = (form: TxForm) => {
    setPostError(null);
    postTx.mutate(
      {
        date: form.date,
        description: form.description,
        reference_type: form.reference_type ?? "manual",
        department_id: form.department_id ?? null,
        entries: form.entries,
      },
      {
        onSuccess: () => {
          setShowPostDialog(false);
          reset();
        },
        onError: (err) => setPostError(err.message),
      },
    );
  };

  const handleReverse = () => {
    if (!selectedTxId) return;
    if (!confirm(t("confirmReverse"))) return;
    reverseTx.mutate(
      { id: selectedTxId },
      {
        onSuccess: () => {
          setSelectedTxId(null);
        },
      },
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={ListChecks}
        title={t("transactions")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("transactions") },
        ]}
        actions={
          <button
            onClick={() => setShowPostDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("newManualPosting")}
          </button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <DateRangePicker value={range} onChange={setRange} />
        <input
          type="text"
          value={refType}
          onChange={(e) => setRefType(e.target.value)}
          placeholder={t("referenceType")}
          className="rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
        />
        <input
          type="text"
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value)}
          placeholder={t("departmentId")}
          className="rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
        />
      </div>

      {/* Table */}
      <DataTable
        headers={[
          { label: t("date") },
          { label: t("reference") },
          { label: t("description") },
          { label: t("amount"), className: "text-right" },
          { label: t("departmentId") },
          { label: t("status") },
        ]}
        isLoading={isLoading}
        isEmpty={!isLoading && !(txs?.length ?? 0)}
        emptyMessage={t("noTransactions")}
      >
        {(txs ?? []).map((tx) => (
          <tr
            key={tx.id}
            className="cursor-pointer hover:bg-muted/30"
            onClick={() => setSelectedTxId(tx.id)}
          >
            <td className="px-4 py-3 text-foreground">{formatDate(tx.date)}</td>
            <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
              {tx.reference_type}
            </td>
            <td className="px-4 py-3 text-foreground">{tx.description}</td>
            <td className="px-4 py-3 text-right">
              <MoneyDisplay value={tx.amount ?? tx.total_amount} bold />
            </td>
            <td className="px-4 py-3 text-muted-foreground">{tx.department_id ?? "—"}</td>
            <td className="px-4 py-3">
              {tx.reversed ? (
                <StatusBadge variant="error">{t("reversed")}</StatusBadge>
              ) : (
                <StatusBadge variant="success">{t("posted")}</StatusBadge>
              )}
            </td>
          </tr>
        ))}
      </DataTable>

      {/* Detail drawer */}
      {selectedTxId && detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setSelectedTxId(null)}
        >
          <div
            className="h-full w-full max-w-xl bg-card p-6 shadow-xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold text-foreground">
                  {t("transactionDetail")}
                </h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {formatDate(detail.date)} · {detail.reference_type}
                </p>
              </div>
              <button
                onClick={() => setSelectedTxId(null)}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-4 text-sm text-foreground">{detail.description}</p>

            <div className="mb-4 rounded-xl border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left">{t("account")}</th>
                    <th className="px-3 py-2 text-right">{t("debit")}</th>
                    <th className="px-3 py-2 text-right">{t("credit")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {detail.entries.map((e, i) => (
                    <tr key={i}>
                      <td className="px-3 py-2 text-foreground">
                        <span className="font-mono text-xs text-muted-foreground">
                          {e.account_code}
                        </span>{" "}
                        {e.account_name}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <MoneyDisplay value={e.debit} showCurrency={false} colorize={false} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <MoneyDisplay value={e.credit} showCurrency={false} colorize={false} />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t border-border bg-muted/20 text-xs font-semibold">
                  <tr>
                    <td className="px-3 py-2 text-foreground">{t("total")}</td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay
                        value={detail.amount ?? detail.total_amount}
                        showCurrency={false}
                        colorize={false}
                        bold
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay
                        value={detail.amount ?? detail.total_amount}
                        showCurrency={false}
                        colorize={false}
                        bold
                      />
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2">
              {!detail.reversed && (
                <button
                  onClick={handleReverse}
                  disabled={reverseTx.isPending}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-950/30"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  {t("reverseTransaction")}
                </button>
              )}
              <button
                onClick={() => setSelectedTxId(null)}
                className="rounded-md border border-input px-3 py-1.5 text-sm text-foreground hover:bg-muted"
              >
                {tc("back")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Post dialog */}
      {showPostDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fade-in_0.15s_ease-out]"
          onClick={() => setShowPostDialog(false)}
        >
          <div
            className="w-full max-w-2xl rounded-2xl bg-card p-6 shadow-xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <h2 className="text-lg font-bold text-foreground">
                {t("newManualPosting")}
              </h2>
              <button
                onClick={() => setShowPostDialog(false)}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {postError && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <p>{postError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("date")} *
                  </label>
                  <input
                    type="date"
                    {...register("date")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("referenceType")}
                  </label>
                  <input
                    {...register("reference_type")}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("description")} *
                </label>
                <textarea
                  {...register("description")}
                  rows={2}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border"
                />
                {formErrors.description && (
                  <p className="mt-1 text-xs text-red-500">
                    {formErrors.description.message}
                  </p>
                )}
              </div>

              {/* Journal entries */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-sm font-medium text-foreground">
                    {t("journalEntries")} *
                  </label>
                  <button
                    type="button"
                    onClick={() => append({ account_id: "", debit: 0, credit: 0 })}
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                  >
                    <Plus className="h-3 w-3" /> {t("addEntry")}
                  </button>
                </div>
                <div className="space-y-2">
                  {fields.map((field, i) => (
                    <EntryRow
                      key={field.id}
                      index={i}
                      onRemove={() => remove(i)}
                      register={register}
                      setValue={setValue}
                      initialAccountId={field.account_id ?? ""}
                      t={t}
                      tc={tc}
                    />
                  ))}
                </div>
                {formErrors.entries && (
                  <p className="mt-1 text-xs text-red-500">
                    {formErrors.entries.message ?? t("balanceMismatch")}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPostDialog(false)}
                  className="rounded-md border border-input px-3 py-1.5 text-sm text-foreground hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={postTx.isPending}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {postTx.isPending ? tc("loading") : t("postTransaction")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
