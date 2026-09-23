/** Inventory item category */
export type InventoryCategory = "consumable" | "equipment" | "surgical" | "linen" | "stationery" | "reagent" | "other";

/** Transaction type */
export type TransactionType = "receipt" | "issue" | "return" | "adjustment" | "transfer" | "write_off" | "opening";

/** Stock status */
export type StockStatus = "ok" | "low" | "out";

/** Purchase order status */
export type POStatus = "draft" | "submitted" | "approved" | "ordered" | "partial" | "received" | "cancelled";

/** Inventory item creation request */
export interface InventoryItemCreate {
  name: string;
  description?: string | null;
  category: InventoryCategory;
  sub_category?: string | null;
  unit_of_measure: string;
  unit_cost?: number;
  reorder_level?: number;
  reorder_quantity?: number;
  max_stock?: number | null;
  store_location?: string | null;
  department_id?: string | null;
  specifications?: Record<string, unknown> | null;
}

/** Inventory item response */
export interface InventoryItemResponse {
  id: string;
  item_code: string;
  name: string;
  description: string | null;
  category: string;
  sub_category: string | null;
  unit_of_measure: string;
  unit_cost: number;
  current_stock: number;
  reorder_level: number;
  reorder_quantity: number;
  max_stock: number | null;
  store_location: string | null;
  department_id: string | null;
  is_active: boolean;
  specifications: Record<string, unknown> | null;
  created_at: string;
}

/** Inventory item in list view */
export interface InventoryItemListItem {
  id: string;
  item_code: string;
  name: string;
  category: string;
  unit_of_measure: string;
  unit_cost: number;
  current_stock: number;
  reorder_level: number;
  is_active: boolean;
  stock_status: StockStatus;
}

/** Inventory item list response */
export interface InventoryItemListResponse {
  items: InventoryItemListItem[];
  total: number;
}

/** Transaction creation request */
export interface InventoryTransactionCreate {
  item_id: string;
  transaction_type: TransactionType;
  quantity: number;
  unit_cost?: number;
  department_id?: string | null;
  issued_to?: string | null;
  reason?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
}

/** Transaction response */
export interface InventoryTransactionResponse {
  id: string;
  item_id: string;
  transaction_type: string;
  quantity: number;
  balance_after: number;
  unit_cost: number;
  total_cost: number;
  transaction_date: string;
  reference_number: string | null;
  department_id: string | null;
  issued_to: string | null;
  reason: string | null;
  batch_number: string | null;
  expiry_date: string | null;
}

/** Transaction list response */
export interface TransactionListResponse {
  items: InventoryTransactionResponse[];
  total: number;
}

/** Supplier creation request */
export interface SupplierCreate {
  name: string;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  kra_pin?: string | null;
  payment_terms?: string | null;
  category?: string | null;
  notes?: string | null;
}

/** Supplier response */
export interface SupplierResponse {
  id: string;
  name: string;
  supplier_code: string | null;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  kra_pin: string | null;
  payment_terms: string | null;
  category: string | null;
  rating: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

/** Supplier list response */
export interface SupplierListResponse {
  items: SupplierResponse[];
  total: number;
}

/** PO line item create */
export interface PurchaseOrderItemCreate {
  item_id: string;
  quantity_ordered: number;
  unit_cost: number;
}

/** PO creation request */
export interface PurchaseOrderCreate {
  supplier_id: string;
  expected_delivery?: string | null;
  delivery_address?: string | null;
  notes?: string | null;
  items: PurchaseOrderItemCreate[];
}

/** PO line item response */
export interface POItemResponse {
  id: string;
  item_id: string;
  item_name: string | null;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: number;
  total_cost: number;
}

/** PO response */
export interface PurchaseOrderResponse {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_name: string | null;
  order_date: string;
  expected_delivery: string | null;
  status: string;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  approved_by: string | null;
  approved_at: string | null;
  delivery_address: string | null;
  notes: string | null;
  items: POItemResponse[];
  created_at: string;
}

/** PO list item */
export interface PurchaseOrderListItem {
  id: string;
  po_number: string;
  supplier_name: string | null;
  order_date: string;
  status: string;
  total_amount: number;
  item_count: number;
}

/** PO list response */
export interface PurchaseOrderListResponse {
  items: PurchaseOrderListItem[];
  total: number;
}

/** Receive item request */
export interface ReceiveItemRequest {
  po_item_id: string;
  quantity_received: number;
  batch_number?: string | null;
  expiry_date?: string | null;
}

/** Inventory summary */
export interface InventorySummary {
  total_items: number;
  active_items: number;
  low_stock_items: number;
  out_of_stock_items: number;
  total_stock_value: number;
  pending_orders: number;
  suppliers_count: number;
  transactions_today: number;
}
