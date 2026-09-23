"use client";

import { Menu, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/components/providers/AuthProvider";

interface WorkspaceHeaderProps {
  navigationOpen: boolean;
  onOpenNavigation: () => void;
}

/**
 * Persistent workspace header with mobile navigation and global search access.
 *
 * @param props.navigationOpen - Whether the mobile navigation is open
 * @param props.onOpenNavigation - Opens the mobile navigation drawer
 * @returns Responsive application header
 */
export function WorkspaceHeader({
  navigationOpen,
  onOpenNavigation,
}: WorkspaceHeaderProps) {
  const t = useTranslations("common");
  const { user } = useAuth();
  const initials = user?.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "A";

  const openCommandPalette = () => {
    window.dispatchEvent(new CustomEvent("aifya:open-command-palette"));
  };

  return (
    <header className="flex h-[72px] flex-shrink-0 items-center gap-3 border-b border-border bg-card/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-card/90 sm:px-6">
      <button
        type="button"
        onClick={onOpenNavigation}
        aria-label={t("openNavigation")}
        aria-controls="primary-navigation"
        aria-expanded={navigationOpen}
        className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-background text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="min-w-0 lg:w-52">
        <p className="truncate text-sm font-semibold text-foreground lg:text-base">
          {t("clinicalWorkspace")}
        </p>
        <p className="hidden truncate text-xs text-muted-foreground lg:block">
          {t("workspaceSubtitle")}
        </p>
      </div>

      <button
        type="button"
        onClick={openCommandPalette}
        className="group mx-auto flex h-11 min-w-0 max-w-xl flex-1 items-center gap-2 rounded-lg border border-input bg-background px-3 text-left text-sm text-muted-foreground shadow-[inset_0_1px_2px_rgb(18_92_67_/_0.03)] transition-all hover:border-primary/35 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={t("openSearch")}
      >
        <Search className="h-4 w-4 flex-shrink-0 transition-colors group-hover:text-primary" />
        <span className="truncate">{t("searchPlaceholder")}</span>
        <kbd className="ml-auto hidden rounded border border-border bg-card px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground sm:inline-flex">
          Ctrl K
        </kbd>
      </button>

      <div className="flex flex-shrink-0 items-center gap-2 sm:pl-2">
        <div className="hidden text-right md:block">
          <p className="max-w-36 truncate text-xs font-semibold text-foreground">
            {user?.name ?? t("workspaceUser")}
          </p>
          <p className="max-w-36 truncate text-[11px] text-muted-foreground">
            {user?.roles[0] ?? t("careTeam")}
          </p>
        </div>
        <div
          className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground ring-4 ring-primary/10"
          aria-hidden="true"
        >
          {initials}
        </div>
      </div>
    </header>
  );
}
