"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { Check, Moon, Palette, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Settings -> Appearance: switch the interface between the light and dark
 * themes. The chosen theme persists through next-themes.
 *
 * @returns Appearance settings page
 */
export default function AppearanceSettingsPage() {
  const t = useTranslations("settings.appearance");
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const options = [
    { value: "light", labelKey: "light", icon: Sun },
    { value: "dark", labelKey: "dark", icon: Moon },
  ] as const;

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold text-foreground">
        <Palette className="h-6 w-6 text-primary" />
        {t("title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("description")}</p>

      <h2 className="mb-3 text-sm font-semibold text-foreground">{t("theme")}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {options.map((option) => {
          const active = mounted && theme === option.value;
          const Icon = option.icon;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              onClick={() => setTheme(option.value)}
              className={cn(
                "flex items-center gap-4 rounded-xl border bg-card p-5 text-left shadow-[var(--shadow-card)] transition-all",
                active
                  ? "border-blue-500 ring-2 ring-blue-200 dark:ring-blue-900"
                  : "border-border hover:border-blue-300 dark:hover:border-blue-700",
              )}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/50">
                <Icon className="h-5 w-5 text-primary" />
              </span>
              <span className="flex-1 font-medium text-foreground">
                {t(option.labelKey)}
              </span>
              {active && <Check className="h-5 w-5 text-blue-600 dark:text-blue-400" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
