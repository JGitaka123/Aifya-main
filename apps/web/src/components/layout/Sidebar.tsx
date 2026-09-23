"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { Link } from "@/i18n/routing";
import {
  LogOut,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Lock,
  Sparkles,
  X,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useLicenseContext } from "@/components/licensing/LicenseProvider";
import { recordModuleVisit } from "@/hooks/useTelemetry";
import { BETA_PUBLIC_ACCESS_ENABLED } from "@/lib/auth/beta";
import { getActiveNavigationHref, NAV_ITEMS } from "@/lib/navigation";
import { AifyaLogo } from "@/components/brand/AifyaLogo";

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
}

const DEFAULT_TIER_BADGE = {
  bg: "bg-slate-100 dark:bg-slate-800",
  text: "text-slate-600 dark:text-slate-300",
};

/** Tier badge colors */
const TIER_BADGE: Record<string, { bg: string; text: string }> = {
  community: DEFAULT_TIER_BADGE,
  professional: { bg: "bg-sky-50 dark:bg-sky-950/50", text: "text-sky-700 dark:text-sky-300" },
  enterprise: { bg: "bg-violet-50 dark:bg-violet-950/50", text: "text-violet-700 dark:text-violet-300" },
  government: { bg: "bg-emerald-50 dark:bg-emerald-950/50", text: "text-emerald-700 dark:text-emerald-300" },
};

/**
 * App sidebar with navigation, facility branding, license tier, and dark mode toggle.
 * Per CLAUDE.md: facility logo in sidebar header, "Powered by Aifya" in footer.
 *
 * @param props.mobileOpen - Whether the mobile navigation drawer is visible
 * @param props.onMobileClose - Closes the mobile navigation drawer
 * @returns Sidebar component
 */
export function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const { hasModule, tier } = useLicenseContext();
  const [mounted, setMounted] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    const desktopQuery = window.matchMedia("(min-width: 1024px)");
    const updateDesktopState = () => setIsDesktop(desktopQuery.matches);
    updateDesktopState();
    desktopQuery.addEventListener("change", updateDesktopState);
    return () => desktopQuery.removeEventListener("change", updateDesktopState);
  }, []);
  useEffect(() => onMobileClose(), [pathname, onMobileClose]);

  const activeHref = getActiveNavigationHref(pathname);

  const tierBadge = TIER_BADGE[tier] ?? DEFAULT_TIER_BADGE;

  return (
    <aside
      id="primary-navigation"
      aria-label={tc("primaryNavigation")}
      aria-hidden={!isDesktop && !mobileOpen}
      inert={!isDesktop && !mobileOpen}
      data-open={mobileOpen}
      data-tour="sidebar"
      className={cn(
        "fixed inset-y-0 left-0 z-[70] flex h-dvh -translate-x-full flex-col border-r border-sidebar-border bg-sidebar shadow-2xl transition-[width,transform] duration-300 ease-out data-[open=true]:translate-x-0 lg:static lg:z-auto lg:translate-x-0 lg:shadow-none",
        collapsed
          ? "w-[min(20rem,88vw)] lg:w-[68px]"
          : "w-[min(20rem,88vw)] lg:w-64",
      )}
    >
      {/* Header — facility logo + collapse */}
      <div className="flex h-[72px] items-center justify-between border-b border-sidebar-border px-4">
        {!collapsed && (
          <div className="flex min-w-0 items-center gap-2.5">
            <AifyaLogo />
            <div className="min-w-0 border-l border-sidebar-border pl-2.5">
              <span className={cn("ml-1.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase", tierBadge.bg, tierBadge.text)}>
                {tier}
              </span>
            </div>
          </div>
        )}
        {collapsed && (
          <AifyaLogo compact className="mx-auto" />
        )}
        <button
          type="button"
          onClick={onMobileClose}
          aria-label={tc("closeNavigation")}
          className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-lg text-sidebar-foreground/70 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-accent lg:hidden"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Collapse toggle */}
      <div className="hidden px-3 py-2 lg:block">
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? tc("expandNavigation") : tc("collapseNavigation")}
          aria-expanded={!collapsed}
          className="flex h-7 w-full items-center justify-center rounded-md text-sidebar-foreground/45 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 pb-3">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const locked = item.module ? !hasModule(item.module) : false;
            const active = item.href === activeHref;
            const Icon = item.icon;

            return (
              <li key={item.key}>
                {item.separator && (
                  <div className="my-2 border-t border-sidebar-border" />
                )}
                {locked ? (
                  <Link
                    href="/settings/billing"
                    onClick={onMobileClose}
                    className={cn(
                      "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                      "text-sidebar-foreground/25 hover:text-sidebar-foreground/40 hover:bg-sidebar-muted/30",
                    )}
                    title={collapsed ? t(item.key) : undefined}
                  >
                    <Icon className="h-[18px] w-[18px] flex-shrink-0" />
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{t(item.key)}</span>
                        <Lock className="h-3 w-3 opacity-50" />
                      </>
                    )}
                  </Link>
                ) : (
                  <Link
                    href={item.href}
                    onClick={() => {
                      if (item.module) recordModuleVisit(item.module);
                      onMobileClose();
                    }}
                    aria-current={active ? "page" : undefined}
                    data-tour={`${item.key}-link`}
                    className={cn(
                      "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
                      active
                        ? "bg-sidebar-muted text-sidebar-accent shadow-[inset_3px_0_0_var(--color-sidebar-accent)]"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-muted hover:text-sidebar-foreground",
                    )}
                    title={collapsed ? t(item.key) : undefined}
                  >
                    <Icon className={cn("h-[18px] w-[18px] flex-shrink-0", active && "text-sidebar-accent")} />
                    {!collapsed && <span className="truncate">{t(item.key)}</span>}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="space-y-1 border-t border-sidebar-border bg-sidebar-muted/30 px-3 py-3">
        {/* Dark mode toggle */}
        <button
          type="button"
          data-tour="theme-toggle"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground"
        >
          {mounted && theme === "dark" ? (
            <Sun className="h-[18px] w-[18px]" />
          ) : (
            <Moon className="h-[18px] w-[18px]" />
          )}
          {!collapsed && (
            <span>{mounted && theme === "dark" ? tc("themeLight") : tc("themeDark")}</span>
          )}
        </button>

        {!BETA_PUBLIC_ACCESS_ENABLED && (
          <button
            type="button"
            data-tour="user-menu"
            onClick={() => window.location.href = "/api/auth/logout"}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-muted hover:text-sidebar-foreground"
          >
            <LogOut className="h-[18px] w-[18px]" />
            {!collapsed && <span>{ta("logout")}</span>}
          </button>
        )}

        {/* Upgrade prompt for community tier */}
        {!collapsed && tier === "community" && (
          <Link
            href="/settings/billing"
            className="mt-2 flex items-center gap-2 rounded-lg bg-sidebar-muted px-3 py-2.5 text-xs text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/10 hover:text-sidebar-accent"
          >
            <Sparkles className="h-4 w-4 text-amber-400" />
            <span className="font-medium">{tc("upgradeProfessional")}</span>
          </Link>
        )}

        {/* Powered by Aifya */}
        {!collapsed && (
          <p className="pt-2 text-center text-[10px] text-sidebar-foreground/30">
            {tc("poweredBy")}
          </p>
        )}
      </div>
    </aside>
  );
}
