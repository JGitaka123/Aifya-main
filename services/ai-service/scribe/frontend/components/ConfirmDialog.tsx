"use client";

import { useEffect, useRef } from "react";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  /** Text for the confirm button */
  confirmLabel?: string;
  /** Text for the cancel button */
  cancelLabel?: string;
  /** Visual variant */
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
  /** Whether the confirm action is in progress */
  loading?: boolean;
}

export default function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) cancelRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const variantStyles = {
    danger: {
      icon: "text-red-600 dark:text-red-400",
      iconBg: "bg-red-100 dark:bg-red-900/30",
      button: "bg-red-600 hover:bg-red-700 text-white",
    },
    warning: {
      icon: "text-orange-600 dark:text-orange-400",
      iconBg: "bg-orange-100 dark:bg-orange-900/30",
      button: "bg-orange-500 hover:bg-orange-600 text-white",
    },
    info: {
      icon: "text-blue-600 dark:text-blue-400",
      iconBg: "bg-blue-100 dark:bg-blue-900/30",
      button: "bg-medical-blue hover:bg-medical-blue-dark text-white",
    },
  };

  const styles = variantStyles[variant];

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] p-4 animate-fade-in"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-message"
    >
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-sm w-full overflow-hidden">
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={`p-2 rounded-full ${styles.iconBg} flex-shrink-0`}>
              <svg className={`w-5 h-5 ${styles.icon}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h3 id="confirm-title" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                {title}
              </h3>
              <p id="confirm-message" className="mt-2 text-sm text-slate-600 dark:text-slate-400">
                {message}
              </p>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 bg-slate-50 dark:bg-slate-800/50 flex gap-3 justify-end border-t border-slate-200 dark:border-slate-700">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-md text-sm hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 ${styles.button}`}
          >
            {loading ? "Processing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
