"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Compass,
  Search,
  Sparkles,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { useTour } from "@/components/help/TourProvider";
import { HelpChat } from "@/components/help/HelpChat";

type GuideCategory =
  | "all"
  | "start"
  | "clinical"
  | "operations"
  | "administration"
  | "governance";

interface GuideCourse {
  id: string;
  category: Exclude<GuideCategory, "all">;
  href: string;
  minutes: number;
  modules: string[];
}

const CATEGORIES: readonly GuideCategory[] = [
  "all",
  "start",
  "clinical",
  "operations",
  "administration",
  "governance",
];

const COURSES: readonly GuideCourse[] = [
  { id: "orientation", category: "start", href: "/", minutes: 8, modules: ["dashboard"] },
  { id: "frontDesk", category: "start", href: "/patients", minutes: 15, modules: ["patients", "registration", "appointments", "referrals"] },
  { id: "clinicalCare", category: "clinical", href: "/opd", minutes: 22, modules: ["opd", "ipd", "emergency"] },
  { id: "diagnostics", category: "clinical", href: "/laboratory", minutes: 18, modules: ["laboratory", "radiology", "theatre", "dental", "mch"] },
  { id: "medicines", category: "clinical", href: "/pharmacy", minutes: 14, modules: ["pharmacy", "inventory"] },
  { id: "revenue", category: "operations", href: "/billing", minutes: 16, modules: ["billing", "insurance"] },
  { id: "finance", category: "administration", href: "/finance", minutes: 24, modules: ["finance", "chartOfAccounts", "glTransactions", "financeReports", "budgets", "fixedAssets", "periods", "reconciliation"] },
  { id: "workforce", category: "administration", href: "/hr", minutes: 20, modules: ["hr", "employees", "leave", "payroll", "payrollReports", "statutory"] },
  { id: "insights", category: "operations", href: "/reports", minutes: 12, modules: ["reports", "analytics", "performance"] },
  { id: "communications", category: "operations", href: "/communications", minutes: 8, modules: ["communications"] },
  { id: "integrations", category: "governance", href: "/integrations/fhir", minutes: 14, modules: ["integrations"] },
  { id: "trials", category: "governance", href: "/trials", minutes: 20, modules: ["trials"] },
  { id: "knowledge", category: "governance", href: "/knowledge", minutes: 8, modules: ["knowledge"] },
  { id: "settings", category: "administration", href: "/settings", minutes: 10, modules: ["settings"] },
];

const STORAGE_PREFIX = "aifya:guide:completed:";

/**
 * Complete, searchable in-app training hub for Aifya users.
 * @returns User guide with courses, progress tracking, tours, and module links
 */
