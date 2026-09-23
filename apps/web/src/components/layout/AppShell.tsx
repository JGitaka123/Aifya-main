"use client";

import { useCallback, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Sidebar } from "./Sidebar";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { CommandPalette } from "@/components/ui/CommandPalette";
import { LicenseProvider, useLicenseContext } from "@/components/licensing/LicenseProvider";
import { UpdateChecker } from "@/components/licensing/UpdateChecker";
import { LicenseExpiryBanner } from "@/components/licensing/UpgradePrompt";
import { useTelemetry } from "@/hooks/useTelemetry";

/**
 * Inner shell that consumes LicenseContext for banners and telemetry.
 * @param props.children - Page content
 * @returns Inner layout with license banners
 */
function AppShellInner({ children }: { children: ReactNode }) {
  const t = useTranslations("common");
  const { daysRemaining, inGracePeriod } = useLicenseContext();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const closeMobileNavigation = useCallback(() => setMobileNavigationOpen(false), []);
  useTelemetry();

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <a
        href="#main-content"
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg transition-transform focus:translate-y-0"
      >
        {t("skipToContent")}
      </a>
      {mobileNavigationOpen && (
        <button
          type="button"
          aria-label={t("closeNavigation")}
          className="fixed inset-0 z-[60] bg-slate-950/40 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileNavigationOpen(false)}
        />
      )}
      <Sidebar
        mobileOpen={mobileNavigationOpen}
        onMobileClose={closeMobileNavigation}
      />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <LicenseExpiryBanner
          daysRemaining={daysRemaining}
          inGracePeriod={inGracePeriod}
        />
        <UpdateChecker />
        <WorkspaceHeader
          navigationOpen={mobileNavigationOpen}
          onOpenNavigation={() => setMobileNavigationOpen(true)}
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto bg-background outline-none"
        >
          {children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

/**
 * Main application shell with sidebar, command palette, and license enforcement.
 * Wraps everything in LicenseProvider for tier-aware rendering.
 * @param props.children - Page content
 * @returns App shell layout
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <LicenseProvider>
      <AppShellInner>{children}</AppShellInner>
    </LicenseProvider>
  );
}
