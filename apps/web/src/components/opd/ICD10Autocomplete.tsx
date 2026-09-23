"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { useIcd10Search } from "@/hooks/useEncounters";

interface ICD10AutocompleteProps {
  onSelect: (code: string, description: string) => void;
}

/**
 * ICD-10 autocomplete backed by the validated diagnosis catalog (D5).
 * Type-ahead search by code or description; selecting a code fills the
 * canonical description. Only codes returned by the catalog can be picked,
 * so free-text that is not a real ICD-10 code cannot be saved as if valid.
 *
 * @param props - onSelect callback with code and canonical description
 * @returns ICD-10 autocomplete input
 */
export function ICD10Autocomplete({ onSelect }: ICD10AutocompleteProps) {
  const t = useTranslations("diagnosis");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, isFetching } = useIcd10Search(query);
  const filtered = query.trim().length >= 2 ? (data?.items ?? []).slice(0, 15) : [];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (code: string, description: string) => {
    setSelectedDisplay(`${code} — ${description}`);
    setQuery("");
    setIsOpen(false);
    onSelect(code, description);
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {t("icd10Code")}
      </label>
      {selectedDisplay ? (
        <div
          onClick={() => {
            setSelectedDisplay("");
            setIsOpen(true);
          }}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
        >
          <span className="font-mono text-primary">{selectedDisplay.split(" — ")[0]}</span>
          <span className="truncate text-muted-foreground">{selectedDisplay.split(" — ")[1]}</span>
        </div>
      ) : (
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
            placeholder={t("icd10Search")}
            className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-2.5 text-sm text-foreground dark:border-border dark:bg-background"
          />
        </div>
      )}

      {isOpen && query.trim().length >= 2 && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
          {filtered.length > 0 ? (
            filtered.map((item) => (
              <li key={item.code}>
                <button
                  type="button"
                  onClick={() => handleSelect(item.code, item.description)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
                >
                  <span className="font-mono font-medium text-primary">{item.code}</span>
                  <span className="truncate text-foreground">{item.description}</span>
                </button>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              {isFetching ? t("icd10Searching") : t("icd10NoResults")}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
