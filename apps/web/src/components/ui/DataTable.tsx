"use client";

import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { TableSkeleton } from "./Skeleton";

/**
 * Premium data table wrapper with consistent styling, loading skeletons,
 * empty state handling, and pagination.
 *
 * @param headers - Array of column header objects
 * @param isLoading - Whether data is loading
 * @param isEmpty - Whether results are empty
 * @param emptyMessage - Message to show when empty
 * @param children - Table body rows (tr elements)
 * @param page - Current page number
 * @param totalPages - Total number of pages
 * @param onPageChange - Pagination callback
 * @param totalCount - Total row count for footer
 * @param columnCount - Number of columns (for skeleton)
 * @returns Premium data table
 */
export function DataTable({
  headers,
  isLoading,
  isEmpty,
  emptyMessage,
  children,
  page,
  totalPages,
  onPageChange,
  totalCount,
  columnCount,
  className,
}: {
  headers: { label: string; className?: string }[];
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyMessage?: string;
  children: React.ReactNode;
  page?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  totalCount?: number;
  columnCount?: number;
  className?: string;
}) {
  const tc = useTranslations("common");
  const cols = columnCount ?? headers.length;

  return (
    <div className={cn("animate-[fade-in_0.3s_ease-out] overflow-hidden rounded-lg border border-border bg-card shadow-[var(--shadow-card)]", className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              {headers.map((h, i) => (
                <th
                  key={i}
                  className={cn(
                    "px-4 py-3 text-xs font-semibold uppercase text-muted-foreground",
                    h.className,
                  )}
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <TableSkeleton columns={cols} rows={5} />
            ) : isEmpty ? (
              <tr>
                <td
                  colSpan={cols}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  {emptyMessage ?? tc("noResults")}
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>

      {/* Footer: count + pagination */}
      {(totalCount !== undefined || (page !== undefined && totalPages !== undefined && totalPages > 1)) && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          {totalCount !== undefined && (
            <p className="text-xs text-muted-foreground">
              {totalCount} {tc("totalItems")}
            </p>
          )}
          {page !== undefined && totalPages !== undefined && totalPages > 1 && onPageChange && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onPageChange(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                {tc("back")}
              </button>
              <span className="tabular-nums text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
              >
                {tc("next")}
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
