"use client";

import { cn } from "@/lib/utils";

type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "danger"
  | "info"
  | "blue"
  | "neutral"
  | "purple"
  | "cyan"
  | "pink"
  | "indigo"
  | "orange"
  | "teal"
  | "rose"
  | "emerald"
  | "slate"
  | "red-solid"
  | "orange-solid"
  | "yellow-solid"
  | "green-solid"
  | "blue-solid";

const VARIANT_STYLES: Record<BadgeVariant, string> = {
  default: "bg-muted text-muted-foreground",
  success: "bg-green-50 text-green-700 ring-1 ring-inset ring-green-600/10 dark:bg-green-950/50 dark:text-green-400 dark:ring-green-500/20",
  warning: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10 dark:bg-amber-950/50 dark:text-amber-400 dark:ring-amber-500/20",
  error: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/10 dark:bg-red-950/50 dark:text-red-400 dark:ring-red-500/20",
  danger: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-600/10 dark:bg-red-950/50 dark:text-red-400 dark:ring-red-500/20",
  info: "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/10 dark:bg-blue-950/50 dark:text-blue-400 dark:ring-blue-500/20",
  blue: "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/10 dark:bg-blue-950/50 dark:text-blue-400 dark:ring-blue-500/20",
  neutral: "bg-muted text-muted-foreground",
  purple: "bg-purple-50 text-purple-700 ring-1 ring-inset ring-purple-600/10 dark:bg-purple-950/50 dark:text-purple-400 dark:ring-purple-500/20",
  cyan: "bg-cyan-50 text-cyan-700 ring-1 ring-inset ring-cyan-600/10 dark:bg-cyan-950/50 dark:text-cyan-400 dark:ring-cyan-500/20",
  pink: "bg-pink-50 text-pink-700 ring-1 ring-inset ring-pink-600/10 dark:bg-pink-950/50 dark:text-pink-400 dark:ring-pink-500/20",
  indigo: "bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-600/10 dark:bg-indigo-950/50 dark:text-indigo-400 dark:ring-indigo-500/20",
  orange: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/10 dark:bg-orange-950/50 dark:text-orange-400 dark:ring-orange-500/20",
  teal: "bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-600/10 dark:bg-teal-950/50 dark:text-teal-400 dark:ring-teal-500/20",
  rose: "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10 dark:bg-rose-950/50 dark:text-rose-400 dark:ring-rose-500/20",
  emerald: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/10 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-500/20",
  slate: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-600/10 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-500/20",
  "red-solid": "bg-red-600 text-white",
  "orange-solid": "bg-orange-500 text-white",
  "yellow-solid": "bg-yellow-400 text-yellow-900",
  "green-solid": "bg-green-500 text-white",
  "blue-solid": "bg-blue-600 text-white",
};

/**
 * Consistent status/type/priority badge used across all modules.
 * Replaces the ad-hoc badge styling that was repeated in every page.
 *
 * @param children - Badge text content
 * @param variant - Color variant
 * @param size - Badge size
 * @param dot - Show colored dot before text
 * @param className - Additional classes
 * @returns Styled badge
 */
export function StatusBadge({
  children,
  variant = "default",
  size = "sm",
  dot = false,
  className,
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: "xs" | "sm";
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap",
        size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-0.5 text-xs",
        VARIANT_STYLES[variant],
        className,
      )}
    >
      {dot && (
        <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      )}
      {children}
    </span>
  );
}
