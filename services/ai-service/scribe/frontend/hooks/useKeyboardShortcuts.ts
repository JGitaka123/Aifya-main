"use client";

import { useEffect, useCallback, useRef } from "react";

interface ShortcutConfig {
  /** Key combination like "ctrl+r", "ctrl+shift+s", "escape" */
  key: string;
  /** Handler function */
  handler: () => void;
  /** Whether to prevent default browser behavior */
  preventDefault?: boolean;
  /** Only active when this condition is true */
  enabled?: boolean;
  /** Description for help overlay */
  description?: string;
}

/**
 * Custom hook for keyboard shortcuts.
 * Supports modifier keys (ctrl, shift, alt, meta) and single keys.
 */
export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in inputs
    const target = event.target as HTMLElement;
    const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable;

    for (const shortcut of shortcutsRef.current) {
      if (shortcut.enabled === false || !shortcut.key) continue;
      const parts = shortcut.key.toLowerCase().split("+");
      const key = parts[parts.length - 1];
      const needsCtrl = parts.includes("ctrl") || parts.includes("control");
      const needsShift = parts.includes("shift");
      const needsAlt = parts.includes("alt");
      const needsMeta = parts.includes("meta") || parts.includes("cmd");

      const ctrlMatch = needsCtrl === (event.ctrlKey || event.metaKey);
      const shiftMatch = needsShift === event.shiftKey;
      const altMatch = needsAlt === event.altKey;
      const keyMatch = event.key.toLowerCase() === key;

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        // Allow escape in inputs, but block other shortcuts
        if (isInput && key !== "escape") continue;

        if (shortcut.preventDefault !== false) {
          event.preventDefault();
          event.stopPropagation();
        }
        shortcut.handler();
        return;
      }
    }
  }, []);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Format shortcut key for display (platform-aware)
 */
export function formatShortcutKey(key: string): string {
  const isMac = typeof navigator !== "undefined" && /Mac/.test(navigator.userAgent);
  return key
    .replace(/ctrl/i, isMac ? "\u2318" : "Ctrl")
    .replace(/shift/i, isMac ? "\u21E7" : "Shift")
    .replace(/alt/i, isMac ? "\u2325" : "Alt")
    .replace(/\+/g, isMac ? "" : "+")
    .replace(/escape/i, "Esc");
}
