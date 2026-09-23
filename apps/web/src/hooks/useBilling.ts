"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  BillingSummary,
  InvoiceListResponse,
  InvoiceDetail,
  InvoiceResponse,
  InvoiceCreate,
  PaymentResponseType,
  PaymentCreate,
  InvoiceWaiveRequest,
  ServiceChargeListResponse,
  ServicePaymentRequest,
  ServicePaymentResponse,
} from "@aifya/shared";

// ── Dashboard Summary ───────────────────────────────────────────────────────

/**
 * Hook for fetching the billing dashboard summary.
 *
 * @returns Query result with billing summary
 */
export function useBillingSummary() {
  return useOfflineQuery<BillingSummary>({
    queryKey: ["billing", "summary"],
    queryFn: () => apiClient.get<BillingSummary>("/billing/summary"),
    refetchInterval: 30_000,
  });
}

// ── Invoice List ────────────────────────────────────────────────────────────

/**
 * Hook for fetching paginated invoice list.
 *
 * @param statusFilter - Optional status filter
 * @param page - Page number
 * @param pageSize - Items per page
 * @param patientId - Restrict the list to one patient's invoices
 * @returns Query result with invoice list
 */
export function useInvoiceList(
  statusFilter?: string,
  page: number = 1,
  pageSize: number = 50,
  patientId?: string
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (statusFilter) {
    params["status"] = statusFilter;
  }
  if (patientId) {
    params["patient_id"] = patientId;
  }

  return useOfflineQuery<InvoiceListResponse>({
    queryKey: [
      "billing",
      "invoices",
      statusFilter ?? "",
      page,
      pageSize,
      patientId ?? "",
    ],
    queryFn: () =>
      apiClient.get<InvoiceListResponse>("/billing/invoices", params),
    refetchInterval: 15_000,
  });
}

// ── Invoice Detail ──────────────────────────────────────────────────────────

/**
 * Hook for fetching a single invoice with items.
 *
 * @param invoiceId - Invoice UUID
 * @returns Query result with invoice detail
 */
export function useInvoiceDetail(invoiceId: string) {
  return useOfflineQuery<InvoiceDetail>({
    queryKey: ["billing", "invoices", invoiceId],
    queryFn: () =>
      apiClient.get<InvoiceDetail>(`/billing/invoices/${invoiceId}`),
    enabled: !!invoiceId,
  });
}

// ── Create Invoice ──────────────────────────────────────────────────────────

/**
 * Hook for creating a new invoice with line items.
 *
 * @returns Mutation for invoice creation
 */
export function useCreateInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<InvoiceResponse, InvoiceCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<InvoiceResponse>(
          "/billing/invoices",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    { url: "/api/v1/billing/invoices", method: "POST" }
  );
}

// ── Finalize Invoice ────────────────────────────────────────────────────────

/**
 * Hook for finalizing (locking) an invoice.
 *
 * @returns Mutation for finalization
 */
export function useFinalizeInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<InvoiceResponse, { invoice_id: string }>(
    {
      mutationFn: ({ invoice_id }) =>
        apiClient.post<InvoiceResponse>(
          `/billing/invoices/${invoice_id}/finalize`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: ({ invoice_id }) =>
        `/api/v1/billing/invoices/${invoice_id}/finalize`,
      method: "POST",
      body: () => ({}),
    }
  );
}

// ── Record Payment ──────────────────────────────────────────────────────────

/**
 * Hook for recording a payment against an invoice.
 *
 * @returns Mutation for payment recording
 */
export function useRecordPayment() {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    PaymentResponseType,
    PaymentCreate & { invoice_id: string }
  >(
    {
      mutationFn: ({ invoice_id, ...data }) =>
        apiClient.post<PaymentResponseType>(
          `/billing/invoices/${invoice_id}/pay`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: ({ invoice_id }) => `/api/v1/billing/invoices/${invoice_id}/pay`,
      method: "POST",
      body: ({ invoice_id, ...data }) => {
        void invoice_id;
        return data;
      },
    }
  );
}

// ── Waive Invoice ───────────────────────────────────────────────────────────

/**
 * Hook for waiving remaining invoice balance.
 *
 * @returns Mutation for waiver
 */
export function useWaiveInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    InvoiceResponse,
    InvoiceWaiveRequest & { invoice_id: string }
  >(
    {
      mutationFn: ({ invoice_id, ...data }) =>
        apiClient.post<InvoiceResponse>(
          `/billing/invoices/${invoice_id}/waive`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: ({ invoice_id }) => `/api/v1/billing/invoices/${invoice_id}/waive`,
      method: "POST",
      body: ({ invoice_id, ...data }) => {
        void invoice_id;
        return data;
      },
    }
  );
}

// ---- Point of sale: ordered services (lab, imaging, pharmacy) -------------

/**
 * Hook for the service charges on one visit.
 *
 * Covers lab requests, imaging studies and prescriptions, so the cashier can
 * see everything a doctor ordered before the patient reaches the service desk.
 *
 * @param encounterId - Encounter UUID
 * @param includePaid - Keep requests that are already settled
 * @returns Query result with the visit's charges
 */
export function useEncounterServiceCharges(
  encounterId: string,
  includePaid = false
) {
  return useOfflineQuery<ServiceChargeListResponse>({
    queryKey: ["billing", "pos", "encounters", encounterId, includePaid],
    queryFn: () =>
      apiClient.get<ServiceChargeListResponse>(
        `/billing/pos/encounters/${encounterId}/charges`,
        { include_paid: String(includePaid) }
      ),
    enabled: !!encounterId,
    refetchInterval: 15_000,
  });
}

/**
 * Hook for what a patient still owes across recent visits.
 *
 * This is the cashier's search: a patient walks up with a lab slip or a
 * prescription and the desk needs every request still outstanding.
 *
 * @param patientId - Patient UUID
 * @param includePaid - Keep requests that are already settled
 * @returns Query result with the patient's outstanding charges
 */
export function usePatientServiceCharges(
  patientId: string,
  includePaid = false
) {
  return useOfflineQuery<ServiceChargeListResponse>({
    queryKey: ["billing", "pos", "patients", patientId, includePaid],
    queryFn: () =>
      apiClient.get<ServiceChargeListResponse>(
        `/billing/pos/patients/${patientId}/charges`,
        { include_paid: String(includePaid) }
      ),
    enabled: !!patientId,
    refetchInterval: 15_000,
  });
}

/**
 * Hook for taking payment for an ordered service at the front desk.
 *
 * The API is idempotent per generated key, so a retry after a dropped response
 * cannot charge the patient twice. Naming a request settles exactly that
 * request; leaving it out settles the whole outstanding bill.
 *
 * @param encounterId - Encounter UUID
 * @returns Mutation returning the settled payment and its receipt URL
 */
export function useCollectServicePayment(encounterId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<ServicePaymentResponse, ServicePaymentRequest>(
    {
      mutationFn: (data: ServicePaymentRequest) =>
        apiClient.post<ServicePaymentResponse>(
          `/billing/pos/encounters/${encounterId}/pay`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    {
      url: `/api/v1/billing/pos/encounters/${encounterId}/pay`,
      method: "POST",
    }
  );
}
