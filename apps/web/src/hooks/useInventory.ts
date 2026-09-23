"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  InventoryItemListResponse,
  InventoryItemResponse,
  InventoryItemCreate,
  TransactionListResponse,
  InventoryTransactionCreate,
  InventoryTransactionResponse,
  SupplierListResponse,
  SupplierCreate,
  SupplierResponse,
  PurchaseOrderListResponse,
  PurchaseOrderResponse,
  PurchaseOrderCreate,
  InventorySummary,
} from "@aifya/shared";
import { apiFetch } from "@/lib/api";
import { idempotentApiFetch } from "@/hooks/idempotentApiFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const INV_KEYS = {
  all: ["inventory"] as const,
  summary: () => [...INV_KEYS.all, "summary"] as const,
  items: (category?: string, search?: string) => [...INV_KEYS.all, "items", category, search] as const,
  item: (id: string) => [...INV_KEYS.all, "item", id] as const,
  transactions: (itemId?: string) => [...INV_KEYS.all, "transactions", itemId] as const,
  suppliers: () => [...INV_KEYS.all, "suppliers"] as const,
  pos: (status?: string) => [...INV_KEYS.all, "pos", status] as const,
  po: (id: string) => [...INV_KEYS.all, "po", id] as const,
};

/** Get inventory summary. */
export function useInventorySummary() {
  return useOfflineQuery<InventorySummary>({
    queryKey: INV_KEYS.summary(),
    queryFn: () => apiFetch("/api/v1/inventory/summary"),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

/** Get inventory items. */
export function useInventoryItems(category?: string, search?: string, lowStock?: boolean) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (search) params.set("search", search);
  if (lowStock) params.set("low_stock", "true");
  const qs = params.toString();

  return useOfflineQuery<InventoryItemListResponse>({
    queryKey: INV_KEYS.items(category, search),
    queryFn: () => apiFetch(`/api/v1/inventory/items${qs ? `?${qs}` : ""}`),
    staleTime: 30_000,
  });
}

/** Get a single inventory item. */
export function useInventoryItem(itemId: string) {
  return useOfflineQuery<InventoryItemResponse>({
    queryKey: INV_KEYS.item(itemId),
    queryFn: () => apiFetch(`/api/v1/inventory/items/${itemId}`),
    enabled: !!itemId,
  });
}

/** Create inventory item. */
export function useCreateInventoryItem() {
  const qc = useQueryClient();
  return useOfflineMutation<InventoryItemResponse, InventoryItemCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/inventory/items", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INV_KEYS.all }),
    },
    { url: `${API_URL}/inventory/items`, method: "POST" }
  );
}

/** Get transactions. */
export function useInventoryTransactions(itemId?: string) {
  const params = itemId ? `?item_id=${itemId}` : "";
  return useOfflineQuery<TransactionListResponse>({
    queryKey: INV_KEYS.transactions(itemId),
    queryFn: () => apiFetch(`/api/v1/inventory/transactions${params}`),
    staleTime: 15_000,
  });
}

/** Create transaction. */
export function useCreateTransaction() {
  const qc = useQueryClient();
  return useOfflineMutation<InventoryTransactionResponse, InventoryTransactionCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/inventory/transactions", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INV_KEYS.all }),
    },
    { url: `${API_URL}/inventory/transactions`, method: "POST" }
  );
}

/** Get suppliers. */
export function useSuppliers() {
  return useOfflineQuery<SupplierListResponse>({
    queryKey: INV_KEYS.suppliers(),
    queryFn: () => apiFetch("/api/v1/inventory/suppliers"),
    staleTime: 60_000,
  });
}

/** Create supplier. */
export function useCreateSupplier() {
  const qc = useQueryClient();
  return useOfflineMutation<SupplierResponse, SupplierCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/inventory/suppliers", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INV_KEYS.suppliers() }),
    },
    { url: `${API_URL}/inventory/suppliers`, method: "POST" }
  );
}

/** Get purchase orders. */
export function usePurchaseOrders(status?: string) {
  const params = status ? `?status=${status}` : "";
  return useOfflineQuery<PurchaseOrderListResponse>({
    queryKey: INV_KEYS.pos(status),
    queryFn: () => apiFetch(`/api/v1/inventory/purchase-orders${params}`),
    staleTime: 30_000,
  });
}

/** Get a single PO. */
export function usePurchaseOrder(poId: string) {
  return useOfflineQuery<PurchaseOrderResponse>({
    queryKey: INV_KEYS.po(poId),
    queryFn: () => apiFetch(`/api/v1/inventory/purchase-orders/${poId}`),
    enabled: !!poId,
  });
}

/** Create purchase order. */
export function useCreatePurchaseOrder() {
  const qc = useQueryClient();
  return useOfflineMutation<PurchaseOrderResponse, PurchaseOrderCreate>(
    {
      mutationFn: (data) => idempotentApiFetch("/api/v1/inventory/purchase-orders", { method: "POST", body: JSON.stringify(data) }),
      onSuccess: () => qc.invalidateQueries({ queryKey: INV_KEYS.all }),
    },
    { url: `${API_URL}/inventory/purchase-orders`, method: "POST" }
  );
}
