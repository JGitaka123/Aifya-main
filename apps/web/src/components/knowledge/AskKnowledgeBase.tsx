"use client";

import { useState, useRef, useEffect, useCallback, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import {
  BookOpen,
  Search,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useKnowledgeQuery } from "@/hooks/useKnowledge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type {
  KnowledgeQueryRequest,
  KnowledgeQueryResponse,
  CitationSource,
  DocumentCategory,
} from "@aifya/shared";

/** Props for the AskKnowledgeBase chat component. */
interface AskKnowledgeBaseProps {
  /** Restrict queries to specific documents. */
  documentIds?: string[];
  /** Restrict queries to specific categories. */
  categories?: DocumentCategory[];
  /** Restrict queries to a specific department. */
  department?: string;
  /** Additional CSS classes. */
  className?: string;
}

/** A single conversation entry pairing a user query with the AI response. */
interface ConversationEntry {
  id: string;
  query: string;
  response: KnowledgeQueryResponse;
}

const EXAMPLE_QUESTIONS = [
  "What is the hand hygiene protocol?",
  "What are the admission criteria for ICU?",
  "How do we process SHA claims?",
  "What is the medication dispensing SOP?",
] as const;

const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  policy: "Policy",
  sop: "SOP",
  guideline: "Guideline",
  manual: "Manual",
  protocol: "Protocol",
  formulary: "Formulary",
  circular: "Circular",
  training: "Training",
  other: "Other",
};

/**
 * Determine the confidence badge variant based on the score.
 *
 * @param confidence - Score between 0 and 1
 * @returns StatusBadge variant string
 */
function getConfidenceVariant(confidence: number): "success" | "warning" | "error" {
  if (confidence > 0.7) return "success";
  if (confidence >= 0.4) return "warning";
  return "error";
}

/**
 * Format a confidence score as a human-readable label.
 *
 * @param confidence - Score between 0 and 1
 * @returns Formatted label string
 */
function getConfidenceLabel(confidence: number): string {
  if (confidence > 0.7) return "High";
  if (confidence >= 0.4) return "Medium";
  return "Low";
}

/**
 * Collapsible citation card showing a source chunk from a retrieved document.
 *
 * @param citation - The citation source data
 * @param t - Translation function
 * @returns Rendered citation card
 */
