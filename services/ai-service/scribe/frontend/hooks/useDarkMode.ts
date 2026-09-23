"use client";

import { useState, useEffect, useCallback } from "react";

type Theme = "light" | "dark" | "system";

export function useDarkMode() {
  const [theme, setThemeState] = useState<Theme>("system");
  const [isDark, setIsDark] = useState(false);

  // Apply dark class to html element
  const applyTheme = useCallback((dark: boolean) => {
    setIsDark(dark);
    if (dark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  // Initialize from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("aifya_theme") as Theme | null;
    const initial = saved || "system";
    setThemeState(initial);

    if (initial === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      applyTheme(prefersDark);
    } else {
      applyTheme(initial === "dark");
    }
  }, [applyTheme]);

  // Listen for system preference changes
  useEffect(() => {
    if (theme !== "system") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => applyTheme(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, applyTheme]);

  const setTheme = useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme);
      localStorage.setItem("aifya_theme", newTheme);

      if (newTheme === "system") {
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        applyTheme(prefersDark);
      } else {
        applyTheme(newTheme === "dark");
      }
    },
    [applyTheme]
  );

  const toggleDark = useCallback(() => {
    setTheme(isDark ? "light" : "dark");
  }, [isDark, setTheme]);

  return { theme, isDark, setTheme, toggleDark };
}
