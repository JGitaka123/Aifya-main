"use client";

import { useState, useRef, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  RefreshCw,
  Upload,
  CheckCircle2,
  Link2,
  AlertTriangle,
} from "lucide-react";
import {
  useAccounts,
  useBankStatements,
  useImportBankStatement,
  useMatchStatement,
  useReconciliation,
  useTransactions,
  usePeriods,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { AccountSelect } from "@/components/finance/AccountSelect";
import { PeriodSelect } from "@/components/finance/PeriodSelect";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { cn, formatDate } from "@/lib/utils";

/**
 * Bank Reconciliation page — import bank statement, match entries, mark reconciled.
 *
 * @returns Reconciliation page
 */
export default function ReconciliationPage() {
  const t = useTranslations("finance");
  const tc = useTranslations("common");
  const [accountId, setAccountId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [selectedStatementId, setSelectedStatementId] = useState<string | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: accounts } = useAccounts();
  const { data: statements } = useBankStatements(accountId);
  const { data: txs } = useTransactions();
  const { data: recon } = useReconciliation(accountId, periodId);
  const { data: periods } = usePeriods();

  const importStatement = useImportBankStatement();
  const matchStatement = useMatchStatement();

  // Filter to cash accounts only
  const cashAccounts = useMemo(
    () => accounts?.filter((a) => a.type === "asset" && a.code.startsWith("10")),
    [accounts],
  );

  const unmatchedStatements = (statements ?? []).filter((s) => !s.matched);
  // GL entries belonging to this account that aren't matched yet — naive approach: use transactions
  const unmatchedGlEntries = useMemo(() => {
    if (!txs) return [];
    return txs.filter((t) => !t.reversed).slice(0, 50);
  }, [txs]);

  const onUploadClick = () => fileInputRef.current?.click();

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !accountId) return;
    setError(null);
    importStatement.mutate(
      { account_id: accountId, file },
      {
        onError: (err) => setError(err.message),
      },
    );
  };

  const tryMatch = () => {
    if (!selectedStatementId || !selectedEntryId) return;
    setError(null);
    matchStatement.mutate(
      { statement_id: selectedStatementId, entry_id: selectedEntryId },
      {
        onSuccess: () => {
          setSelectedStatementId(null);
          setSelectedEntryId(null);
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={RefreshCw}
        title={t("reconciliation")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("reconciliation") },
        ]}
      />

      {/* Filters & upload */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-72">
          <AccountSelect
            value={accountId}
            onChange={setAccountId}
            typeFilter={["asset"]}
            placeholder={t("selectCashAccount")}
          />
        </div>
        <div className="w-60">
          <PeriodSelect
            value={periodId}
            onChange={setPeriodId}
            filterStatus={["open"]}
          />
        </div>
        <button
          onClick={onUploadClick}
          disabled={!accountId || importStatement.isPending}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          <Upload className="h-4 w-4" />
          {t("importBankStatement")}
        </button>
        <input
          type="file"
          ref={fileInputRef}
          accept=".csv"
          className="hidden"
          onChange={onFileChange}
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {!accountId ? (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-sm text-muted-foreground">
          {t("selectAccountToReconcile")}
        </div>
      ) : (
        <>
          {/* Two-pane match panel */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-4 py-3">
                <h3 className="text-sm font-semibold text-foreground">
                  {t("unmatchedBankEntries")}{" "}
                  <span className="text-muted-foreground">
                    ({unmatchedStatements.length})
                  </span>
                </h3>
              </div>
              <ul className="divide-y divide-border max-h-96 overflow-y-auto">
                {unmatchedStatements.length === 0 ? (
                  <li className="px-4 py-6 text-center text-sm text-muted-foreground">
                    {t("noUnmatchedBankEntries")}
                  </li>
                ) : (
                  unmatchedStatements.map((s) => (
                    <li
                      key={s.id}
                      onClick={() => setSelectedStatementId(s.id)}
                      className={cn(
                        "cursor-pointer px-4 py-2 text-sm transition-colors hover:bg-muted/40",
                        selectedStatementId === s.id && "bg-primary/10",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-foreground">
                          {formatDate(s.date)} · {s.description}
                        </span>
                        <MoneyDisplay value={s.amount} showCurrency={false} bold />
                      </div>
                      {s.reference && (
                        <span className="text-xs text-muted-foreground">{s.reference}</span>
                      )}
                    </li>
                  ))
                )}
              </ul>
            </div>

            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-4 py-3">
                <h3 className="text-sm font-semibold text-foreground">
                  {t("unmatchedGlEntries")}{" "}
                  <span className="text-muted-foreground">
                    ({unmatchedGlEntries.length})
                  </span>
                </h3>
              </div>
              <ul className="divide-y divide-border max-h-96 overflow-y-auto">
                {unmatchedGlEntries.length === 0 ? (
                  <li className="px-4 py-6 text-center text-sm text-muted-foreground">
                    {t("noUnmatchedGlEntries")}
                  </li>
                ) : (
                  unmatchedGlEntries.map((e) => (
                    <li
                      key={e.id}
                      onClick={() => setSelectedEntryId(e.id)}
                      className={cn(
                        "cursor-pointer px-4 py-2 text-sm transition-colors hover:bg-muted/40",
                        selectedEntryId === e.id && "bg-primary/10",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-foreground">
                          {formatDate(e.date)} · {e.description}
                        </span>
                        <MoneyDisplay value={e.total_amount} showCurrency={false} bold />
                      </div>
                      <span className="font-mono text-xs text-muted-foreground">
                        {e.reference_type}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>

          {/* Match button */}
          <div className="flex items-center justify-center">
            <button
              onClick={tryMatch}
              disabled={
                !selectedStatementId || !selectedEntryId || matchStatement.isPending
              }
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
            >
              <Link2 className="h-4 w-4" />
              {matchStatement.isPending ? tc("loading") : t("matchSelected")}
            </button>
          </div>

          {/* Recon summary */}
          {recon && (
            <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
              <h3 className="mb-3 text-sm font-semibold text-foreground">
                {t("reconciliationSummary")}
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <SummaryCell label={t("glBalance")} value={recon.gl_balance} />
                <SummaryCell label={t("depositsInTransit")} value={recon.deposits_in_transit} />
                <SummaryCell label={t("outstandingCheques")} value={recon.outstanding_cheques} />
                <SummaryCell label={t("bankBalance")} value={recon.bank_balance} bold />
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
                <span className="text-xs text-muted-foreground">
                  {t("unmatchedCount")}: {recon.unmatched_count}
                </span>
                {recon.unmatched_count === 0 && !recon.reconciled && (
                  <button className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">
                    <CheckCircle2 className="h-4 w-4" />
                    {t("markReconciled")}
                  </button>
                )}
                {recon.reconciled && (
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-green-600">
                    <CheckCircle2 className="h-4 w-4" />
                    {t("reconciled")}
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {!cashAccounts?.length && accounts && (
        <p className="text-xs text-muted-foreground">{t("noCashAccounts")}</p>
      )}
      {!periods?.length && (
        <p className="text-xs text-muted-foreground">{t("noPeriods")}</p>
      )}
    </div>
  );
}

function SummaryCell({
  label,
  value,
  bold = false,
}: {
  label: string;
  value: string | number;
  bold?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <MoneyDisplay value={value} bold={bold} colorize={false} />
    </div>
  );
}
