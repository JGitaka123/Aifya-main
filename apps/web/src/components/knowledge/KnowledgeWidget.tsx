"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { BookOpen, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useKnowledgeContext } from "@/hooks/useKnowledge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import type { CitationSource, DocumentCategory } from "@aifya/shared";

interface KnowledgeWidgetProps {
  /** The clinical context query to search for relevant guidelines. */
  contextQuery: string;
  /** Additional CSS classes for the outer container. */
  className?: string;
}

/** Map document categories to StatusBadge variants. */
const CATEGORY_VARIANT: Record<
  DocumentCategory,
  "default" | "success" | "info" | "purple" | "cyan" | "warning" | "orange" | "teal" | "pink"
> = {
  policy: "purple",
  sop: "info",
  guideline: "success",
  manual: "cyan",
  protocol: "teal",
  formulary: "warning",
  circular: "orange",
  training: "pink",
  other: "default",
};

/**
 * Returns the Tailwind background class for a relevance score bar.
 *
 * @param score - Relevance score between 0 and 1
 * @returns Tailwind background class string
 */
function relevanceBarColor(score: number): string {
  if (score > 0.7) return "bg-green-500 dark:bg-green-400";
  if (score > 0.4) return "bg-amber-500 dark:bg-amber-400";
  return "bg-muted-foreground/40";
}

/**
 * Contextual sidebar widget that surfaces relevant institutional documents
 * based on the current clinical context. For example, when a doctor is writing
 * notes about pneumonia, this widget auto-surfaces the hospital's pneumonia
 * treatment protocol.
 *
 * @param props - contextQuery and optional className
 * @returns Collapsible knowledge widget card
 */
export function KnowledgeWidget({ contextQuery, className }: KnowledgeWidgetProps) {
  const t = useTranslations("knowledge");
  const [isExpanded, setIsExpanded] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState("");

  // Debounce contextQuery by 500ms
  useEffect(() => {
    if (!contextQuery.trim()) {
      setDebouncedQuery("");
      return;
    }

    const timer = setTimeout(() => {
      setDebouncedQuery(contextQuery.trim());
    }, 500);

    return () => clearTimeout(timer);
  }, [contextQuery]);

  const { data: citations, isLoading } = useKnowledgeContext(
    debouncedQuery,
    debouncedQuery.length > 0,
  );

  const displayCitations = citations?.slice(0, 3) ?? [];

  return (
    <div
      className={cn(
        "bg-card rounded-xl shadow-[var(--shadow-card)] p-4",
        className,
      )}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">
            {t("relatedGuidelines")}
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {/* Collapsible content */}
      {isExpanded && (
        <div className="mt-3 max-h-64 overflow-y-auto">
          {isLoading ? (
            <WidgetSkeleton />
          ) : displayCitations.length === 0 ? (
            <p className="py-2 text-xs text-muted-foreground">
              {t("noRelatedDocuments")}
            </p>
          ) : (
            <>
              <ul className="space-y-2.5">
                {displayCitations.map((citation) => (
                  <CitationRow key={citation.document_id} citation={citation} />
                ))}
              </ul>

              {/* View all link */}
              <Link
                href="/knowledge"
                className="mt-3 block text-xs font-medium text-primary hover:text-primary/80 transition-colors"
              >
                {t("viewAllInKnowledgeBase")}
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Single citation row inside the knowledge widget.
 *
 * @param props - citation data
 * @returns Citation list item with title, category, section, and relevance bar
 */
function CitationRow({ citation }: { citation: CitationSource }) {
  const variant = CATEGORY_VARIANT[citation.category] ?? "default";

  return (
    <li className="space-y-1">
      {/* Title + category */}
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/knowledge/${citation.document_id}`}
          className="text-xs font-medium text-foreground hover:text-primary transition-colors truncate flex-1"
          title={citation.document_title}
        >
          {citation.document_title}
        </Link>
        <StatusBadge variant={variant} size="xs">
          {citation.category}
        </StatusBadge>
      </div>

      {/* Section name */}
      {citation.section && (
        <p className="text-[11px] text-muted-foreground truncate">
          {citation.section}
        </p>
      )}

      {/* Relevance score bar */}
      <div className="flex items-center gap-2">
        <div className="h-1 flex-1 rounded-full bg-muted">
          <div
            className={cn(
              "h-1 rounded-full transition-all",
              relevanceBarColor(citation.relevance_score),
            )}
            style={{ width: `${Math.round(citation.relevance_score * 100)}%` }}
          />
        </div>
        <span className="text-[10px] text-muted-foreground tabular-nums">
          {Math.round(citation.relevance_score * 100)}%
        </span>
      </div>
    </li>
  );
}

/**
 * Loading skeleton for the widget content area.
 *
 * @returns Three skeleton lines mimicking citation rows
 */
function WidgetSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-2 w-1/2" />
          <Skeleton className="h-1 w-full" />
        </div>
      ))}
    </div>
  );
}
