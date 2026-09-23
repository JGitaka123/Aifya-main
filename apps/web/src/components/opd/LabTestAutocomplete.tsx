"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { useLabCatalogSearch, type LabCatalogItem } from "@/hooks/useLaboratory";
import { formatKES } from "@/lib/utils";

interface LabTestAutocompleteProps {
  /** Called with the chosen catalog test so the caller can append a row. */
  onSelect: (test: LabCatalogItem) => void;
}

/**
 * Lab test catalog type-ahead (D6). Searches the facility catalog by code or
 * name; selecting a test hands the caller its canonical code, name, panel and
 * managed price so ordering no longer relies on hand-keyed values. Manual test
 * rows remain as an "uncatalogued" free-text fallback.
 *
 * @param props - onSelect callback with the chosen catalog test
 * @returns Catalog search input
 */
export function LabTestAutocomplete({ onSelect }: LabTestAutocompleteProps) {
  const t = useTranslations("lab");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, isFetching } = useLabCatalogSearch(query);
  const results = query.trim().length >= 2 ? (data?.items ?? []).slice(0, 15) : [];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (test: LabCatalogItem) => {
    onSelect(test);
    setQuery("");
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => query.trim().length >= 2 && setIsOpen(true)}
          placeholder={t("catalogSearch")}
          className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-2.5 text-sm text-foreground dark:border-border dark:bg-background"
        />
      </div>

      {isOpen && query.trim().length >= 2 && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
          {results.length > 0 ? (
            results.map((test) => (
              <li key={test.id}>
                <button
                  type="button"
                  onClick={() => handleSelect(test)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
                >
                  <span className="font-mono font-medium text-primary">{test.test_code}</span>
                  <span className="flex-1 truncate text-foreground">{test.test_name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatKES(test.price_cents)}
                  </span>
                </button>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              {isFetching ? t("catalogSearching") : t("catalogNoResults")}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
