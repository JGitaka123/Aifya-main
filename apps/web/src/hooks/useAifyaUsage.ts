"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";

const API_URL = "/api/v1";

// ── Types ────────────────────────────────────────────────────────────────

/** The patient-day rate the hospital is billed at. */
export interface AifyaUsageConfig {
  rate_cents: number;
  currency: string;
  notes: string | null;
  is_configured: boolean;
}

/** One day of billable usage. */
export interface AifyaUsageDay {
  usage_date: string;
  registration_patients: number;
  emergency_patients: number;
  inpatient_patients: number;
  total_billable_patients: number;
  rate_cents: number;
  currency: string;
  amount_cents: number;
  is_finalized: boolean;
  computed_at: string | null;
}

/** Daily usage over a range, with the range totals. */
export interface AifyaUsageRange {
  start_date: string;
  end_date: string;
  currency: string;
  rate_cents: number;
  total_patient_days: number;
  registration_patient_days: number;
  emergency_patient_days: number;
  inpatient_patient_days: number;
  total_amount_cents: number;
  days: AifyaUsageDay[];
}

/** Aifya's monthly invoice to the hospital. */
export interface AifyaUsageInvoice {
  id: string;
  invoice_number: string;
  period_year: number;
  period_month: number;
  period_label: string;
  status: string;
  patient_days: number;
  registration_patient_days: number;
  emergency_patient_days: number;
  inpatient_patient_days: number;
  rate_cents: number | null;
  amount_cents: number;
  paid_cents: number;
  balance_cents: number;
  currency: string;
  issued_at: string | null;
  due_at: string | null;
  paid_at: string | null;
  payment_reference: string | null;
  notes: string | null;
}

/** The hospital's Aifya bill for one calendar month. */
export interface AifyaUsageMonth {
  year: number;
  month: number;
  period_label: string;
  facility_id: string;
  facility_name: string;
  currency: string;
  rate_cents: number;
  rate_is_confirmed: boolean;
  rate_changed_mid_month: boolean;
  total_patient_days: number;
  registration_patient_days: number;
  emergency_patient_days: number;
  inpatient_patient_days: number;
  total_amount_cents: number;
  is_finalized: boolean;
  invoice: AifyaUsageInvoice | null;
  days: AifyaUsageDay[];
}

export interface AifyaUsageConfigUpdate {
  rate_cents: number;
  currency?: string;
  notes?: string | null;
}

export interface AifyaUsageAccrualRequest {
  start_date: string;
  end_date: string;
  force?: boolean;
}

export interface AifyaUsageFinalizeRequest {
  year: number;
  month: number;
}

export interface AifyaUsageInvoiceCreate {
  year: number;
  month: number;
  notes?: string | null;
}

export interface AifyaUsageInvoicePayment {
  amount_cents: number;
  reference?: string | null;
}

/** An invoice id paired with the amount being received against it. */
export interface AifyaUsageInvoicePaymentRequest extends AifyaUsageInvoicePayment {
  id: string;
}

// ── Queries ──────────────────────────────────────────────────────────────

/**
 * Read the patient-day rate this facility is billed at.
 *
 * @returns Query result with the current rate
 */
export function useAifyaUsageConfig() {
  return useOfflineQuery<AifyaUsageConfig>({
    queryKey: ["aifya-usage", "config"],
    queryFn: () => apiClient.get<AifyaUsageConfig>("/aifya-usage/config"),
  });
}

/**
 * The hospital's Aifya bill for one month, read from the stored ledger.
 *
 * @param year - Calendar year
 * @param month - Calendar month, 1-12
 * @returns Query result with the month's usage
 */
export function useAifyaUsageSummary(year: number, month: number) {
  return useOfflineQuery<AifyaUsageMonth>({
    queryKey: ["aifya-usage", "summary", year, month],
    queryFn: () =>
      apiClient.get<AifyaUsageMonth>("/aifya-usage/summary", {
        year: String(year),
        month: String(month),
      }),
  });
}

