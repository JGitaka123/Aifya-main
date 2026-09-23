"use client";

import { useTranslations } from "next-intl";
import { ChevronRight, Home } from "lucide-react";
import { Link } from "@/i18n/routing";

interface Breadcrumb {
  label: string;
  href?: string;
}

/**
 * Consistent page header with breadcrumbs, title, subtitle, and action area.
 * Provides unified navigation context across all pages.
 *
 * @param icon - Lucide icon component for the page
 * @param title - Page title
 * @param subtitle - Optional subtitle/description
 * @param badge - Optional count badge next to title
 * @param breadcrumbs - Navigation breadcrumb trail
 * @param actions - Action buttons (right side)
 * @returns Page header component
 */
export function PageHeader({
  icon: Icon,
  title,
  subtitle,
  badge,
  breadcrumbs,
  actions,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle?: string;
  badge?: string | number;
  breadcrumbs?: Breadcrumb[];
  actions?: React.ReactNode;
}) {
  const tc = useTranslations("common");

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-3 border-b border-border pb-5">
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Link
            href="/"
            className="flex items-center gap-1 transition-colors hover:text-foreground"
          >
            <Home className="h-3 w-3" />
            <span>{tc("home")}</span>
          </Link>
          {breadcrumbs.map((crumb, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <ChevronRight className="h-3 w-3" />
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="transition-colors hover:text-foreground"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="font-medium text-foreground">
                  {crumb.label}
                </span>
              )}
            </span>
          ))}
        </nav>
      )}

      {/* Title row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/10">
              <Icon className="h-5 w-5" />
            </div>
          )}
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold text-foreground">
                {title}
              </h1>
              {badge !== undefined && badge !== null && (
                <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-primary/10 px-2 text-xs font-semibold text-primary">
                  {badge}
                </span>
              )}
            </div>
            {subtitle && (
              <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
    </div>
  );
}
