"use client";

import { useTranslations } from "next-intl";
import { usePeriods } from "@/hooks/useFinance";
import { cn } from "@/lib/utils";

/**
 * Reusable period picker dropdown. Loads from usePeriods.
 *
 * @param value - Selected period id
 * @param onChange - Callback for period id change
 * @param disabled - Disable the select
 * @param className - Extra classes
 * @returns Native select element
 */
export function PeriodSelect({
  value,
  onChange,
  disabled = false,
  className,
  placeholder,
  filterStatus,
}: {
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  filterStatus?: ("open" | "closed" | "locked" | "year_end")[];
}) {
  const t = useTranslations("finance");
  const { data: periods, isLoading } = usePeriods();

  const filtered = (periods ?? []).filter((p) =>
    filterStatus ? filterStatus.includes(p.status) : true,
  );

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || isLoading}
      className={cn(
        "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground disabled:opacity-50 dark:border-border dark:bg-background",
        className,
      )}
    >
      <option value="">{placeholder ?? t("selectPeriod")}</option>
      {filtered.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