// ── Mutations ────────────────────────────────────────────────────────────

/**
 * Recompute the usage ledger for a range of days.
 *
 * Idempotent, so it is safe to call every time the report is opened: the same
 * encounters always produce the same figures.
 *
 * @returns Mutation returning the refreshed range
 */
export function useAccrueAifyaUsage() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageRange, AifyaUsageAccrualRequest>(
    {
      mutationFn: (data) =>
        apiClient.post<AifyaUsageRange>("/aifya-usage/accrue", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    { url: `${API_URL}/aifya-usage/accrue`, method: "POST" },
  );
}

/**
 * Change the patient-day rate. Applies to days computed from now on.
 *
 * @returns Mutation updating the rate
 */
export function useUpdateAifyaUsageConfig() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageConfig, AifyaUsageConfigUpdate>(
    {
      mutationFn: (data) =>
        apiClient.put<AifyaUsageConfig>("/aifya-usage/config", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    { url: `${API_URL}/aifya-usage/config`, method: "PUT" },
  );
}

/**
 * Close a month so its figures stop moving.
 *
 * @returns Mutation returning the closed month
 */
export function useFinalizeAifyaUsage() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageMonth, AifyaUsageFinalizeRequest>(
    {
      mutationFn: (data) =>
        apiClient.post<AifyaUsageMonth>("/aifya-usage/finalize", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    { url: `${API_URL}/aifya-usage/finalize`, method: "POST" },
  );
}

/**
 * Raise, or refresh, the Aifya invoice for a calendar month.
 *
 * Idempotent while the invoice is still a draft, so re-opening the page can
 * never raise a second invoice for the same month.
 *
 * @returns Mutation returning the draft invoice
 */
export function useRaiseAifyaUsageInvoice() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageInvoice, AifyaUsageInvoiceCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<AifyaUsageInvoice>("/aifya-usage/invoices", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    { url: `${API_URL}/aifya-usage/invoices`, method: "POST" },
  );
}

/**
 * Issue a draft Aifya invoice, starting its payment term.
 *
 * @returns Mutation taking the invoice id and returning the issued invoice
 */
export function useIssueAifyaUsageInvoice() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageInvoice, string>(
    {
      mutationFn: (id) =>
        apiClient.post<AifyaUsageInvoice>(
          `/aifya-usage/invoices/${id}/issue`,
          {},
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    {
      url: (id) => `${API_URL}/aifya-usage/invoices/${id}/issue`,
      method: "POST",
      body: () => ({}),
    },
  );
}

/**
 * Record money received against an issued Aifya invoice.
 *
 * The invoice only reads paid once the payments cover it in full.
 *
 * @returns Mutation returning the updated invoice
 */
export function usePayAifyaUsageInvoice() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageInvoice, AifyaUsageInvoicePaymentRequest>(
    {
      mutationFn: ({ id, amount_cents, reference }) =>
        apiClient.post<AifyaUsageInvoice>(
          `/aifya-usage/invoices/${id}/payment`,
          { amount_cents, reference },
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    {
      url: (v) => `${API_URL}/aifya-usage/invoices/${v.id}/payment`,
      method: "POST",
      body: (v) => ({ amount_cents: v.amount_cents, reference: v.reference }),
    },
  );
}

/**
 * Void an Aifya invoice that has taken no money.
 *
 * @returns Mutation taking the invoice id and returning the voided invoice
 */
export function useVoidAifyaUsageInvoice() {
  const qc = useQueryClient();
  return useOfflineMutation<AifyaUsageInvoice, string>(
    {
      mutationFn: (id) =>
        apiClient.post<AifyaUsageInvoice>(
          `/aifya-usage/invoices/${id}/void`,
          {},
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["aifya-usage"] });
      },
    },
    {
      url: (id) => `${API_URL}/aifya-usage/invoices/${id}/void`,
      method: "POST",
      body: () => ({}),
    },
  );
}
