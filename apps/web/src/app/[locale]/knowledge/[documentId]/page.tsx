"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  FileText,
  ArrowLeft,
  Trash2,
  Layers,
  BookOpen,
  AlertCircle,
  Hash,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StatCard } from "@/components/ui/StatCard";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { TabGroup } from "@/components/ui/TabGroup";
import {
  useKnowledgeDocument,
  useDocumentChunks,
  useIngestStatus,
  useDeleteDocument,
} from "@/hooks/useKnowledge";
import { AskKnowledgeBase } from "@/components/knowledge/AskKnowledgeBase";
import type { DocumentCategory, DocumentStatus } from "@aifya/shared";

/** Map document status to StatusBadge variant. */
const STATUS_VARIANT: Record<DocumentStatus, "success" | "warning" | "error" | "info" | "default"> = {
  uploading: "info",
  processing: "warning",
  chunking: "warning",
  embedding: "warning",
  ready: "success",
  failed: "error",
  archived: "default",
};

/** Map document category to StatusBadge variant. */
const CATEGORY_VARIANT: Record<DocumentCategory, "purple" | "blue" | "teal" | "cyan" | "indigo" | "orange" | "pink" | "emerald" | "default"> = {
  policy: "purple",
  sop: "blue",
  guideline: "teal",
  manual: "cyan",
  protocol: "indigo",
  formulary: "orange",
  circular: "pink",
  training: "emerald",
  other: "default",
};

/**
 * Format file size from bytes to human-readable string.
 *
 * @param bytes - File size in bytes
 * @returns Formatted size string (e.g. "1.5 MB")
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Knowledge document detail page.
 * Displays document metadata, processing status, chunks, and an embedded
 * RAG "Ask" interface scoped to this document.
 *
 * @param params - Route params containing documentId
 * @returns Document detail page
 */