function CitationCard({
  citation,
  t,
}: {
  citation: CitationSource;
  t: ReturnType<typeof useTranslations>;
}) {
  const [expanded, setExpanded] = useState(false);
  const relevancePct = Math.round(citation.relevance_score * 100);

  return (
    <div className="rounded-lg border border-border bg-muted/30 dark:bg-muted/10">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-start gap-3 p-3 text-left"
        aria-expanded={expanded}
      >
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-foreground">
              {citation.document_title}
            </span>
            <StatusBadge variant="info" size="xs">
              {CATEGORY_LABELS[citation.category]}
            </StatusBadge>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {citation.section && (
              <span>
                {t("section")}: {citation.section}
              </span>
            )}
            {citation.page_number !== null && (
              <span>
                {t("page")} {citation.page_number}
              </span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-muted dark:bg-muted/50">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  relevancePct > 70
                    ? "bg-green-500 dark:bg-green-400"
                    : relevancePct >= 40
                      ? "bg-amber-500 dark:bg-amber-400"
                      : "bg-red-500 dark:bg-red-400"
                )}
                style={{ width: `${relevancePct}%` }}
              />
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">
              {relevancePct}%
            </span>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div className="border-t border-border px-3 py-3">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">
            {citation.chunk_text}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Rendered answer card for a completed knowledge base query.
 *
 * @param entry - The conversation entry containing query and response
 * @param t - Translation function
 * @returns Rendered answer card with citations
 */
function AnswerCard({
  entry,
  t,
}: {
  entry: ConversationEntry;
  t: ReturnType<typeof useTranslations>;
}) {
  const { response } = entry;

  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-muted/40 px-4 py-2 dark:bg-muted/20">
        <p className="text-sm font-medium text-foreground">{entry.query}</p>
      </div>

      <div className="rounded-xl bg-card p-4 shadow-sm ring-1 ring-border dark:bg-card">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {response.answer}
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3">
          <StatusBadge
            variant={getConfidenceVariant(response.confidence)}
            size="xs"
            dot
          >
            {t("confidence")}: {getConfidenceLabel(response.confidence)}
          </StatusBadge>
          <span className="text-xs text-muted-foreground">
            {response.model_used}
          </span>
          <span className="text-xs text-muted-foreground">
            {t("retrieval")}: {response.retrieval_time_ms}ms | {t("generation")}:{" "}
            {response.generation_time_ms}ms
          </span>
        </div>
      </div>

      {response.citations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("sources")} ({response.citations.length})
          </h4>
          {response.citations.map((citation, idx) => (
            <CitationCard
              key={`${citation.document_id}-${idx}`}
              citation={citation}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Chat-style interface for querying the institutional knowledge base.
 * Supports conversational history, language toggling (EN/SW), and citation display.
 *
 * @param props - Component props including optional filters and className
 * @returns Knowledge base chat component
 */
export function AskKnowledgeBase({
  documentIds,
  categories,
  department,
  className,
}: AskKnowledgeBaseProps) {
  const t = useTranslations("knowledge");
  const { mutate, data, isPending, isError, error, reset } = useKnowledgeQuery();

  const [inputValue, setInputValue] = useState("");
  const [language, setLanguage] = useState<"en" | "sw">("en");
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [conversation, isPending, scrollToBottom]);

  useEffect(() => {
    if (data && pendingQuery) {
      setConversation((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          query: pendingQuery,
          response: data,
        },
      ]);
      setPendingQuery(null);
      reset();
    }
  }, [data, pendingQuery, reset]);

  const submitQuery = useCallback(
    (queryText: string) => {
      const trimmed = queryText.trim();
      if (!trimmed || isPending) return;

      setPendingQuery(trimmed);
      setInputValue("");

      const request: KnowledgeQueryRequest = {
        query: trimmed,
        language,
        include_chunks: true,
      };
      if (documentIds && documentIds.length > 0) {
        request.document_ids = documentIds;
      }
      if (categories && categories.length > 0) {
        request.categories = categories;
      }
      if (department) {
        request.department = department;
      }

      mutate(request);
    },
    [isPending, language, documentIds, categories, department, mutate]
  );

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      submitQuery(inputValue);
    },
    [inputValue, submitQuery]
  );

  const handleExampleClick = useCallback(
    (question: string) => {
      submitQuery(question);
    },
    [submitQuery]
  );

  const handleRetry = useCallback(() => {
    if (pendingQuery) {
      const retryQuery = pendingQuery;
      reset();
      submitQuery(retryQuery);
    }
  }, [pendingQuery, reset, submitQuery]);

  const hasConversation = conversation.length > 0 || isPending || isError;

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-xl border border-border bg-background",
        className
      )}
    >
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
        {!hasConversation ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
              <BookOpen className="h-8 w-8 text-muted-foreground/50" />
            </div>
            <h3 className="text-lg font-semibold text-foreground">
              {t("askTitle")}
            </h3>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              {t("askDescription")}
            </p>
            <div className="mt-6 flex max-w-lg flex-wrap justify-center gap-2">
              {EXAMPLE_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => handleExampleClick(question)}
                  disabled={isPending}
                  className={cn(
                    "rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground",
                    "transition-colors hover:bg-accent hover:text-accent-foreground",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    "disabled:pointer-events-none disabled:opacity-50",
                    "dark:bg-card dark:hover:bg-accent"
                  )}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {conversation.map((entry) => (
              <AnswerCard key={entry.id} entry={entry} t={t} />
            ))}

            {isPending && pendingQuery && (
              <div className="space-y-3">
                <div className="rounded-lg bg-muted/40 px-4 py-2 dark:bg-muted/20">
                  <p className="text-sm font-medium text-foreground">
                    {pendingQuery}
                  </p>
                </div>
                <div className="flex items-center gap-3 rounded-xl bg-card p-4 shadow-sm ring-1 ring-border dark:bg-card">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {t("searching")}
                  </span>
                </div>
              </div>
            )}

            {isError && pendingQuery && (
              <div className="space-y-3">
                <div className="rounded-lg bg-muted/40 px-4 py-2 dark:bg-muted/20">
                  <p className="text-sm font-medium text-foreground">
                    {pendingQuery}
                  </p>
                </div>
                <div className="flex items-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 dark:bg-destructive/10">
                  <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-destructive">
                      {error instanceof Error
                        ? error.message
                        : t("queryError")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleRetry}
                    className={cn(
                      "shrink-0 rounded-md border border-destructive/30 px-3 py-1 text-sm font-medium text-destructive",
                      "transition-colors hover:bg-destructive/10",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    )}
                  >
                    {t("tryAgain")}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-border p-3">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <div className="flex shrink-0 gap-0.5 rounded-md border border-border bg-muted/50 p-0.5 dark:bg-muted/20">
            <button
              type="button"
              onClick={() => setLanguage("en")}
              className={cn(
                "rounded px-2 py-0.5 text-xs font-medium transition-colors",
                language === "en"
                  ? "bg-background text-foreground shadow-sm dark:bg-card"
                  : "text-muted-foreground hover:text-foreground"
              )}
              aria-label="Switch to English"
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage("sw")}
              className={cn(
                "rounded px-2 py-0.5 text-xs font-medium transition-colors",
                language === "sw"
                  ? "bg-background text-foreground shadow-sm dark:bg-card"
                  : "text-muted-foreground hover:text-foreground"
              )}
              aria-label="Switch to Swahili"
            >
              SW
            </button>
          </div>

          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={t("inputPlaceholder")}
            disabled={isPending}
            className={cn(
              "min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground",
              "placeholder:text-muted-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "dark:bg-background"
            )}
          />

          <button
            type="submit"
            disabled={!inputValue.trim() || isPending}
            aria-label={t("send")}
            className={cn(
              "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground",
              "transition-colors hover:bg-primary/90",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:pointer-events-none disabled:opacity-50"
            )}
          >
            <Search className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
