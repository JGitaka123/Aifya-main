/**
 * M-Pesa Daraja integration types.
 * STK Push payments, callbacks, and transaction tracking.
 */

/** STK Push payment request. */
export interface STKPushApiRequest {
  /** Customer phone number, e.g. 0712345678 or +254712345678. */
  phone_number: string;
  /** Whole shillings the customer will be asked for. */
  amount_kes: number;
  /** Invoice the money is posted against. */
  invoice_id?: string | null;
  /** Patient the money belongs to. */
  patient_id?: string | null;
  /** Account reference shown on the M-Pesa SMS (defaults to the invoice). */
  reference?: string | null;
  description?: string;
  /** Ordered service being paid for: lab_order, imaging_order, prescription. */
  reference_type?: string | null;
  /** UUID of the lab order, imaging order or prescription being paid for. */
  reference_id?: string | null;
}

/** STK Push API response. */
export interface STKPushResponse {
  merchant_request_id: string;
  checkout_request_id: string;
  response_code: string;
  response_description: string;
  customer_message: string;
  success: boolean;
  error: string | null;
}

/**
 * Local state of an STK Push, read from Aifya's own records.
 *
 * Daraja's query endpoint reports what Safaricom thinks happened. This
 * reports whether the money actually reached the patient's bill, which is
 * what decides whether it is safe to tell the patient the payment succeeded.
 */
export interface STKRequestStatus {
  checkout_request_id: string;
  status: "pending" | "success" | "failed" | "timeout";
  result_code: number | null;
  result_desc: string | null;
  receipt_number: string | null;
  amount_kes: number;
  phone_number: string;
  invoice_id: string | null;
  invoice_number: string | null;
  payment_id: string | null;
  /** True once a payment exists against the invoice for this receipt. */
  recorded: boolean;
}

/** Transaction status query result. */
export interface MPesaTransactionStatus {
  result_code: number;
  result_desc: string;
  receipt_number: string | null;
}

/** M-Pesa configuration status. */
export interface MPesaStatus {
  configured: boolean;
  environment: string;
  shortcode: string;
}
