"use client";

import { useState, type ChangeEvent } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Package,
  Search,
  Plus,
  AlertTriangle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Upload,
  Download,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  usePharmacyInventory,
  useStockAlerts,
  useCreatePharmacyItem,
} from "@/hooks/usePharmacy";
import { formatKES, formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { PharmacyItemCreate } from "@aifya/shared";

const newItemSchema = z.object({
  drug_code: z.string().min(1),
  drug_name: z.string().min(1),
  generic_name: z.string().nullable().optional(),
  is_keml: z.boolean().optional(),
  dosage_form: z.string().nullable().optional(),
  strength: z.string().nullable().optional(),
  batch_number: z.string().nullable().optional(),
  current_quantity: z.coerce.number().min(0),
  unit_of_measure: z.string(),
  reorder_level: z.coerce.number().min(0),
  selling_price_cents: z.coerce.number().min(0).nullable().optional(),
  buying_price_cents: z.coerce.number().min(0).nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  manufacturer: z.string().nullable().optional(),
  supplier: z.string().nullable().optional(),
  shelf_location: z.string().nullable().optional(),
  atc_code: z.string().nullable().optional(),
  max_stock_level: z.coerce.number().min(0).nullable().optional(),
  storage_conditions: z.string().nullable().optional(),
  is_active: z.boolean().optional(),
});

type NewItemFormData = z.infer<typeof newItemSchema>;

type BulkImportRow = PharmacyItemCreate & {
  is_active?: boolean;
  selling_price_cents?: number | null;
  buying_price_cents?: number | null;
  expiry_date?: string | null;
};

function parseBulkCsv(text: string): { rows: BulkImportRow[]; errs: string[] } {
  const lines = text.trim().split(/\r?\n/);
  const headerLine = lines[0];
  if (!headerLine) {
    return { rows: [], errs: ["CSV header row required"] };
  }

  const headers = headerLine
    .split(",")
    .map((header) => header.trim().replace(/"/g, ""));
  const rows: BulkImportRow[] = [];
  const errs: string[] = [];

  lines.slice(1).forEach((line, index) => {
    if (!line.trim()) return;

    const values = line.split(",").map((value) => value.trim().replace(/"/g, ""));
    const row = headers.reduce<Record<string, string>>((acc, header, valueIndex) => {
      acc[header] = values[valueIndex] ?? "";
      return acc;
    }, {});

    if (!row["drug_code"] || !row["drug_name"]) {
      errs.push(`Row ${index + 2}: drug_code and drug_name required`);
      return;
    }

    rows.push({
      drug_code: row["drug_code"],
      drug_name: row["drug_name"],
      generic_name: row["generic_name"] || "",
      strength: row["strength"] || "",
      dosage_form: row["dosage_form"] || "",
      unit_of_measure: row["unit_of_measure"] || "tablet",
      current_quantity: Number(row["current_quantity"]) || 0,
      reorder_level: Number(row["reorder_level"]) || 10,
      max_stock_level: Number(row["max_stock_level"]) || null,
      selling_price_cents: Number(row["selling_price_kes"]) || null,
      buying_price_cents: Number(row["buying_price_kes"]) || null,
      atc_code: row["atc_code"] || "",
      manufacturer: row["manufacturer"] || "",
      supplier: row["supplier"] || "",
      batch_number: row["batch_number"] || "",
      expiry_date: row["expiry_date"] || "",
      shelf_location: row["shelf_location"] || "",
      storage_conditions: row["storage_conditions"] || "",
      is_keml: String(row["is_keml"]).toLowerCase() === "true",
      is_active: String(row["is_active"]).toLowerCase() !== "false",
    });
  });

  return { rows, errs };
}

/**
 * Pharmacy inventory management page.
 * Search, view stock levels, add items, see reorder and expiry alerts.
 *
 * @returns Inventory management page
 */
export default function InventoryPage() {
  const t = useTranslations("pharmacy");
  const tc = useTranslations("common");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkRows, setBulkRows] = useState<BulkImportRow[]>([]);
  const [bulkErrors, setBulkErrors] = useState<string[]>([]);
  const [bulkSuccess, setBulkSuccess] = useState(0);
  const [bulkLoading, setBulkLoading] = useState(false);
  const pageSize = 30;

  const { data: inventory, isLoading } = usePharmacyInventory(
    searchQuery || undefined,
    page,
    pageSize
  );
  const { data: alerts } = useStockAlerts();
  const createItem = useCreatePharmacyItem();

  const totalPages = inventory ? Math.ceil(inventory.total / pageSize) : 0;

  const { register, handleSubmit, reset } = useForm<NewItemFormData>({
    resolver: zodResolver(newItemSchema),
    defaultValues: {
      current_quantity: 0,
      reorder_level: 10,
      unit_of_measure: "tablet",
      is_keml: false,
      is_active: true,
    },
  });

  const onSubmit = (data: NewItemFormData) => {
    createItem.mutate(
      {
        ...data,
        selling_price_cents: data.selling_price_cents ? Math.round(data.selling_price_cents * 100) : undefined,
        buying_price_cents: data.buying_price_cents ? Math.round(data.buying_price_cents * 100) : undefined,
        expiry_date: data.expiry_date || undefined,
      },
      {
        onSuccess: () => {
          setShowAddForm(false);
          reset();
        },
      }
    );
  };

  const downloadTemplate = () => {
    const headers = ["drug_code","drug_name","generic_name","strength","dosage_form","unit_of_measure","current_quantity","reorder_level","max_stock_level","selling_price_kes","buying_price_kes","atc_code","manufacturer","supplier","batch_number","expiry_date","shelf_location","storage_conditions","is_keml","is_active"].join(",");
    const example = ["AMX-500","Amoxicillin","Amoxicillin Trihydrate","500mg","tablet","tablet","500","50","1000","25","8","J01CA04","Dawa Ltd","Meds Africa","BATCH-001","2027-06-30","A1-SHELF-3","Store below 25 deg C","true","true"].join(",");
    const blob = new Blob([headers+"\n"+example],{type:"text/csv"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href=url; a.download="drug_import_template.csv"; a.click();
    URL.revokeObjectURL(url);
  };
  const handleBulkFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const { rows, errs } = parseBulkCsv(String(ev.target?.result ?? ""));
      setBulkRows(rows); setBulkErrors(errs); setBulkSuccess(0);
    };
    reader.readAsText(file);
  };
  const handleBulkSubmit = async () => {
    setBulkLoading(true); let ok=0; const errs=[...bulkErrors];
    for(const row of bulkRows){
      await new Promise<void>(resolve=>{
        const item = { ...row };
        delete item.is_active;
        createItem.mutate({...item,selling_price_cents:row.selling_price_cents?Math.round(Number(row.selling_price_cents)*100):undefined,buying_price_cents:row.buying_price_cents?Math.round(Number(row.buying_price_cents)*100):undefined,expiry_date:row.expiry_date||undefined},{onSuccess:()=>{ok++;resolve();},onError:(error)=>{errs.push(error instanceof Error ? error.message : String(error));resolve();}});
      });
    }
    setBulkSuccess(ok); setBulkErrors(errs); setBulkRows([]); setBulkLoading(false);
  };


  const alertColors: Record<string, string> = {
    out_of_stock: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    low_stock: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200",
    expired: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    expiring_soon: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  };

  const alertLabels: Record<string, string> = {
    out_of_stock: "outOfStock",
    low_stock: "lowStock",
    expired: "expired",
    expiring_soon: "expiringSoon",
  };

  return (
    <div className="mx-auto max-w-6xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <Link href="/pharmacy" className="mb-3 inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          {t("queue")}
        </Link>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Package className="h-7 w-7 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">{t("inventoryManagement")}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={downloadTemplate} className="flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"><Download className="h-4 w-4" />Template</button>
            <button onClick={() => {setShowBulkImport(!showBulkImport);setShowAddForm(false);}} className="flex items-center gap-2 rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"><Upload className="h-4 w-4" />Bulk Import</button>
            <button onClick={() => {setShowAddForm(!showAddForm);setShowBulkImport(false);}} className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"><Plus className="h-4 w-4" />{t("addItem")}</button>
          </div>
        </div>
      </div>

      {/* Bulk Import Panel */}
      {showBulkImport && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-2 font-semibold text-foreground flex items-center gap-2"><Upload className="h-4 w-4 text-primary" />Bulk Drug Import</h3>
          <p className="mb-3 text-sm text-muted-foreground">Download the template, fill in your drug list (prices in KES, dates as YYYY-MM-DD), then upload.</p>
          <div className="flex items-center gap-3 mb-4">
            <button onClick={downloadTemplate} className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"><Download className="h-4 w-4" />Download Template CSV</button>
          </div>
          <div className="mb-4">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Option 1 — Paste CSV text directly</label>
            <textarea
              rows={5}
              placeholder="Paste CSV content here (including header row)..."
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground font-mono"
              onChange={(e) => {
                const text = e.target.value.trim();
                if (!text) return;
                const { rows, errs } = parseBulkCsv(text);
                setBulkRows(rows); setBulkErrors(errs); setBulkSuccess(0);
              }}
            />
          </div>
          <div className="mb-4">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Option 2 — Upload CSV file</label>
            <input type="file" accept=".csv" onChange={handleBulkFile} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
          </div>
          {bulkRows.length > 0 && (
            <div className="mb-3 rounded-lg bg-muted/40 p-3">
              <p className="text-sm font-medium text-foreground mb-2">{bulkRows.length} drugs ready to import:</p>
              <div className="max-h-40 overflow-y-auto space-y-1">
                {bulkRows.map((row, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <CheckCircle2 className="h-3 w-3 text-green-500 flex-shrink-0" />
                    {row.drug_code} — {row.drug_name} ({row.strength}) Qty:{row.current_quantity} KES {row.selling_price_cents}
                  </div>
                ))}
              </div>
              <button onClick={handleBulkSubmit} disabled={bulkLoading} className="mt-3 flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                <Upload className="h-4 w-4" />{bulkLoading ? "Importing..." : "Import "+bulkRows.length+" Drugs"}
              </button>
            </div>
          )}
          {bulkSuccess > 0 && <div className="flex items-center gap-2 rounded-lg bg-green-50 dark:bg-green-950 px-3 py-2 text-sm text-green-800 dark:text-green-200"><CheckCircle2 className="h-4 w-4" />{bulkSuccess} drugs imported successfully!</div>}
          {bulkErrors.length > 0 && <div className="mt-2 rounded-lg bg-red-50 dark:bg-red-950 p-3 space-y-1">{bulkErrors.map((e,i)=><div key={i} className="flex items-center gap-2 text-xs text-red-800 dark:text-red-200"><XCircle className="h-3 w-3 flex-shrink-0" />{e}</div>)}</div>}
        </div>
      )}

      {/* Stock alerts */}
      {alerts && alerts.length > 0 && (
        <div className="mb-4 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            {t("stockAlerts")} ({alerts.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {alerts.map((alert) => (
              <span
                key={`${alert.item_id}-${alert.alert_type}`}
                className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", alertColors[alert.alert_type])}
              >
                {alert.drug_name} — {t(alertLabels[alert.alert_type] as Parameters<typeof t>[0])}
                {alert.alert_type === "low_stock" && ` (${alert.current_quantity})`}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Add item form */}
      {showAddForm && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-4 font-semibold text-foreground">{t("addItem")}</h3>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("drugCode")}</label>
                <input {...register("drug_code")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("drugName")}</label>
                <input {...register("drug_name")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("genericName")}</label>
                <input {...register("generic_name")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("strength")}</label>
                <input {...register("strength")} placeholder="e.g. 500mg" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("currentStock")}</label>
                <input type="number" {...register("current_quantity")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("unitOfMeasure")}</label>
                <select {...register("unit_of_measure")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground">
                  <option value="tablet">{t("tablet")}</option>
                  <option value="capsule">{t("capsule")}</option>
                  <option value="ml">ml</option>
                  <option value="vial">Vial</option>
                  <option value="tube">Tube</option>
                  <option value="sachet">{t("sachet")}</option>
                  <option value="bottle">Bottle</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("reorderLevel")}</label>
                <input type="number" {...register("reorder_level")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("sellingPrice")}</label>
                <input type="number" step="0.01" {...register("selling_price_cents")} placeholder="e.g. 25.00" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Buying Price (KES) *</label>
                <input type="number" step="0.01" {...register("buying_price_cents")} placeholder="e.g. 8.00" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">ATC Code</label>
                <input {...register("atc_code")} placeholder="e.g. J01CA04" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Dosage Form</label>
                <select {...register("dosage_form")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground">
                  <option value="">Select...</option>
                  <option value="tablet">Tablet</option>
                  <option value="capsule">Capsule</option>
                  <option value="syrup">Syrup</option>
                  <option value="injection">Injection</option>
                  <option value="cream">Cream</option>
                  <option value="drops">Drops</option>
                  <option value="suppository">Suppository</option>
                  <option value="inhaler">Inhaler</option>
                  <option value="powder">Powder</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Manufacturer</label>
                <input {...register("manufacturer")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Supplier</label>
                <input {...register("supplier")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Max Stock Level</label>
                <input type="number" {...register("max_stock_level")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Storage Conditions</label>
                <input {...register("storage_conditions")} placeholder="e.g. Store below 25 deg C" className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("batchNumber")}</label>
                <input {...register("batch_number")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("expiryDate")}</label>
                <input type="date" {...register("expiry_date")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("shelfLocation")}</label>
                <input {...register("shelf_location")} className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
              </div>
              <div className="flex items-end gap-6">
                <label className="flex items-center gap-2 pb-1.5 text-sm text-foreground">
                  <input type="checkbox" {...register("is_keml")} className="rounded border-input text-primary" />
                  {t("keml")}
                </label>
                <label className="flex items-center gap-2 pb-1.5 text-sm text-foreground">
                  <input type="checkbox" {...register("is_active")} className="rounded border-input text-primary" />
                  Active
                </label>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={createItem.isPending}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {createItem.isPending ? t("addingItem") : t("addItem")}
              </button>
              <button
                type="button"
                onClick={() => { setShowAddForm(false); reset(); }}
                className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                {tc("cancel")}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
          placeholder={tc("searchPlaceholder")}
          className="w-full rounded-lg border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground shadow-sm"
        />
      </div>

      {/* Inventory table */}
      <div className="overflow-hidden rounded-xl border border-border shadow-[var(--shadow-card)]">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">{t("drugCode")}</th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">{t("drugName")}</th>
              <th className="hidden px-3 py-2.5 text-left font-medium text-muted-foreground md:table-cell">{t("strength")}</th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">{t("currentStock")}</th>
              <th className="hidden px-3 py-2.5 text-right font-medium text-muted-foreground sm:table-cell">{t("sellingPrice")}</th>
              <th className="hidden px-3 py-2.5 text-left font-medium text-muted-foreground lg:table-cell">{t("expiryDate")}</th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">{t("stockAlerts")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">{tc("loading")}</td>
              </tr>
            ) : inventory?.items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">{tc("noResults")}</td>
              </tr>
            ) : (
              inventory?.items.map((item) => {
                const itemAlerts = alerts?.filter((a) => a.item_id === item.id) ?? [];
                return (
                  <tr key={item.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2.5 font-mono text-xs text-primary">{item.drug_code}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-foreground">{item.drug_name}</span>
                        {item.is_keml && <ShieldCheck className="h-3.5 w-3.5 text-green-500" />}
                      </div>
                      {item.generic_name && <p className="text-xs text-muted-foreground">{item.generic_name}</p>}
                    </td>
                    <td className="hidden px-3 py-2.5 text-muted-foreground md:table-cell">{item.strength ?? "—"}</td>
                    <td className={cn(
                      "px-3 py-2.5 text-right font-medium",
                      item.current_quantity === 0 ? "text-red-600" :
                        item.current_quantity <= item.reorder_level ? "text-yellow-600" : "text-foreground"
                    )}>
                      {item.current_quantity}
                    </td>
                    <td className="hidden px-3 py-2.5 text-right text-muted-foreground sm:table-cell">
                      {item.selling_price_cents != null ? formatKES(item.selling_price_cents) : "—"}
                    </td>
                    <td className="hidden px-3 py-2.5 text-muted-foreground lg:table-cell">
                      {item.expiry_date ? formatDate(item.expiry_date) : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {itemAlerts.map((alert) => (
                          <span
                            key={alert.alert_type}
                            className={cn("rounded-full px-1.5 py-0.5 text-xs font-medium", alertColors[alert.alert_type])}
                          >
                            {t(alertLabels[alert.alert_type] as Parameters<typeof t>[0])}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-50"
          >
            <ChevronLeft className="h-4 w-4" />
            {tc("back")}
          </button>
          <span className="text-sm text-muted-foreground">{page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-50"
          >
            {tc("next")}
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
