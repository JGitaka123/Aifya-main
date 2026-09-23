"use client";

import { cn } from "@/lib/utils";

/**
 * Consistent empty state component with icon, title, description, and optional action.
 * Replaces the ad-hoc empty states across pages.
 *
 * @param icon - Lucide icon component
 * @param title - Empty state title
 * @param description - Explanatory text
 * @param action - Optional action button/link
 * @returns Empty state component
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex animate-[fade-in_0.3s_ease-out] flex-col items-center justify-center py-16 text-center",
        className,
      )}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-lg bg-muted ring-1 ring-border">
        <Icon className="h-8 w-8 text-muted-foreground/50" />
      </div>
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
