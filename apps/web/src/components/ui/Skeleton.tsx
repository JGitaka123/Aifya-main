"use client";

import { cn } from "@/lib/utils";

/**
 * Shimmer skeleton loading placeholder.
 * Replaces plain "Loading..." text with a premium animated placeholder.
 *
 * @param className - Additional CSS classes
 * @returns Animated skeleton placeholder
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("skeleton-shimmer rounded-md", className)}
      aria-hidden="true"
    />
  );
}

/**
 * Skeleton row for table loading states.
 *
 * @param columns - Number of columns in the table
 * @param rows - Number of skeleton rows to render
 * @returns Table body with skeleton rows
 */
export function TableSkeleton({
  columns = 5,
  rows = 5,
}: {
  columns?: number;
  rows?: number;
}) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="animate-[fade-in_0.3s_ease-out]">
          {Array.from({ length: columns }).map((_, c) => (
            <td key={c} className="px-4 py-3">
              <Skeleton className={cn("h-4", c === 0 ? "w-24" : "w-20")} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/**
 * Skeleton card grid for dashboard loading states.
 *
 * @param count - Number of cards to show
 * @returns Grid of skeleton stat cards
 */
export function StatCardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-border bg-card p-5 shadow-[var(--shadow-card)]"
        >
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-6 w-24" />
            </div>
          </div>
          <Skeleton className="mt-3 h-3 w-20" />
        </div>
      ))}
    </>
  );
}

/**
 * Full page skeleton for detail pages.
 *
 * @returns Page-level skeleton layout
 */
export function PageSkeleton() {
  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-7 w-7 rounded-lg" />
        <Skeleton className="h-7 w-48" />
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCardSkeleton count={4} />
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
    </div>
  );
}
