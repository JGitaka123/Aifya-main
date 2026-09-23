"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Compass, ExternalLink, Send, Sparkles } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { normalizeNavigationPath } from "@/lib/navigation";
import { useTour } from "@/components/help/TourProvider";

/** Suggested in-app navigation link returned by the help bot. */
interface SuggestedLink {
  label: string;
  href: string;
}

/** Help bot answer. */
interface AnswerResponse {
  answer: string;
  suggested_links: SuggestedLink[];
  confidence: number;
  model: string;
}

/** Single chat turn in the local history. */
interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  links?: SuggestedLink[];
}

interface HelpChatProps {
  /** Sizing classes for the conversation container. */
  className?: string;
  /** Questions offered before the first turn; defaults to the standard set. */
  quickPrompts?: readonly string[];
  /** Render the guided-tour shortcut in the empty state. */
  showTour?: boolean;
  /** Called after opening a link or starting the tour, e.g. to close a drawer. */
  onAction?: () => void;
}

/**
 * Aifya Care conversation surface.
 *
 * Shared by the floating help button and the User Guide so both talk to the
 * same /api/v1/help/ask endpoint, keep the same session-only history, and
 * report the screen they were asked from so answers stay grounded.
 *
 * @param className - Sizing classes for the conversation container
 * @param quickPrompts - Suggested questions for the empty state
 * @param showTour - Render the guided-tour shortcut
 * @param onAction - Invoked after navigating away or starting the tour
 * @returns Help conversation panel
 */
export function HelpChat({
  className,
  quickPrompts,
  showTour = false,
  onAction,
}: HelpChatProps) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("helpBot");
  const { startRecommended } = useTour();
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const prompts =
    quickPrompts ??
    [
      t("quickPromptPayroll"),
      t("quickPromptPayment"),
      t("quickPromptPatient"),
      t("quickPromptClaims"),
    ];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, pending]);

  /**
   * Send a question to the help bot.
   *
   * @param queryText - Question to send
   */
  const ask = async (queryText: string): Promise<void> => {
    const trimmed = queryText.trim();
    if (!trimmed || pending) return;

    setHistory((h) => [
      ...h,
      { id: crypto.randomUUID(), role: "user", text: trimmed },
    ]);
    setInput("");
    setPending(true);

    try {
      const res = await apiFetch<AnswerResponse>("/api/v1/help/ask", {
        method: "POST",
        body: JSON.stringify({
          query: trimmed,
          context: normalizeNavigationPath(pathname),
        }),
      });
      setHistory((h) => [
        ...h,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: res.answer,
          links: res.suggested_links,
        },
      ]);
    } catch {
      setHistory((h) => [
        ...h,
        { id: crypto.randomUUID(), role: "assistant", text: t("errorFallback") },
      ]);
    } finally {
      setPending(false);
    }
  };

  const openLink = (href: string): void => {
    router.push(href);
    onAction?.();
  };

  return (
    <div className={cn("flex flex-col", className)}>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {history.length === 0 ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">{t("intro")}</p>
            {showTour && (
              <button
                type="button"
                onClick={() => {
                  startRecommended();
                  onAction?.();
                }}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
              >
                <Compass className="h-4 w-4" />
                {t("takeTheTour")}
              </button>
            )}
            <div className="flex flex-col gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void ask(prompt)}
                  className="rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          history.map((turn) => (
            <div
              key={turn.id}
              className={cn(
                "flex flex-col gap-2",
                turn.role === "user" ? "items-end" : "items-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
                  turn.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground",
                )}
              >
                {turn.text}
              </div>
              {turn.role === "assistant" && turn.links && turn.links.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {turn.links.map((link) => (
                    <button
                      key={link.href}
                      type="button"
                      onClick={() => openLink(link.href)}
                      className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-xs font-medium transition-colors hover:bg-muted"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {link.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
        {pending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3 w-3 animate-pulse" />
            {t("thinking")}
          </div>
        )}
      </div>

      <form
        className="flex items-center gap-2 border-t border-border px-3 py-2"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          void ask(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t("inputPlaceholder")}
          maxLength={1000}
          aria-label={t("inputPlaceholder")}
          className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          aria-label={t("send")}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}