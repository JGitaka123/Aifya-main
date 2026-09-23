/** Pharmacy inventory item. */
export interface PharmacyItem {
  id: string;
  facility_id: string;
  drug_code: string;
  drug_name: string;
  generic_name: string | null;
  atc_code: string | null;
  is_keml: boolean;
  dosage_form: string | null;
  strength: string | null;
  batch_number: string | null;
  current_quantity: number;
  unit_of_measure: string;
  reorder_level: number;
  max_stock_level: number | null;
  buying_price_cents: number | null;
  selling_price_cents: number | null;
  expiry_date: string | null;
  manufacturer: string | null;
  supplier: string | null;
  storage_conditions: string | null;
  shelf_location: string | null;
  is_active: boolean;
  created_at: string;
}

/** Payload for creating a pharmacy item. */
export interface PharmacyItemCreate {
  drug_code: string;
  drug_name: string;
  generic_name?: string | null;
  atc_code?: string | null;
  is_keml?: boolean;
  dosage_form?: string | null;
  strength?: string | null;
  batch_number?: string | null;
  current_quantity?: number;
  unit_of_measure?: string;
  reorder_level?: number;
  max_stock_level?: number | null;
  buying_price_cents?: number | null;
  selling_price_cents?: number | null;
  expiry_date?: string | null;
  manufacturer?: string | null;
  supplier?: string | null;
  storage_conditions?: string | null;
  shelf_location?: string | null;
}

/** Payload for updating a pharmacy item. */
export interface PharmacyItemUpdate {
  drug_name?: string;
  generic_name?: string | null;
  is_keml?: boolean;
  current_quantity?: number;
  reorder_level?: number;
  selling_price_cents?: number | null;
  expiry_date?: string | null;
  shelf_location?: string | null;
  is_active?: boolean;
}

/** Paginated inventory list response. */
export interface InventoryListResponse {
  items: PharmacyItem[];
  total: number;
  page: number;
  page_size: number;
}

/** A pending prescription in the pharmacy queue. */
export interface PharmacyQueueItem {
  prescription_id: string;
  encounter_id: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  drug_name: string;
  generic_name: string | null;
  is_keml: boolean;
  dosage: string;
  route: string;
  frequency: string;
  duration_days: number | null;
  quantity: number | null;
  instructions: string | null;
  prescriber_id: string;
  status: string;
  created_at: string;
}

/** Pharmacy queue response. */
export interface PharmacyQueueResponse {
  items: PharmacyQueueItem[];
  total: number;
}

/** Dispensing record. */
export interface Dispensing {
  id: string;
  prescription_id: string;
  patient_id: string;
  pharmacy_item_id: string | null;
  dispensed_by: string;
  drug_name: string;
  quantity_requested: number;
  quantity_dispensed: number;
  substitution_drug: string | null;
  substitution_reason: string | null;
  dosage_instructions: string | null;
  counseling_done: boolean;
  counseling_notes: string | null;
  status: string;
  unit_price_cents: number | null;
  total_price_cents: number | null;
  payment_status: string;
  payment_method: string | null;
  dispensed_at: string;
  created_at: string;
}

/** Payload for dispensing a prescription. */
export interface DispenseRequest {
  prescription_id: string;
  patient_id: string;
  pharmacy_item_id?: string | null;
  quantity_dispensed: number;
  substitution_drug?: string | null;
  substitution_reason?: string | null;
  dosage_instructions?: string | null;
  counseling_done?: boolean;
  counseling_notes?: string | null;
  payment_method?: string | null;
}

/** Stock alert (low stock, expiry, etc.). */
export interface StockAlert {
  item_id: string;
  drug_name: string;
  drug_code: string;
  current_quantity: number;
  reorder_level: number;
  expiry_date: string | null;
  alert_type: "low_stock" | "expiring_soon" | "expired" | "out_of_stock";
}

/** Payload for receiving stock. */
export interface StockReceiptRequest {
  pharmacy_item_id: string;
  quantity: number;
  batch_number?: string | null;
  expiry_date?: string | null;
  unit_cost_cents?: number | null;
  reference_number?: string | null;
  reason?: string | null;
}

/** Payload for stock adjustment. */
export interface StockAdjustmentRequest {
  pharmacy_item_id: string;
  quantity_change: number;
  reason: string;
  reference_number?: string | null;
}

/** Stock transaction record. */
export interface StockTransaction {
  id: string;
  pharmacy_item_id: string;
  dispensing_id: string | null;
  transaction_type: string;
  quantity_change: number;
  quantity_before: number;
  quantity_after: number;
  reference_number: string | null;
  reason: string | null;
  unit_cost_cents: number | null;
  batch_number: string | null;
  expiry_date: string | null;
  created_at: string;
}
