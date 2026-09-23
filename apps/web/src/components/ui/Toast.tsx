"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** Toast variant. */
export type ToastVariant = "success" | "error" | "info";

/** Toast item shape. */
export interface ToastItem {
  id: string;
  variant: ToastVariant;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 4000;

/**
 * Hook to read the toast API. Must be used inside a `<ToastProvider>`.
 *
 * @returns Toast API
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside <ToastProvider>");
  }
  return ctx;
}

/**
 * Provider that exposes a `useToast()` hook and renders the live toast stack
 * via React portal. Auto-dismisses after 4 seconds. Stack is bottom-right.
 *
 * @param children - App tree
 * @returns Toast provider component
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : String(Date.now() + Math.random());
      setItems((prev) => [...prev, { id, variant, message }]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((t) => t.id !== id));
      }, AUTO_DISMISS_MS);
    },
    [],
  );

  const value: ToastContextValue = {
    toast,
    success: (m) => toast(m, "success"),
    error: (m) => toast(m, "error"),
    info: (m) => toast(m, "info"),
    dismiss,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted &&
        createPortal(
          <div
            className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[min(360px,calc(100vw-2.5rem))] flex-col gap-2"
            aria-live="polite"
            aria-atomic="false"
          >
            {items.map((t) => (
              <ToastCard key={t.id} item={t} onDismiss={dismiss} />
            ))}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  );
}

/**
 * Single toast card.
 *
 * @param item - Toast item
 * @param onDismiss - Dismiss handler
 * @returns Toast card
 */
function ToastCard({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const Icon =
    item.variant === "success"
      ? CheckCircle2
      : item.variant === "error"
        ? AlertTriangle
        : Info;
  const styles: Record<ToastVariant, string> = {
    success:
      "bg-green-50 border-green-200 text-green-900 dark:bg-green-950/80 dark:border-green-900 dark:text-green-100",
    error:
      "bg-red-50 border-red-200 text-red-900 dark:bg-red-950/80 dark:border-red-900 dark:text-red-100",
    info: "bg-card border-border text-foreground",
  };
  const iconColor: Record<ToastVariant, string> = {
    success: "text-green-600 dark:text-green-400",
    error: "text-red-600 dark:text-red-400",
    info: "text-primary",
  };
  return (
    <div
      role="status"
      className={cn(
        "pointer-events-auto flex animate-[fade-in_0.2s_ease-out] items-start gap-2 rounded-lg border px-3 py-2 text-sm shadow-lg",
        styles[item.variant],
      )}
    >
      <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", iconColor[item.variant])} />
      <p className="flex-1">{item.message}</p>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => onDismiss(item.id)}
        className="rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
