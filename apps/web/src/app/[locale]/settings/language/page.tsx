"use client";

import { useLocale, useTranslations } from "next-intl";
import { Check, Globe, Languages } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/**
 * Settings -> Language: switch the interface between English and Kiswahili.
 * The change applies immediately and keeps the current page.
 *
 * @returns Language settings page
 */
export default function LanguageSettingsPage() {
  const t = useTranslations("settings.language");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  const options = [
    { value: "en", labelKey: "english" },
    { value: "sw", labelKey: "kiswahili" },
  ] as const;

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold text-foreground">
        <Globe className="h-6 w-6 text-primary" />
        {t("title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("description")}</p>

      <h2 className="mb-3 text-sm font-semibold text-foreground">
        {t("interfaceLanguage")}
      </h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {options.map((option) => {
          const active = locale === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              onClick={() => router.replace(pathname, { locale: option.value })}
              className={cn(
                "flex items-center gap-4 rounded-xl border bg-card p-5 text-left shadow-[var(--shadow-card)] transition-all",
                active
                  ? "border-blue-500 ring-2 ring-blue-200 dark:ring-blue-900"
                  : "border-border hover:border-blue-300 dark:hover:border-blue-700",
              )}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/50">
                <Languages className="h-5 w-5 text-primary" />
              </span>
              <span className="flex-1 font-medium text-foreground">
                {t(option.labelKey)}
              </span>
              {active && <Check className="h-5 w-5 text-blue-600 dark:text-blue-400" />}
            </button>
          );
        })}
      </div>

      <p className="mt-4 text-xs text-muted-foreground">{t("hint")}</p>
    </div>
  );
}
