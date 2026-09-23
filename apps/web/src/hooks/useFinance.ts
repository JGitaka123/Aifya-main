"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";
export type CashflowCategory = "operating" | "investing" | "financing" | "none";
export type PeriodStatus = "open" | "closed" | "locked" | "year_end";

/** Backend may return monetary values as string or number. */
export type Money = string | number;

export interface Account {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  cashflow_category: CashflowCategory;
  is_active: boolean;
  parent_id?: string | null;
  balance?: Money;
}

export interface AccountCreate {
  code: string;
  name: string;
  type: AccountType;
  cashflow_category: CashflowCategory;
  parent_id?: string | null;
}

export interface AccountUpdate {
  name?: string;
  cashflow_category?: CashflowCategory;
  is_active?: boolean;
}

export interface JournalEntry {
  account_id: string;
  account_code: string;
  account_name: string;
  debit: Money;
  credit: Money;
}

export interface Transaction {
  id: string;
  date: string;
  reference_type: string;
  reference_id?: string | null;
  description: string;
  department_id?: string | null;
  period_id: string;
  amount?: Money;
  total_amount?: Money;
  entries: JournalEntry[];
  reversed?: boolean;
  is_reversal?: boolean;
}

export interface TransactionListItem {
  id: string;
  date: string;
  reference_type: string;
  reference_id?: string | null;
  event_type: string;
  description: string;
  department_id?: string | null;
  amount: Money;
  total_amount?: Money;
  is_reversal: boolean;
  reversed?: boolean;
}

export interface TransactionFilters {
  start?: string;
  end?: string;
  type?: string;
  department_id?: string;
}

export interface TransactionCreate {
  date: string;
  description: string;
  reference_type?: string;
  department_id?: string | null;
  entries: { account_id: string; debit: number; credit: number }[];
}

export interface GeneralLedgerRow {
  date: string;
  reference: string;
  description: string;
  debit: Money;
  credit: Money;
  balance: Money;
}

export interface GeneralLedgerResponse {
  account_id: string;
  account_code: string;
  account_name: string;
  opening_balance: Money;
  closing_balance: Money;
  rows: GeneralLedgerRow[];
}

export interface TrialBalanceRow {
  account_code: string;
  account_name: string;
  debit_total: Money;
  credit_total: Money;
  balance: Money;
}

export interface TrialBalanceResponse {
  period_id: string;
  rows: TrialBalanceRow[];
  total_debit: Money;
  total_credit: Money;
}

export interface PnLLineItem {
  account_code: string;
  account_name: string;
  amount: Money;
}

export interface ProfitLossResponse {
  start: string;
  end: string;
  income: PnLLineItem[];
  expenses: PnLLineItem[];
  total_income: Money;
  total_expenses: Money;
  net_profit: Money;
}

export interface BalanceSheetSection {
  account_code: string;
  account_name: string;
  amount: Money;
}

export interface BalanceSheetResponse {
  as_of: string;
  assets: BalanceSheetSection[];
  liabilities: BalanceSheetSection[];
  equity: BalanceSheetSection[];
  total_assets: Money;
  total_liabilities: Money;
  total_equity: Money;
}

export interface CashFlowRow {
  account_id: string;
  account_code: string;
  account_name: string;
  amount: Money;
}

export interface CashFlowSection {
  rows: CashFlowRow[];
  total: Money;
}

export interface CashFlowResponse {
  start: string;
  end: string;
  method: "direct" | "indirect";
  operating: CashFlowSection;
  investing: CashFlowSection;
  financing: CashFlowSection;
  net_operating: Money;
  net_investing: Money;
  net_financing: Money;
  net_change: Money;
  opening_cash: Money;
  closing_cash: Money;
}

export interface ARAgingRow {
  insurer_id: string;
  insurer_name: string;
  current: Money;
  days_30: Money;
  days_60: Money;
  days_90: Money;
  days_120_plus: Money;
  total: Money;
}

