"use client";

import { useTranslations } from "next-intl";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DateRange {
  start: string;
  end: string;
}

/**
 * Native date input range picker — simpler than shadcn Calendar but works
 * across locales and zero deps. Returns ISO YYYY-MM-DD strings.
 *
 * @param value - { start, end } ISO dates
 * @param onChange - Callback when either date changes
 * @param className - Extra classes
 * @returns Date range picker
 */
export function DateRangePicker({
  value,
  onChange,
  className,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
}) {
  const t = useTranslations("finance");

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-md border border-input bg-card p-2",
        className,
      )}
    >
      <Calendar className="h-4 w-4 text-muted-foreground" />
      <label className="text-xs font-medium text-muted-foreground">
        {t("from")}
      </label>
      <input
        type="date"
        value={value.start}
        onChange={(e) => onChange({ ...value, start: e.target.value })}
        className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground dark:border-border dark:bg-background"
      />
      <label className="text-xs font-medium text-muted-foreground">
        {t("to")}
      </label>
      <input
        type="date"
        value={value.end}
        onChange={(e) => onChange({ ...value, end: e.target.value })}
        className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground dark:border-border dark:bg-background"
      />
    </div>
  );
}
