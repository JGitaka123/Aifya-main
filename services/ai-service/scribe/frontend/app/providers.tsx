"use client";

import { ReactNode, useState } from "react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ToastProvider } from "@/components/Toast";
import OfflineIndicator from "@/components/OfflineIndicator";
import SessionTimeoutModal from "@/components/SessionTimeoutModal";
import KeyboardShortcutsHelp from "@/components/KeyboardShortcutsHelp";
import CommandPalette from "@/components/CommandPalette";
import Breadcrumbs from "@/components/Breadcrumbs";
import RouteProgressBar from "@/components/RouteProgressBar";
import { useSessionTimeout } from "@/hooks/useSessionTimeout";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { usePathname, useRouter } from "next/navigation";

function SessionManager({ children }: { children: ReactNode }) {
  const { isAuthenticated, logout, tokenExpiryMinutes } = useAuth();
  const [showShortcuts, setShowShortcuts] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const { showWarning, remainingSeconds, extendSession, dismissWarning } = useSessionTimeout({
    tokenExpiryMinutes,
    warningMinutesBefore: 2,
    onExpired: logout,
    isAuthenticated,
  });

  // Determine current page for context-aware shortcuts
  const currentPage = pathname.startsWith("/clinician")
    ? "clinician"
    : pathname.startsWith("/billing")
    ? "billing"
    : pathname.startsWith("/admin")
    ? "admin"
    : pathname.startsWith("/analytics")
    ? "analytics"
    : undefined;

  // Global keyboard shortcuts
  useKeyboardShortcuts([
    {
      key: "ctrl+/",
      description: "Toggle keyboard shortcuts help",
      handler: () => setShowShortcuts((prev) => !prev),
    },
    {
      key: "escape",
      description: "Close dialogs",
      handler: () => setShowShortcuts(false),
      enabled: showShortcuts,
    },
    {
      key: "ctrl+h",
      description: "Go to Home",
      handler: () => router.push("/"),
      enabled: isAuthenticated,
    },
  ]);

  return (
    <>
      {/* Route transition progress bar */}
      <RouteProgressBar />

      {/* Breadcrumbs */}
      {isAuthenticated && pathname !== "/" && pathname !== "/login" && (
        <div className="print:hidden">
          <Breadcrumbs />
        </div>
      )}

      {children}

      {/* Command Palette (Ctrl+K) */}
      <CommandPalette />

      {/* Session timeout warning */}
      {showWarning && (
        <SessionTimeoutModal
          remainingSeconds={remainingSeconds}
          onExtend={extendSession}
          onDismiss={dismissWarning}
          onLogout={logout}
        />
      )}

      {/* Keyboard shortcuts help */}
      <KeyboardShortcutsHelp
        isOpen={showShortcuts}
        onClose={() => setShowShortcuts(false)}
        page={currentPage as any}
      />
    </>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>
        <SessionManager>
          {children}
          <OfflineIndicator />
        </SessionManager>
      </ToastProvider>
    </AuthProvider>
  );
}