export interface ARAgingResponse {
  as_of: string;
  rows: ARAgingRow[];
  total_current: Money;
  total_30: Money;
  total_60: Money;
  total_90: Money;
  total_120_plus: Money;
  grand_total: Money;
}

export interface BudgetVsActualRow {
  account_id: string;
  account_code: string;
  account_name: string;
  department_id?: string | null;
  department_name?: string | null;
  budget: Money;
  actual: Money;
  variance: Money;
  pct_used: Money;
}

export interface BudgetVsActualResponse {
  period_id: string;
  rows: BudgetVsActualRow[];
}

export interface Period {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  closed_by?: string | null;
  closed_at?: string | null;
  year_end?: boolean;
}

export interface PeriodCreate {
  name: string;
  start_date: string;
  end_date: string;
  year_end?: boolean;
}

export interface BankStatementEntry {
  id: string;
  account_id: string;
  date: string;
  description: string;
  amount: Money;
  reference?: string | null;
  matched: boolean;
  matched_entry_id?: string | null;
}

export interface ReconciliationSummary {
  account_id: string;
  period_id: string;
  gl_balance: Money;
  bank_balance: Money;
  deposits_in_transit: Money;
  outstanding_cheques: Money;
  unmatched_count: number;
  reconciled: boolean;
}

export interface FixedAsset {
  id: string;
  name: string;
  account_id: string;
  account_code?: string;
  account_name?: string;
  purchase_date: string;
  purchase_cost: Money;
  useful_life_months: number;
  salvage_value: Money;
  depreciation_method: "straight_line" | "declining_balance";
  accumulated_depreciation: Money;
  is_active: boolean;
}

export interface FixedAssetCreate {
  name: string;
  account_id: string;
  purchase_date: string;
  purchase_cost: number;
  useful_life_months: number;
  salvage_value?: number;
  depreciation_method?: "straight_line" | "declining_balance";
  asset_tag?: string | null;
}

export interface TaxRate {
  id: string;
  name: string;
  rate: Money;
  is_active: boolean;
}

export interface TaxRateCreate {
  name: string;
  rate: number;
}

export interface Budget {
  id: string;
  account_id: string;
  account_code?: string;
  account_name?: string;
  department_id?: string | null;
  department_name?: string | null;
  period_id: string;
  budgeted_amount: Money;
  notes?: string | null;
}

export interface BudgetCreate {
  account_id: string;
  department_id?: string | null;
  period_id: string;
  budgeted_amount: number;
  notes?: string | null;
}

export interface RecurringTransaction {
  id: string;
  name: string;
  description: string;
  cadence: "daily" | "weekly" | "monthly" | "quarterly" | "yearly";
  next_run: string;
  amount: Money;
  is_active: boolean;
}

export interface RecurringTransactionCreate {
  name: string;
  description: string;
  cadence: "daily" | "weekly" | "monthly" | "quarterly" | "yearly";
  next_run: string;
  amount: number;
  entries: { account_id: string; debit: number; credit: number }[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

function toQueryParams(filters: Record<string, string | undefined>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "") out[k] = v;
  }
  return out;
}

type ListResponse<T> = T[] | { items?: T[] };

function listItems<T>(response: ListResponse<T>): T[] {
  return Array.isArray(response) ? response : response.items ?? [];
}

// ── Accounts ───────────────────────────────────────────────────────────────

/** Fetch the chart of accounts. */
export function useAccounts() {
  return useOfflineQuery<Account[]>({
    queryKey: ["finance", "accounts"],
    queryFn: () =>
      apiClient.get<ListResponse<Account>>("/finance/accounts").then(listItems),
  });
}

/** Fetch a single account. */
export function useAccount(id: string) {
  return useOfflineQuery<Account>({
    queryKey: ["finance", "accounts", id],
    queryFn: () => apiClient.get<Account>(`/finance/accounts/${id}`),
    enabled: !!id,
  });
}

