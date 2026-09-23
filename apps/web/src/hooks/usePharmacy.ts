"use client";

import { useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import { drugLookupKey, drugStockLevel, pickStockMatch } from "@/lib/drugStock";
import type {
  PharmacyQueueResponse,
  Dispensing,
  DispenseRequest,
  InventoryListResponse,
  PharmacyItem,
  PharmacyItemCreate,
  PharmacyItemUpdate,
  StockAlert,
  StockTransaction,
  StockReceiptRequest,
  StockAdjustmentRequest,
} from "@aifya/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Queue ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching the pharmacy dispensing queue.
 *
 * @returns Query result with pending prescriptions
 */
export function usePharmacyQueue() {
  return useOfflineQuery<PharmacyQueueResponse>({
    queryKey: ["pharmacy", "queue"],
    queryFn: () => apiClient.get<PharmacyQueueResponse>("/pharmacy/queue"),
    refetchInterval: 15_000,
  });
}

// ── Dispensing ───────────────────────────────────────────────────────────

/**
 * Hook for dispensing a prescription.
 *
 * @returns Mutation for dispensing
 */
export function useDispense() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Dispensing, DispenseRequest>(
    {
      mutationFn: (data: DispenseRequest) =>
        apiClient.post<Dispensing>("/pharmacy/dispense", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/pharmacy/dispense`, method: "POST" }
  );
}

// ── Inventory ────────────────────────────────────────────────────────────

/**
 * Hook for fetching pharmacy inventory with search and pagination.
 *
 * @param query - Optional search string
 * @param page - Page number
 * @param pageSize - Items per page
 * @returns Query result with inventory list
 */
export function usePharmacyInventory(
  query?: string,
  page: number = 1,
  pageSize: number = 50
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (query) {
    params["q"] = query;
  }

  return useOfflineQuery<InventoryListResponse>({
    queryKey: ["pharmacy", "inventory", query ?? "", page, pageSize],
    queryFn: () =>
      apiClient.get<InventoryListResponse>("/pharmacy/inventory", params),
  });
}

/**
 * Hook for checking whether a prescribed drug is available in the pharmacy.
 *
 * Prescribers must be able to see stock on hand before they commit a patient
 * to a medicine, so this runs the inventory search on the drug's leading word
 * and classifies the best match. It is the read-only counterpart of the
 * dispensing counter's stock lookup.
 *
 * @param drugName - Prescribed drug name
 * @param genericName - Prescribed generic name, used when the brand is unknown
 * @returns Matched inventory item, its stock level and a checking flag
 */
export function useDrugStock(
  drugName?: string | null,
  genericName?: string | null,
) {
  const key = drugLookupKey(drugName) || drugLookupKey(genericName);

  const query = useOfflineQuery<InventoryListResponse>({
    queryKey: ["pharmacy", "inventory", "drug-stock", key],
    queryFn: () =>
      apiClient.get<InventoryListResponse>("/pharmacy/inventory", {
        q: key,
        page: "1",
        page_size: "50",
      }),
    enabled: key.length >= 3,
    staleTime: 60_000,
  });

  const item = useMemo(
    () => pickStockMatch(query.data?.items, drugName, genericName),
    [query.data, drugName, genericName],
  );

  return {
    item,
    level: drugStockLevel(item),
    isChecking: key.length >= 3 && query.isLoading,
    refetch: query.refetch,
  };
}

/**
 * Hook for creating a pharmacy inventory item.
 *
 * @returns Mutation for creating inventory item
 */
export function useCreatePharmacyItem() {
  const queryClient = useQueryClient();

  return useOfflineMutation<PharmacyItem, PharmacyItemCreate>(
    {
      mutationFn: (data: PharmacyItemCreate) =>
        apiClient.post<PharmacyItem>("/pharmacy/inventory", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy", "inventory"] });
      },
    },
    { url: `${API_URL}/pharmacy/inventory`, method: "POST" }
  );
}

/**
 * Hook for updating a pharmacy inventory item.
 *
 * @param itemId - PharmacyItem UUID
 * @returns Mutation for updating inventory item
 */
export function useUpdatePharmacyItem(itemId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<PharmacyItem, PharmacyItemUpdate>(
    {
      mutationFn: (data: PharmacyItemUpdate) =>
        apiClient.patch<PharmacyItem>(
          `/pharmacy/inventory/${itemId}`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy", "inventory"] });
      },
    },
    { url: `${API_URL}/pharmacy/inventory/${itemId}`, method: "PATCH" }
  );
}

// ── Stock ────────────────────────────────────────────────────────────────

/**
 * Hook for receiving stock.
 *
 * @returns Mutation for stock receipt
 */
export function useReceiveStock() {
  const queryClient = useQueryClient();

  return useOfflineMutation<StockTransaction, StockReceiptRequest>(
    {
      mutationFn: (data: StockReceiptRequest) =>
        apiClient.post<StockTransaction>("/pharmacy/stock/receive", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    { url: `${API_URL}/pharmacy/stock/receive`, method: "POST" }
  );
}

/**
 * Hook for adjusting stock.
 *
 * @returns Mutation for stock adjustment
 */
export function useAdjustStock() {
  const queryClient = useQueryClient();

  return useOfflineMutation<StockTransaction, StockAdjustmentRequest>(
    {
      mutationFn: (data: StockAdjustmentRequest) =>
        apiClient.post<StockTransaction>("/pharmacy/stock/adjust", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    { url: `${API_URL}/pharmacy/stock/adjust`, method: "POST" }
  );
}

// ── Alerts ───────────────────────────────────────────────────────────────

/**
 * Hook for fetching stock alerts (low stock, expiring, expired).
 *
 * @returns Query result with stock alerts
 */
export function useStockAlerts() {
  return useOfflineQuery<StockAlert[]>({
    queryKey: ["pharmacy", "alerts"],
    queryFn: () => apiClient.get<StockAlert[]>("/pharmacy/alerts"),
    refetchInterval: 60_000,
  });
}
