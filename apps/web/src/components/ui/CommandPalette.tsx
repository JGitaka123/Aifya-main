"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import {
  Search,
  Users,
  X,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, PRIMARY_COMMAND_HREFS } from "@/lib/navigation";
import { useLicenseContext } from "@/components/licensing/LicenseProvider";
import type { PatientListResponse } from "@aifya/shared";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  action: () => void;
  group: "patients" | "navigation";
}

/**
 * Cmd+K command palette for global search.
 * Per CLAUDE.md: primary navigation, must search patients, actions, modules.
 * @returns Command palette dialog
 */
export function CommandPalette() {
  const t = useTranslations("nav");
  const tp = useTranslations("patients");
  const tc = useTranslations("common");
  const router = useRouter();
  const { hasModule } = useLicenseContext();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [patientResults, setPatientResults] = useState<CommandItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((wasOpen) => {
          if (!wasOpen && document.activeElement instanceof HTMLElement) {
            previouslyFocusedRef.current = document.activeElement;
          }
          return !wasOpen;
        });
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    const handleOpen = () => {
      if (document.activeElement instanceof HTMLElement) {
        previouslyFocusedRef.current = document.activeElement;
      }
      setOpen(true);
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("aifya:open-command-palette", handleOpen);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("aifya:open-command-palette", handleOpen);
    };
  }, []);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    searchInputRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocusedRef.current?.focus();
      previouslyFocusedRef.current = null;
    };
  }, [open]);

  // Search patients on query change
  useEffect(() => {
    if (!query || query.length < 2) {
      setPatientResults([]);
      return;
    }

    const timeout = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await apiClient.get<PatientListResponse>("/patients", {
          q: query,
          page: "1",
          page_size: "5",
        });
        setPatientResults(
          data.items.map((p) => ({
            id: p.id,
            label: `${p.first_name} ${p.last_name}`,
            description: `${p.mrn} · ${p.phone_number}`,
            icon: <Users className="h-4 w-4" />,
            action: () => {
              router.push(`/patients/${p.id}`);
              setOpen(false);
            },
            group: "patients" as const,
          }))
        );
      } catch {
        setPatientResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [query, router]);

  const navigationItems: CommandItem[] = NAV_ITEMS.filter(
    (item) => !item.module || hasModule(item.module),
  ).map((item) => {
    const Icon = item.icon;
    return {
      id: `nav-${item.key}`,
      label: t(item.key),
      icon: <Icon className="h-4 w-4" />,
      action: () => {
        router.push(item.href);
        setOpen(false);
      },
      group: "navigation" as const,
    };
  });

  // Filter navigation by query
  const filteredNav = query
    ? navigationItems.filter((item) =>
        item.label.toLowerCase().includes(query.toLowerCase()),
      )
    : navigationItems.filter((item) => {
        const href = NAV_ITEMS.find((navItem) => `nav-${navItem.key}` === item.id)?.href;
        return href ? PRIMARY_COMMAND_HREFS.has(href) : false;
      });

  const allItems = [...patientResults, ...filteredNav];

  // Keyboard navigation
  const handleDialogKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Tab") {
      const focusableElements = dialogRef.current?.querySelectorAll<HTMLElement>(
        'input, button, [href], [tabindex]:not([tabindex="-1"])',
      );

      if (!focusableElements?.length) return;

      const firstElement = focusableElements.item(0);
      const lastElement = focusableElements.item(
        focusableElements.length - 1,
      );
      if (!firstElement || !lastElement) return;
      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
      return;
    }

    if (!(e.target instanceof HTMLInputElement)) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) =>
        Math.min(i + 1, Math.max(allItems.length - 1, 0)),
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = allItems[selectedIndex];
      if (item) item.action();
    }
  };

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    setSelectedIndex((index) =>
      Math.min(index, Math.max(allItems.length - 1, 0)),
    );
  }, [allItems.length]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50"
        aria-hidden="true"
        onClick={() => setOpen(false)}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={tc("globalSearch")}
        onKeyDown={handleDialogKeyDown}
        className="fixed left-1/2 top-16 z-50 w-[calc(100%_-_2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-card shadow-2xl sm:top-[16%]"
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-border px-4 dark:border-border">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            ref={searchInputRef}
            aria-label={tc("globalSearch")}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tc("searchPlaceholder")}
            className="flex-1 bg-transparent py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground dark:text-foreground"
            autoFocus
          />
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label={tc("close")}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto p-2">
          {isSearching && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              {tc("loading")}
            </p>
          )}

          {/* Patient results */}
          {patientResults.length > 0 && (
            <div className="mb-2">
              <p className="px-3 py-1 text-xs font-semibold uppercase text-muted-foreground">
                {tp("search")}
              </p>
              {patientResults.map((item, i) => (
                <CommandItemRow
                  key={item.id}
                  item={item}
                  isSelected={i === selectedIndex}
                  onClick={item.action}
                />
              ))}
            </div>
          )}

          {/* Navigation */}
          {filteredNav.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-semibold uppercase text-muted-foreground">
                {tc("actions")}
              </p>
              {filteredNav.map((item, i) => (
                <CommandItemRow
                  key={item.id}
                  item={item}
                  isSelected={i + patientResults.length === selectedIndex}
                  onClick={item.action}
                />
              ))}
            </div>
          )}

          {allItems.length === 0 && !isSearching && query.length >= 2 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">
              {tc("noResults")}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function CommandItemRow({
  item,
  isSelected,
  onClick,
}: {
  item: CommandItem;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
        isSelected
          ? "bg-primary/10 text-primary dark:bg-primary/10 dark:text-primary"
          : "text-foreground hover:bg-muted dark:text-foreground dark:hover:bg-muted"
      )}
    >
      <span className="text-muted-foreground">{item.icon}</span>
      <div className="flex-1 text-left">
        <p className="font-medium">{item.label}</p>
        {item.description && (
          <p className="text-xs text-muted-foreground">{item.description}</p>
        )}
      </div>
    </button>
  );
}