export default function UserGuidePage() {
  const t = useTranslations("userGuide");
  const tn = useTranslations("nav");
  const th = useTranslations("helpBot");
  const { user } = useAuth();
  const { startRecommended } = useTour();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<GuideCategory>("all");
  const [expanded, setExpanded] = useState<string | null>("orientation");
  const [completed, setCompleted] = useState<Set<string>>(new Set());

  const storageKey = `${STORAGE_PREFIX}${user?.id ?? "beta"}`;

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (!saved) return;
      const parsed: unknown = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        setCompleted(new Set(parsed.filter((id): id is string => typeof id === "string")));
      }
    } catch {
      setCompleted(new Set());
    }
  }, [storageKey]);

  const courses = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return COURSES.filter((course) => {
      if (category !== "all" && course.category !== category) return false;
      if (!normalizedQuery) return true;
      const rawLessons: unknown = t.raw(`courses.${course.id}.lessons`);
      const lessons = Array.isArray(rawLessons)
        ? rawLessons.filter((lesson): lesson is string => typeof lesson === "string")
        : [];
      const searchableText = [
        t(`courses.${course.id}.title`),
        t(`courses.${course.id}.summary`),
        ...course.modules.map((module) => tn(module)),
        ...lessons,
      ]
        .join(" ")
        .toLocaleLowerCase();
      return searchableText.includes(normalizedQuery);
    });
  }, [category, query, t, tn]);

  const completionPercent = Math.round((completed.size / COURSES.length) * 100);

  const toggleCompleted = (courseId: string) => {
    setCompleted((current) => {
      const next = new Set(current);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify([...next]));
      } catch {
        // Training remains usable when browser storage is unavailable.
      }
      return next;
    });
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-6 p-5 sm:p-6 lg:p-8">
      <section className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl border-l-[3px] border-primary pl-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-primary">
            <BookOpenCheck className="h-4 w-4" />
            {t("eyebrow")}
          </div>
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{t("title")}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("subtitle")}</p>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-2 flex items-center justify-between text-xs font-medium">
            <span className="text-foreground">{t("progress")}</span>
            <span className="tabular-nums text-primary">{completed.size}/{COURSES.length}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted" aria-label={t("progressLabel", { percent: completionPercent })}>
            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${completionPercent}%` }} />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <div className="mb-3 flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-foreground">{th("panelTitle")}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">{th("panelHint")}</p>
          </div>
        </div>
        <HelpChat
          className="h-[360px] rounded-lg border border-border bg-background"
          quickPrompts={[th("quickPromptStart"), th("quickPromptGuide"), th("quickPromptPatient")]}
        />
      </section>

      <section className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <label className="relative min-w-0 flex-1 lg:max-w-xl">
          <span className="sr-only">{t("searchLabel")}</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("searchPlaceholder")}
            className="h-11 w-full rounded-lg border border-input bg-card pl-10 pr-3 text-sm text-foreground shadow-[var(--shadow-card)] outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <button
          type="button"
          onClick={startRecommended}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary-hover"
        >
          <Compass className="h-4 w-4" />
          {t("startTour")}
        </button>
      </section>

      <div className="flex gap-1 overflow-x-auto rounded-lg bg-muted/70 p-1" role="tablist" aria-label={t("categoriesLabel")}>
        {CATEGORIES.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={category === item}
            onClick={() => setCategory(item)}
            className={cn(
              "min-h-9 shrink-0 rounded-md px-3 text-sm font-medium transition-colors",
              category === item
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`categories.${item}`)}
          </button>
        ))}
      </div>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">{t("trainingLibrary")}</h2>
          <span className="text-xs text-muted-foreground">{t("courseCount", { count: courses.length })}</span>
        </div>

        {courses.length === 0 ? (
          <div className="border-y border-border py-16 text-center">
            <Search className="mx-auto h-8 w-8 text-muted-foreground/50" />
            <p className="mt-3 text-sm font-medium text-foreground">{t("emptyTitle")}</p>
            <p className="mt-1 text-sm text-muted-foreground">{t("emptyDescription")}</p>
          </div>
        ) : (
          <div className="grid items-start gap-4 lg:grid-cols-2">
            {courses.map((course) => {
              const navItem = NAV_ITEMS.find((item) => item.href === course.href);
              const Icon = navItem?.icon ?? BookOpenCheck;
              const isComplete = completed.has(course.id);
              const isExpanded = expanded === course.id;
              const rawLessons: unknown = t.raw(`courses.${course.id}.lessons`);
              const lessons = Array.isArray(rawLessons)
                ? rawLessons.filter((lesson): lesson is string => typeof lesson === "string")
                : [];

              return (
                <article key={course.id} className="overflow-hidden rounded-lg border border-border bg-card shadow-[var(--shadow-card)]">
                  <button
                    type="button"
                    onClick={() => setExpanded(isExpanded ? null : course.id)}
                    aria-expanded={isExpanded}
                    className="flex w-full items-start gap-4 p-5 text-left hover:bg-muted/30"
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-foreground">{t(`courses.${course.id}.title`)}</span>
                        {isComplete && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                            <Check className="h-3 w-3" /> {t("completed")}
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-sm leading-5 text-muted-foreground">{t(`courses.${course.id}.summary`)}</span>
                      <span className="mt-3 flex flex-wrap items-center gap-1.5">
                        {course.modules.map((module) => (
                          <span key={module} className="rounded bg-muted px-2 py-1 text-[11px] font-medium text-muted-foreground">
                            {tn(module)}
                          </span>
                        ))}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                      <Clock3 className="h-3.5 w-3.5" />
                      {t("minutes", { count: course.minutes })}
                      <ChevronDown className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-180")} />
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-border px-5 py-4">
                      <h3 className="text-xs font-semibold uppercase text-muted-foreground">{t("lessonOutline")}</h3>
                      <ol className="mt-3 space-y-3">
                        {lessons.map((lesson, index) => (
                          <li key={lesson} className="flex gap-3 text-sm leading-5 text-foreground">
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
                              {index + 1}
                            </span>
                            {lesson}
                          </li>
                        ))}
                      </ol>
                      <div className="mt-5 flex flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                        <button
                          type="button"
                          onClick={() => toggleCompleted(course.id)}
                          className={cn(
                            "inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold transition-colors",
                            isComplete
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300"
                              : "border-input bg-background text-foreground hover:bg-muted",
                          )}
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          {isComplete ? t("markIncomplete") : t("markComplete")}
                        </button>
                        <Link
                          href={course.href}
                          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-hover"
                        >
                          {t("openModule")}
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
