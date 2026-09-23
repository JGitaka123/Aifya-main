"use client";

import { cn } from "@/lib/utils";

/**
 * Format a numeric or string money value as KES with thousand separators.
 * Negative values shown in parentheses and red.
 *
 * @param value - Amount as number or numeric string (decimal, NOT cents)
 * @param currency - Currency prefix, defaults to "KES"
 * @param showCurrency - Whether to show the currency code prefix
 * @param colorize - Color negatives red and positives default
 * @param className - Extra classes
 * @returns Formatted money span
 */
export function MoneyDisplay({
  value,
  currency = "KES",
  showCurrency = true,
  colorize = true,
  className,
  bold = false,
}: {
  value: number | string | null | undefined;
  currency?: string;
  showCurrency?: boolean;
  colorize?: boolean;
  className?: string;
  bold?: boolean;
}) {
  const num = typeof value === "string" ? Number(value) : (value ?? 0);
  const safe = Number.isFinite(num) ? num : 0;
  const isNegative = safe < 0;
  const formatted = Math.abs(safe).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const display = isNegative ? `(${formatted})` : formatted;

  return (
    <span
      className={cn(
        "tabular-nums",
        bold && "font-semibold",
        colorize && isNegative && "text-red-600 dark:text-red-400",
        className,
      )}
    >
      {showCurrency && (
        <span className="mr-0.5 text-muted-foreground/80">{currency}</span>
      )}
      {display}
    </span>
  );
}

/**
 * Compact variant — no currency prefix, smaller font.
 *
 * @param value - Numeric value
 * @returns Compact money display
 */
export function MoneyCompact({ value }: { value: number | string | null | undefined }) {
  return <MoneyDisplay value={value} showCurrency={false} colorize className="text-sm" />;
}
