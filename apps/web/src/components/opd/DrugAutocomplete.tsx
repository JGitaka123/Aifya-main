"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Search, ShieldCheck, AlertTriangle } from "lucide-react";
import { usePharmacyInventory } from "@/hooks/usePharmacy";

interface DrugAutocompleteProps {
  onSelect: (drugName: string, genericName: string | null, isKeml: boolean, stock?: number, unit?: string, strength?: string) => void;
}

interface DrugOption {
  name: string;
  generic: string;
  isKeml: boolean;
  stock: number;
  unit: string;
  strength: string;
  outOfStock: boolean;
  lowStock: boolean;
}

/**
 * Drug autocomplete with KEML flag.
 * Highlights KEML drugs per CLAUDE.md requirements.
 *
 * @param props - onSelect callback with drug info
 * @returns Drug autocomplete input
 */
export function DrugAutocomplete({ onSelect }: DrugAutocompleteProps) {
  const t = useTranslations("prescription");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: inventory, isFetching } = usePharmacyInventory(query.length >= 2 ? query : undefined, 1, 20);

  const filtered: DrugOption[] = query.length >= 2
    ? (inventory?.items ?? []).map(item => ({
        name: item.drug_name,
        generic: item.generic_name ?? "",
        isKeml: item.is_keml ?? false,
        stock: item.current_quantity,
        unit: item.unit_of_measure,
        strength: item.strength ?? "",
        outOfStock: item.current_quantity === 0,
        lowStock:
          item.current_quantity > 0 &&
          item.reorder_level > 0 &&
          item.current_quantity <= item.reorder_level,
      })).slice(0, 10)
    : [];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (drug: DrugOption) => {
    setSelectedDisplay(drug.name);
    setQuery("");
    setIsOpen(false);
    onSelect(drug.name, drug.generic, drug.isKeml, drug.stock, drug.unit, drug.strength ?? "");
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {t("drugName")}
      </label>
      {selectedDisplay ? (
        <div
          onClick={() => { setSelectedDisplay(""); setIsOpen(true); }}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
        >
          <span>{selectedDisplay}</span>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
            onFocus={() => query.length >= 2 && setIsOpen(true)}
            placeholder={t("drugSearch")}
            className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-2.5 text-sm text-foreground dark:border-border dark:bg-background"
          />
        </div>
      )}

      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
          {filtered.map((drug) => (
            <li key={drug.name}>
              <button
                type="button"
                onClick={() => handleSelect(drug)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
              >
                <span className={"flex-1 " + (drug.outOfStock ? "text-muted-foreground line-through" : "text-foreground")}>{drug.name}</span>
                <span className="text-xs text-muted-foreground">{drug.generic}</span>
                {drug.outOfStock
                  ? <span className="flex items-center gap-0.5 rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-200"><AlertTriangle className="h-3 w-3" />{t("outOfStock")}</span>
                  : drug.lowStock
                    ? <span className="flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200"><AlertTriangle className="h-3 w-3" />{drug.stock} {drug.unit}{" \u00b7 "}{t("stockLow")}</span>
                    : <span className="text-xs text-muted-foreground">{drug.stock} {drug.unit}</span>
                }
                {drug.isKeml && !drug.outOfStock && (
                  <span className="flex items-center gap-0.5 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
                    <ShieldCheck className="h-3 w-3" />
                    {t("keml")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {isOpen && query.length >= 2 && filtered.length === 0 && !isFetching && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground shadow-lg">
          {t("notInInventory", { query })}
        </div>
      )}
    </div>
  );
}
