"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { FileQuestion, Home } from "lucide-react";

/**
 * Branded, localized, dark-mode-aware 404 for unmatched routes under a locale
 * (QA F19 — replaces the default unstyled Next.js 404).
 *
 * @returns Not-found page
 */
export default function NotFound() {
  const t = useTranslations("notFound");
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-full bg-muted p-4">
        <FileQuestion className="h-10 w-10 text-muted-foreground" />
      </div>
      <p className="text-5xl font-bold text-foreground">404</p>
      <h1 className="text-xl font-semibold text-foreground">{t("title")}</h1>
      <p className="max-w-md text-sm text-muted-foreground">{t("message")}</p>
      <Link
        href="/"
        className="mt-2 inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
      >
        <Home className="h-4 w-4" />
        {t("backHome")}
      </Link>
    </div>
  );
}