export default function KnowledgeDocumentPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = use(params);
  const t = useTranslations("knowledge");
  const tc = useTranslations("common");
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<string>("chunks");
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set());

  const { data: document, isLoading } = useKnowledgeDocument(documentId);
  const { data: chunks, isLoading: chunksLoading } = useDocumentChunks(documentId);
  const deleteDocument = useDeleteDocument();

  const isProcessing =
    document?.status === "processing" ||
    document?.status === "embedding" ||
    document?.status === "chunking";

  const { data: ingestStatus } = useIngestStatus(documentId, isProcessing);

  /**
   * Toggle chunk text expansion.
   *
   * @param index - Chunk index to toggle
   */
  function toggleChunkExpansion(index: number): void {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  /**
   * Handle document deletion with confirmation.
   */
  function handleDelete(): void {
    const confirmed = window.confirm(t("deleteConfirmation"));
    if (!confirmed) return;

    deleteDocument.mutate(documentId, {
      onSuccess: () => {
        router.push("/knowledge");
      },
    });
  }

  // --- Loading state ---
  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl p-6 lg:p-8">
        <PageSkeleton />
      </div>
    );
  }

  // --- Not found ---
  if (!document) {
    return (
      <div className="mx-auto max-w-5xl p-6 lg:p-8">
        <EmptyState
          icon={FileText}
          title={t("documentNotFound")}
          description={t("documentNotFoundDescription")}
          action={
            <Link
              href="/knowledge"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("backToKnowledge")}
            </Link>
          }
        />
      </div>
    );
  }

  // --- Role check for admin delete (simple JWT role check) ---
  let userRole: string | null = null;
  try {
    const token = localStorage.getItem("access_token");
    if (token) {
      const payloadSegment = token.split(".")[1];
      if (payloadSegment) {
        const payload = JSON.parse(atob(payloadSegment));
        userRole = payload.role ?? payload.realm_access?.roles?.[0] ?? null;
      }
    }
  } catch {
    // Token parse failure is non-critical
  }
  const isAdmin = userRole === "admin" || userRole === "facility_admin";

  const tabs = [
    { key: "chunks", label: t("chunks"), count: document.chunk_count },
    { key: "ask", label: t("askDocument") },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-8">
      {/* Page header */}
      <PageHeader
        icon={FileText}
        title={document.title}
        breadcrumbs={[
          { label: t("knowledgeBase"), href: "/knowledge" },
          { label: document.title },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/knowledge"
              className="inline-flex items-center gap-2 rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              <ArrowLeft className="h-4 w-4" />
              {tc("back")}
            </Link>
            {isAdmin && (
              <button
                onClick={handleDelete}
                disabled={deleteDocument.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                {deleteDocument.isPending ? tc("deleting") : tc("delete")}
              </button>
            )}
          </div>
        }
      />

      {/* Processing indicator */}
      {isProcessing && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-5 dark:border-amber-800 dark:bg-amber-950/30">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                {t("processingDocument")}
              </p>
              {ingestStatus && (
                <p className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
                  {t(`ingestStatus_${ingestStatus.status}`)} &mdash;{" "}
                  {ingestStatus.chunks_processed} / {ingestStatus.total_chunks}{" "}
                  {t("chunksProcessed")}
                </p>
              )}
            </div>
            {ingestStatus && (
              <span className="text-sm font-semibold text-amber-700 dark:text-amber-300">
                {ingestStatus.progress_pct}%
              </span>
            )}
          </div>
          {ingestStatus && (
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-amber-200/50 dark:bg-amber-800/50">
              <div
                className="skeleton-shimmer h-full rounded-full bg-amber-500 transition-all duration-500"
                style={{ width: `${ingestStatus.progress_pct}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Document info grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Document Details */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-base font-semibold text-foreground">
            {t("documentDetails")}
          </h2>
          <div className="space-y-3.5">
            {/* Category + Status */}
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge variant={CATEGORY_VARIANT[document.category]}>
                {t(`category_${document.category}`)}
              </StatusBadge>
              <StatusBadge variant={STATUS_VARIANT[document.status]} dot>
                {t(`status_${document.status}`)}
              </StatusBadge>
            </div>

            {/* Description */}
            {document.description && (
              <InfoRow label={t("description")} value={document.description} />
            )}

            {/* Department */}
            {document.department && (
              <InfoRow label={t("department")} value={document.department} />
            )}

            {/* Tags */}
            {document.tags.length > 0 && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">
                  {t("tags")}
                </span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {document.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Access scope */}
            <InfoRow label={t("accessScope")} value={t(`scope_${document.access_scope}`)} />

            {/* Version */}
            {document.version_label && (
              <InfoRow label={t("version")} value={document.version_label} />
            )}

            {/* Dates */}
            <div className="grid grid-cols-2 gap-3">
              {document.effective_date && (
                <InfoRow
                  label={t("effectiveDate")}
                  value={new Date(document.effective_date).toLocaleDateString()}
                />
              )}
              {document.expiry_date && (
                <InfoRow
                  label={t("expiryDate")}
                  value={new Date(document.expiry_date).toLocaleDateString()}
                />
              )}
            </div>

            {/* File info */}
            <div className="border-t border-border pt-3">
              <span className="text-xs font-medium text-muted-foreground">
                {t("fileInfo")}
              </span>
              <div className="mt-1.5 grid grid-cols-2 gap-2 text-sm">
                <InfoRow label={t("fileName")} value={document.file_name} />
                <InfoRow
                  label={t("fileSize")}
                  value={formatFileSize(document.file_size_bytes)}
                />
                <InfoRow label={t("mimeType")} value={document.mime_type} />
              </div>
            </div>

            {/* Upload info */}
            <div className="border-t border-border pt-3">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {document.uploaded_by_name && (
                  <InfoRow
                    label={t("uploadedBy")}
                    value={document.uploaded_by_name}
                  />
                )}
                <InfoRow
                  label={t("uploadedDate")}
                  value={new Date(document.created_at).toLocaleDateString()}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Processing Stats */}
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-foreground">
            {t("processingStats")}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              icon={Layers}
              label={t("chunks")}
              value={document.chunk_count}
              color="blue"
            />
            <StatCard
              icon={BookOpen}
              label={t("pages")}
              value={document.page_count}
              color="purple"
            />
            <StatCard
              icon={FileText}
              label={tc("status")}
              value={t(`status_${document.status}`)}
              color={document.status === "failed" ? "red" : "green"}
            />
          </div>

          {/* Error message */}
          {document.status === "failed" && ingestStatus?.error_message && (
            <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/30">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600 dark:text-red-400" />
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  {t("processingFailed")}
                </p>
                <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                  {ingestStatus.error_message}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tabs: Chunks / Ask */}
      <div className="space-y-4">
        <TabGroup
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          variant="underline"
        />

        {/* Chunks tab */}
        {activeTab === "chunks" && (
          <div className="space-y-3">
            {chunksLoading && (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="skeleton-shimmer h-24 rounded-xl"
                  />
                ))}
              </div>
            )}

            {!chunksLoading && (!chunks || chunks.length === 0) && (
              <EmptyState
                icon={Layers}
                title={t("noChunks")}
                description={t("noChunksDescription")}
              />
            )}

            {!chunksLoading &&
              chunks &&
              chunks.length > 0 &&
              chunks.map((chunk) => {
                const isExpanded = expandedChunks.has(chunk.chunk_index);
                const needsTruncation = chunk.text.length > 300;
                const displayText =
                  needsTruncation && !isExpanded
                    ? chunk.text.slice(0, 300) + "..."
                    : chunk.text;

                return (
                  <div
                    key={chunk.chunk_index}
                    className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all"
                  >
                    {/* Chunk header */}
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                        <Hash className="h-3 w-3" />
                        {chunk.chunk_index + 1}
                      </span>
                      {chunk.page_number !== null && (
                        <StatusBadge variant="info" size="xs">
                          {t("page")} {chunk.page_number}
                        </StatusBadge>
                      )}
                      {chunk.section_title && (
                        <span className="text-xs font-medium text-foreground">
                          {chunk.section_title}
                        </span>
                      )}
                      <span className="ml-auto text-xs text-muted-foreground">
                        {chunk.token_count} {t("tokens")}
                      </span>
                    </div>

                    {/* Chunk text */}
                    <p className="whitespace-pre-wrap text-sm text-foreground/80">
                      {displayText}
                    </p>

                    {/* Expand/collapse toggle */}
                    {needsTruncation && (
                      <button
                        onClick={() => toggleChunkExpansion(chunk.chunk_index)}
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="h-3 w-3" />
                            {t("showLess")}
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-3 w-3" />
                            {t("showMore")}
                          </>
                        )}
                      </button>
                    )}
                  </div>
                );
              })}
          </div>
        )}

        {/* Ask tab */}
        {activeTab === "ask" && (
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <AskKnowledgeBase documentIds={[documentId]} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Simple label/value pair for document info display.
 *
 * @param label - Field label
 * @param value - Field value
 * @returns Info row component
 */
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <p className="text-sm text-foreground">{value}</p>
    </div>
  );
}