/** Create a new account. */
export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Account, AccountCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Account>("/finance/accounts", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "accounts"] });
      },
    },
    { url: "/finance/accounts", method: "POST" }
  );
}

/** Update an account. */
export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Account, { id: string } & AccountUpdate>(
    {
      mutationFn: ({ id, ...data }) =>
        apiClient.patch<Account>(`/finance/accounts/${id}`, data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "accounts"] });
      },
    },
    { url: "/finance/accounts", method: "PATCH" }
  );
}

/** Soft-delete an account. */
export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useOfflineMutation<void, { id: string }>(
    {
      mutationFn: ({ id }) =>
        apiClient.request<void>(`/finance/accounts/${id}`, { method: "DELETE" }),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "accounts"] });
      },
    },
    { url: "/finance/accounts", method: "DELETE" }
  );
}

// ── Transactions ───────────────────────────────────────────────────────────

/** Fetch transactions with optional filters. */
export function useTransactions(filters: TransactionFilters = {}) {
  return useOfflineQuery<TransactionListItem[]>({
    queryKey: ["finance", "transactions", filters],
    queryFn: () =>
      apiClient.get<ListResponse<TransactionListItem>>(
        "/finance/transactions",
        toQueryParams({
          start: filters.start,
          end: filters.end,
          type: filters.type,
          department_id: filters.department_id,
        })
      ).then(listItems),
  });
}

/** Fetch a single transaction with its journal entries. */
export function useTransaction(id: string) {
  return useOfflineQuery<Transaction>({
    queryKey: ["finance", "transactions", id],
    queryFn: () => apiClient.get<Transaction>(`/finance/transactions/${id}`),
    enabled: !!id,
  });
}

/** Post a manual journal entry (finance admin only). */
export function usePostTransaction() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Transaction, TransactionCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Transaction>(
          "/finance/transactions/manual",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/transactions/manual", method: "POST" }
  );
}

/** Reverse an existing transaction. */
export function useReverseTransaction() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Transaction, { id: string }>(
    {
      mutationFn: ({ id }) =>
        apiClient.post<Transaction>(
          `/finance/transactions/${id}/reverse`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/transactions/reverse", method: "POST" }
  );
}

// ── Reports ────────────────────────────────────────────────────────────────

/** General ledger report for a single account. */
export function useGeneralLedger(accountId: string, start: string, end: string) {
  return useOfflineQuery<GeneralLedgerResponse>({
    queryKey: ["finance", "reports", "gl", accountId, start, end],
    queryFn: () =>
      apiClient.get<GeneralLedgerResponse>(
        "/finance/reports/general-ledger",
        toQueryParams({ account_id: accountId, start, end })
      ),
    enabled: !!accountId && !!start && !!end,
  });
}

/** Trial balance for a period or as-of date. */
export function useTrialBalance(periodId?: string, asOf?: string) {
  return useOfflineQuery<TrialBalanceResponse>({
    queryKey: ["finance", "reports", "trial-balance", periodId ?? "", asOf ?? ""],
    queryFn: () =>
      apiClient.get<TrialBalanceResponse>(
        "/finance/reports/trial-balance",
        toQueryParams({ period_id: periodId, as_of: asOf })
      ),
  });
}

/** Profit & Loss for a date range. */
export function useProfitLoss(start: string, end: string, departmentId?: string) {
  return useOfflineQuery<ProfitLossResponse>({
    queryKey: ["finance", "reports", "pl", start, end, departmentId ?? ""],
    queryFn: () =>
      apiClient.get<ProfitLossResponse>(
        "/finance/reports/profit-loss",
        toQueryParams({ start, end, department_id: departmentId })
      ),
    enabled: !!start && !!end,
  });
}

/** Balance sheet as of a given date. */
export function useBalanceSheet(asOfDate: string) {
  return useOfflineQuery<BalanceSheetResponse>({
    queryKey: ["finance", "reports", "balance-sheet", asOfDate],
    queryFn: () =>
      apiClient.get<BalanceSheetResponse>(
        "/finance/reports/balance-sheet",
        toQueryParams({ as_of: asOfDate })
      ),
    enabled: !!asOfDate,
  });
}

/** Cash flow report. */
export function useCashFlow(
  start: string,
  end: string,
  method: "direct" | "indirect"
) {
  return useOfflineQuery<CashFlowResponse>({
    queryKey: ["finance", "reports", "cash-flow", start, end, method],
    queryFn: () =>
      apiClient.get<CashFlowResponse>(
        "/finance/reports/cash-flow",
        toQueryParams({ start, end, method })
      ),
    enabled: !!start && !!end,
  });
}

/** AR aging report. */
export function useARAging(asOfDate: string) {
  return useOfflineQuery<ARAgingResponse>({
    queryKey: ["finance", "reports", "ar-aging", asOfDate],
    queryFn: () =>
      apiClient.get<ARAgingResponse>(
        "/finance/reports/ar-aging",
        toQueryParams({ as_of_date: asOfDate })
      ),
    enabled: !!asOfDate,
  });
}

/** Budget vs actual for a period. */
export function useBudgetVsActual(periodId: string) {
  return useOfflineQuery<BudgetVsActualResponse>({
    queryKey: ["finance", "reports", "budget-vs-actual", periodId],
    queryFn: () =>
      apiClient.get<BudgetVsActualResponse>(
        "/finance/reports/budget-vs-actual",
        toQueryParams({ period_id: periodId })
      ),
    enabled: !!periodId,
  });
}

// ── Periods ────────────────────────────────────────────────────────────────

/** List all accounting periods. */
export function usePeriods() {
  return useOfflineQuery<Period[]>({
    queryKey: ["finance", "periods"],
    queryFn: () =>
      apiClient.get<ListResponse<Period>>("/finance/periods").then(listItems),
  });
}

/** Create a new period. */
export function useCreatePeriod() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Period, PeriodCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Period>("/finance/periods", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "periods"] });
      },
    },
    { url: "/finance/periods", method: "POST" }
  );
}

