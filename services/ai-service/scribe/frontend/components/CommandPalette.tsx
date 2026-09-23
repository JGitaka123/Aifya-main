"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  category: string;
  icon?: string;
  action: () => void;
  roles?: string[];
  keywords?: string[];
}

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

  // Toggle with Ctrl+K
  useKeyboardShortcuts([
    {
      key: "ctrl+k",
      description: "Open command palette",
      handler: () => {
        setIsOpen((prev) => !prev);
        setQuery("");
        setSelectedIndex(0);
      },
    },
  ]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const commands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [
      // Navigation
      { id: "nav-home", label: "Go to Home", category: "Navigation", action: () => router.push("/"), keywords: ["dashboard", "main"] },
      { id: "nav-clinician", label: "Go to Clinician Console", category: "Navigation", action: () => router.push("/clinician"), roles: ["clinician", "superadmin"], keywords: ["scribe", "soap", "recording"] },
      { id: "nav-billing", label: "Go to Billing Dashboard", category: "Navigation", action: () => router.push("/billing"), roles: ["billing_admin", "facility_admin", "superadmin"], keywords: ["claims", "scrub"] },
      { id: "nav-analytics", label: "Go to Analytics", category: "Navigation", action: () => router.push("/analytics"), roles: ["billing_admin", "facility_admin", "superadmin"], keywords: ["charts", "reports", "trends"] },
      { id: "nav-admin", label: "Go to Admin Panel", category: "Navigation", action: () => router.push("/admin"), roles: ["facility_admin", "superadmin"], keywords: ["users", "audit", "health"] },
      { id: "nav-profile", label: "Go to Profile & Settings", category: "Navigation", action: () => router.push("/profile"), keywords: ["account", "password", "settings", "license"] },

      // Actions
      { id: "act-refresh", label: "Refresh Page", description: "Reload the current page", category: "Actions", action: () => window.location.reload(), keywords: ["reload"] },
      { id: "act-logout", label: "Sign Out", description: "End your session", category: "Actions", action: logout, keywords: ["exit", "leave"] },

      // Help
      { id: "help-shortcuts", label: "Keyboard Shortcuts", description: "View all keyboard shortcuts", category: "Help", action: () => { setIsOpen(false); document.dispatchEvent(new KeyboardEvent("keydown", { key: "/", ctrlKey: true })); }, keywords: ["keys", "hotkeys"] },
    ];

    // Filter by role
    return items.filter((item) => {
      if (!item.roles) return true;
      return user && item.roles.includes(user.role);
    });
  }, [router, user, logout]);

  // Filter by search query
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(q) ||
        cmd.description?.toLowerCase().includes(q) ||
        cmd.category.toLowerCase().includes(q) ||
        cmd.keywords?.some((k) => k.includes(q))
    );
  }, [commands, query]);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [filtered]);

  // Scroll selected item into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const selected = list.children[selectedIndex] as HTMLElement;
    if (selected) selected.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const executeCommand = useCallback(
    (cmd: CommandItem) => {
      setIsOpen(false);
      setQuery("");
      cmd.action();
    },
    []
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      executeCommand(filtered[selectedIndex]);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  if (!isOpen || !isAuthenticated) return null;

  // Group by category
  const grouped = filtered.reduce<Record<string, CommandItem[]>>((acc, cmd) => {
    (acc[cmd.category] = acc[cmd.category] || []).push(cmd);
    return acc;
  }, {});

  let flatIndex = 0;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-start justify-center pt-[15vh] z-[200] p-4 animate-fade-in"
      onClick={() => setIsOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden border border-slate-200 dark:border-slate-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center border-b border-slate-200 dark:border-slate-700 px-4">
          <svg className="w-5 h-5 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search commands..."
            className="w-full px-3 py-4 text-sm bg-transparent outline-none text-slate-900 dark:text-slate-100 placeholder:text-slate-400"
            autoComplete="off"
          />
          <kbd className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded text-xs font-mono text-slate-500 flex-shrink-0">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-72 overflow-y-auto py-2">
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              No commands found for &ldquo;{query}&rdquo;
            </div>
          ) : (
            Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <div className="px-4 py-1.5 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                  {category}
                </div>
                {items.map((cmd) => {
                  const idx = flatIndex++;
                  return (
                    <button
                      key={cmd.id}
                      onClick={() => executeCommand(cmd)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${
                        idx === selectedIndex
                          ? "bg-medical-blue/10 text-medical-blue dark:bg-medical-blue/20"
                          : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{cmd.label}</p>
                        {cmd.description && (
                          <p className="text-xs text-slate-400 truncate">{cmd.description}</p>
                        )}
                      </div>
                      {idx === selectedIndex && (
                        <kbd className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-600 rounded text-xs font-mono text-slate-400 flex-shrink-0">
                          Enter
                        </kbd>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 dark:border-slate-700 px-4 py-2 flex items-center gap-4 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">&uarr;&darr;</kbd> navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">Enter</kbd> select
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">Esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
