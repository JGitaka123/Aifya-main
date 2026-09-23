"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { useEmployees } from "@/hooks/usePayroll";
import { cn } from "@/lib/utils";

/**
 * Async-loading employee picker. Searches the employee directory and exposes
 * keyboard-friendly selection via combobox-style dropdown.
 *
 * @param value - Selected employee UUID
 * @param onChange - Callback when an employee is picked
 * @param placeholder - Optional placeholder for the search input
 * @returns Employee select control
 */
export function EmployeeSelect({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (id: string, name: string) => void;
  placeholder?: string;
}) {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useEmployees({
    search: search || undefined,
    is_active: true,
    page_size: 50,
  });

  const items = useMemo(() => data?.items ?? [], [data?.items]);

  const selected = useMemo(
    () => items.find((e) => e.id === value),
    [items, value],
  );

  return (
    <div className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={open ? search : selected?.full_name ?? search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Delay to allow click handling on items
            window.setTimeout(() => setOpen(false), 150);
          }}
          placeholder={placeholder ?? t("searchEmployee")}
          className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm text-foreground"
        />
      </div>

      {open && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
          {isLoading ? (
            <div className="p-3 text-sm text-muted-foreground">
              {tc("loading")}
            </div>
          ) : items.length === 0 ? (
            <div className="p-3 text-sm text-muted-foreground">
              {t("noEmployees")}
            </div>
          ) : (
            items.map((emp) => (
              <button
                key={emp.id}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(emp.id, emp.full_name);
                  setSearch("");
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-muted/50",
                  emp.id === value && "bg-primary/5",
                )}
              >
                <div>
                  <div className="font-medium text-foreground">
                    {emp.full_name}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {emp.staff_id} • {emp.job_title}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