/** Close (lock) a period. */
export function useClosePeriod() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Period, { id: string; reason: string }>(
    {
      mutationFn: ({ id, reason }) =>
        apiClient.post<Period>(
          `/finance/periods/${id}/close`,
          { reason },
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/periods/close", method: "POST" }
  );
}

/** Year-end close (rolls income/expense into retained earnings). */
export function useYearEndClose() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Period, { id: string }>(
    {
      mutationFn: ({ id }) =>
        apiClient.post<Period>(
          `/finance/periods/${id}/year-end-close`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/periods/year-end-close", method: "POST" }
  );
}

// ── Bank statements / Reconciliation ───────────────────────────────────────

/** Bank statement entries for a cash account. */
export function useBankStatements(accountId: string) {
  return useOfflineQuery<BankStatementEntry[]>({
    queryKey: ["finance", "bank-statements", accountId],
    queryFn: () =>
      apiClient.get<BankStatementEntry[]>(
        "/finance/bank-statements",
        toQueryParams({ account_id: accountId })
      ),
    enabled: !!accountId,
  });
}

/** Import a bank statement CSV (multipart). */
export function useImportBankStatement() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    { imported: number },
    { account_id: string; file: File }
  >(
    {
      mutationFn: async ({ account_id, file }) => {
        const fd = new FormData();
        fd.append("account_id", account_id);
        fd.append("file", file);
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/finance/bank-statements/import`,
          { method: "POST", body: fd, credentials: "include" }
        );
        if (!res.ok) {
          throw new Error(await res.text());
        }
        return (await res.json()) as { imported: number };
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/bank-statements/import", method: "POST" }
  );
}

/** Match a bank statement entry to a GL entry. */
export function useMatchStatement() {
  const queryClient = useQueryClient();
  return useOfflineMutation<
    BankStatementEntry,
    { statement_id: string; entry_id: string }
  >(
    {
      mutationFn: ({ statement_id, entry_id }) =>
        apiClient.post<BankStatementEntry>(
          `/finance/bank-statements/${statement_id}/match`,
          { entry_id },
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/bank-statements/match", method: "POST" }
  );
}

/** Reconciliation summary for a cash account in a period. */
export function useReconciliation(accountId: string, periodId: string) {
  return useOfflineQuery<ReconciliationSummary>({
    queryKey: ["finance", "reconciliation", accountId, periodId],
    queryFn: () =>
      apiClient.get<ReconciliationSummary>(
        `/finance/reconciliation/${accountId}`,
        toQueryParams({ period_id: periodId })
      ),
    enabled: !!accountId,
  });
}

// ── Fixed assets / Depreciation ────────────────────────────────────────────

/** List fixed assets. */
export function useFixedAssets() {
  return useOfflineQuery<FixedAsset[]>({
    queryKey: ["finance", "fixed-assets"],
    queryFn: () =>
      apiClient.get<ListResponse<FixedAsset>>("/finance/fixed-assets").then(listItems),
  });
}

/** Create a fixed asset. */
export function useCreateFixedAsset() {
  const queryClient = useQueryClient();
  return useOfflineMutation<FixedAsset, FixedAssetCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<FixedAsset>("/finance/fixed-assets", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "fixed-assets"] });
      },
    },
    { url: "/finance/fixed-assets", method: "POST" }
  );
}

/** Run monthly depreciation (posts journal). */
export function useRunDepreciation() {
  const queryClient = useQueryClient();
  return useOfflineMutation<{ posted: number }, { period_id?: string }>(
    {
      mutationFn: (data) =>
        apiClient.post<{ posted: number }>(
          "/finance/depreciation/run",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/depreciation/run", method: "POST" }
  );
}

// ── Tax rates ──────────────────────────────────────────────────────────────

/** List tax rates. */
export function useTaxRates() {
  return useOfflineQuery<TaxRate[]>({
    queryKey: ["finance", "tax-rates"],
    queryFn: () => apiClient.get<TaxRate[]>("/finance/tax-rates"),
  });
}

/** Create a tax rate. */
export function useCreateTaxRate() {
  const queryClient = useQueryClient();
  return useOfflineMutation<TaxRate, TaxRateCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<TaxRate>("/finance/tax-rates", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "tax-rates"] });
      },
    },
    { url: "/finance/tax-rates", method: "POST" }
  );
}

// ── Budgets ────────────────────────────────────────────────────────────────

/** List budgets. */
export function useBudgets() {
  return useOfflineQuery<Budget[]>({
    queryKey: ["finance", "budgets"],
    queryFn: () =>
      apiClient.get<ListResponse<Budget>>("/finance/budgets").then(listItems),
  });
}

/** Create a budget line. */
export function useCreateBudget() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Budget, BudgetCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Budget>("/finance/budgets", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/budgets", method: "POST" }
  );
}

// ── Recurring transactions ─────────────────────────────────────────────────

/** List recurring transactions. */
export function useRecurring() {
  return useOfflineQuery<RecurringTransaction[]>({
    queryKey: ["finance", "recurring"],
    queryFn: () => apiClient.get<RecurringTransaction[]>("/finance/recurring"),
  });
}

/** Create a recurring transaction template. */
export function useCreateRecurring() {
  const queryClient = useQueryClient();
  return useOfflineMutation<RecurringTransaction, RecurringTransactionCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<RecurringTransaction>(
          "/finance/recurring",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance", "recurring"] });
      },
    },
    { url: "/finance/recurring", method: "POST" }
  );
}

/** Manually post a recurring transaction now. */
export function usePostRecurringNow() {
  const queryClient = useQueryClient();
  return useOfflineMutation<Transaction, { id: string }>(
    {
      mutationFn: ({ id }) =>
        apiClient.post<Transaction>(
          `/finance/recurring/${id}/post-now`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["finance"] });
      },
    },
    { url: "/finance/recurring/post-now", method: "POST" }
  );
}
