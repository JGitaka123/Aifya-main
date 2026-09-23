"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Box,
  ClipboardList,
  Package,
  ShoppingCart,
  Truck,
  Users,
  Warehouse,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useInventorySummary, useInventoryItems, usePurchaseOrders, useSuppliers } from "@/hooks/useInventory";
import { cn } from "@/lib/utils";

const STOCK_STYLES: Record<string, string> = {
  ok: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  low: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  out: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

const PO_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  approved: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  ordered: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  partial: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  received: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** Format KES cents to readable currency. */
function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2 })}`;
}

export default function InventoryPage() {
  const t = useTranslations("inventory");
  const [tab, setTab] = useState<"items" | "orders" | "suppliers">("items");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data: summary, isLoading: summaryLoading } = useInventorySummary();
  const { data: items, isLoading: itemsLoading } = useInventoryItems(
    categoryFilter || undefined,
    search || undefined
  );
  const { data: orders, isLoading: ordersLoading } = usePurchaseOrders();
  const { data: suppliers } = useSuppliers();

  const summaryCards = [
    { label: t("totalItems"), value: summary?.total_items ?? 0, icon: Package, color: "text-blue-600 dark:text-blue-400" },
    { label: t("activeItems"), value: summary?.active_items ?? 0, icon: Box, color: "text-green-600 dark:text-green-400" },
    { label: t("lowStock"), value: summary?.low_stock_items ?? 0, icon: AlertTriangle, color: "text-amber-600 dark:text-amber-400" },
    { label: t("outOfStock"), value: summary?.out_of_stock_items ?? 0, icon: Warehouse, color: "text-red-600 dark:text-red-400" },
    { label: t("stockValue"), value: summary ? formatKES(summary.total_stock_value) : "—", icon: ClipboardList, color: "text-purple-600 dark:text-purple-400" },
    { label: t("pendingOrders"), value: summary?.pending_orders ?? 0, icon: ShoppingCart, color: "text-indigo-600 dark:text-indigo-400" },
    { label: t("suppliers"), value: summary?.suppliers_count ?? 0, icon: Truck, color: "text-cyan-600 dark:text-cyan-400" },
    { label: t("transactionsToday"), value: summary?.transactions_today ?? 0, icon: Users, color: "text-teal-600 dark:text-teal-400" },
  ];

  const categories = ["", "consumable", "equipment", "surgical", "linen", "stationery", "reagent", "other"];
  const tabs = ["items", "orders", "suppliers"] as const;

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]"
          >
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-1 text-lg font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {tabs.map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t_
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`tab.${t_}`)}
          </button>
        ))}
      </div>

      {/* Items Tab */}
      {tab === "items" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchItems")}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
            />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c ? t(`category.${c}`) : t("allCategories")}
                </option>
              ))}
            </select>
          </div>

          <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("code")}</th>
                  <th className="px-4 py-3">{t("name")}</th>
                  <th className="px-4 py-3">{t("categoryLabel")}</th>
                  <th className="px-4 py-3">{t("unit")}</th>
                  <th className="px-4 py-3">{t("stock")}</th>
                  <th className="px-4 py-3">{t("reorderLevel")}</th>
                  <th className="px-4 py-3">{t("unitCost")}</th>
                  <th className="px-4 py-3">{t("stockStatus")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {itemsLoading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td>
                  </tr>
                ) : !items?.items.length ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("noItems")}</td>
                  </tr>
                ) : (
                  items.items.map((item) => (
                    <tr key={item.id} className="bg-card hover:bg-muted/50">
                      <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                        {item.item_code}
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">{item.name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{t(`category.${item.category}`)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{item.unit_of_measure}</td>
                      <td className="px-4 py-3 font-medium">{item.current_stock}</td>
                      <td className="px-4 py-3 text-muted-foreground">{item.reorder_level}</td>
                      <td className="px-4 py-3 text-muted-foreground">{formatKES(item.unit_cost)}</td>
                      <td className="px-4 py-3">
                        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STOCK_STYLES[item.stock_status])}>
                          {t(`stockLevel.${item.stock_status}`)}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Orders Tab */}
      {tab === "orders" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("poNumber")}</th>
                <th className="px-4 py-3">{t("supplier")}</th>
                <th className="px-4 py-3">{t("orderDate")}</th>
                <th className="px-4 py-3">{t("itemCount")}</th>
                <th className="px-4 py-3">{t("totalAmount")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ordersLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td>
                </tr>
              ) : !orders?.items.length ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("noOrders")}</td>
                </tr>
              ) : (
                orders.items.map((po) => (
                  <tr key={po.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3">
                      <Link
                        href={`/inventory/orders/${po.id}`}
                        className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {po.po_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-foreground">{po.supplier_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{new Date(po.order_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-muted-foreground">{po.item_count}</td>
                    <td className="px-4 py-3 font-medium">{formatKES(po.total_amount)}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", PO_STYLES[po.status])}>
                        {t(`poStatus.${po.status}`)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Suppliers Tab */}
      {tab === "suppliers" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("code")}</th>
                <th className="px-4 py-3">{t("name")}</th>
                <th className="px-4 py-3">{t("contact")}</th>
                <th className="px-4 py-3">{t("phone")}</th>
                <th className="px-4 py-3">{t("email")}</th>
                <th className="px-4 py-3">{t("kraPin")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!suppliers?.items.length ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("noSuppliers")}</td>
                </tr>
              ) : (
                suppliers.items.map((s) => (
                  <tr key={s.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{s.supplier_code}</td>
                    <td className="px-4 py-3 font-medium text-foreground">{s.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.contact_person || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.phone || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.email || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{s.kra_pin || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
