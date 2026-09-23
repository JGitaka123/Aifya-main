"use client";

import { useState } from "react";
import { Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { HelpChat } from "@/components/help/HelpChat";

/**
 * Floating AI Help Bot.
 * A FAB at the bottom-right opens a chat drawer. The conversation itself lives
 * in HelpChat so the User Guide can embed the same assistant. Chat history is
 * session-only.
 *
 * @returns Help bot component
 */
export function HelpBot() {
  const t = useTranslations("helpBot");
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* FAB */}
      <button
        type="button"
        data-tour="help-bot"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("fabLabel")}
        className={cn(
          "fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center",
          "rounded-full bg-primary text-primary-foreground shadow-lg",
          "transition-transform hover:scale-105 focus-visible:outline-none",
          "focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
        )}
      >
        {open ? <X className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
      </button>

      {/* Drawer */}
      {open && (
        <div
          className={cn(
            "fixed bottom-20 right-5 z-40 flex w-[min(380px,calc(100vw-2.5rem))] flex-col",
            "max-h-[min(560px,calc(100vh-7rem))]",
            "rounded-xl border border-border bg-card shadow-xl",
          )}
          role="dialog"
          aria-label={t("drawerTitle")}
        >
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">
                {t("drawerTitle")}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("close")}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <HelpChat
            className="min-h-0 flex-1"
            showTour
            onAction={() => setOpen(false)}
          />
        </div>
      )}
    </>
  );
}