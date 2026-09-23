"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { useAccounts, type AccountType } from "@/hooks/useFinance";
import { cn } from "@/lib/utils";

/**
 * Reusable account picker dropdown. Filters by type if provided.
 * Loads from useAccounts.
 *
 * @param value - Selected account id
 * @param onChange - Callback for account id change
 * @param typeFilter - Optional account types to include
 * @param required - Mark required
 * @param disabled - Disable the select
 * @param className - Extra classes
 * @returns Native select element
 */
export function AccountSelect({
  value,
  onChange,
  typeFilter,
  required = false,
  disabled = false,
  className,
  placeholder,
}: {
  value: string;
  onChange: (id: string) => void;
  typeFilter?: AccountType[];
  required?: boolean;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}) {
  const t = useTranslations("finance");
  const { data: accounts, isLoading } = useAccounts();

  const filtered = useMemo(() => {
    const list = accounts ?? [];
    if (!typeFilter || typeFilter.length === 0) return list;
    return list.filter((a) => typeFilter.includes(a.type));
  }, [accounts, typeFilter]);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || isLoading}
      required={required}
      className={cn(
        "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground disabled:opacity-50 dark:border-border dark:bg-background",
        className,
      )}
    >
      <option value="">{placeholder ?? t("selectAccount")}</option>
      {filtered
        .filter((a) => a.is_active)
        .map((a) => (
          <option key={a.id} value={a.id}>
            {a.code} — {a.name}
          </option>
        ))}
    </select>
  );
}
