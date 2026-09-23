"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  BookOpen,
  Upload,
  FileText,
  Search,
  File,
  CheckCircle2,
  Loader2,
  FolderOpen,
  Eye,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useKnowledgeDocuments } from "@/hooks/useKnowledge";
import type { DocumentCategory, KnowledgeDocument } from "@aifya/shared";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterChips } from "@/components/ui/TabGroup";

/** Number of documents per page. */
const PAGE_SIZE = 20;

/** Category filter options including the "all" sentinel. */
const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All" },
  { value: "policy", label: "Policy" },
  { value: "sop", label: "SOP" },
  { value: "guideline", label: "Guideline" },
  { value: "manual", label: "Manual" },
  { value: "protocol", label: "Protocol" },
  { value: "formulary", label: "Formulary" },
  { value: "training", label: "Training" },
  { value: "other", label: "Other" },
];

/**
 * Map document status to StatusBadge variant.
 *
 * @param status - Document processing status
 * @returns StatusBadge variant string
 */
function statusVariant(
  status: string
): "success" | "warning" | "error" | "slate" | "info" {
  switch (status) {
    case "ready":
      return "success";
    case "processing":
    case "uploading":
    case "chunking":
    case "embedding":
      return "warning";
    case "failed":
      return "error";
    case "archived":
      return "slate";
    default:
      return "info";
  }
}

/**
 * Format a file size in bytes to a human-readable string.
 *
 * @param bytes - File size in bytes
 * @returns Formatted string like "1.2 MB"
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/**
 * Format an ISO 8601 date string for display.
 *
 * @param iso - ISO 8601 date string
 * @returns Formatted date like "10 Apr 2026"
 */
function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Nairobi",
  });
}

/**
 * Capitalize the first letter of a string.
 *
 * @param str - Input string
 * @returns Capitalized string
 */
function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Knowledge Base document library page.
 * Lists all institutional documents with filtering, search, and pagination.
 *
 * @returns Knowledge base page component
 */
export default function KnowledgeBasePage() {
  const t = useTranslations("knowledge");
  const tc = useTranslations("common");

  const [page, setPage] = useState(1);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const activeCategory =
    categoryFilter === "all"
      ? undefined
      : (categoryFilter as DocumentCategory);

  const searchTerm = searchQuery.trim().length >= 2 ? searchQuery.trim() : undefined;

  const { data, isLoading } = useKnowledgeDocuments(
    page,
    PAGE_SIZE,
    activeCategory,
    undefined,
    searchTerm,
    undefined
  );

  const documents = useMemo(() => data?.items ?? [], [data?.items]);
  const totalCount = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const stats = useMemo(() => {
    const readyCount = documents.filter(
      (d: KnowledgeDocument) => d.status === "ready"
    ).length;
    const processingCount = documents.filter(
      (d: KnowledgeDocument) =>
        d.status === "processing" ||
        d.status === "uploading" ||
        d.status === "chunking" ||
        d.status === "embedding"
    ).length;
    const uniqueCategories = new Set(
      documents.map((d: KnowledgeDocument) => d.category)
    ).size;
    return { readyCount, processingCount, uniqueCategories };
  }, [documents]);

  const tableHeaders = [
    { label: t("columnTitle") },
    { label: t("columnDepartment") },
    { label: t("columnStatus") },
    { label: t("columnChunks"), className: "text-right" },
    { label: t("columnPages"), className: "text-right" },
    { label: t("columnUploadedBy") },
    { label: t("columnDate") },
    { label: tc("actions"), className: "text-right" },
  ];

  /**
   * Handle category filter change, resetting page to 1.
   *
   * @param value - Selected category filter value
   */
  function handleCategoryChange(value: string): void {
    setCategoryFilter(value);
    setPage(1);
  }

  /**
   * Handle search input change, resetting page to 1.
   *
   * @param e - Input change event
   */
  function handleSearchChange(
    e: React.ChangeEvent<HTMLInputElement>
  ): void {
    setSearchQuery(e.target.value);
    setPage(1);
  }

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6">
      {/* Header */}
      <PageHeader
        icon={BookOpen}
        title={t("title")}
        subtitle={t("subtitle")}
        badge={totalCount}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <Link
            href="/knowledge/upload"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          >
            <Upload className="h-4 w-4" />
            {t("uploadDocument")}
          </Link>
        }
      />

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard
              icon={FileText}
              label={t("statTotalDocuments")}
              value={totalCount}
              color="blue"
            />
            <StatCard
              icon={CheckCircle2}
              label={t("statReady")}
              value={stats.readyCount}
              color="green"
            />
            <StatCard
              icon={Loader2}
              label={t("statProcessing")}
              value={stats.processingCount}
              color="amber"
            />
            <StatCard
              icon={FolderOpen}
              label={t("statCategories")}
              value={stats.uniqueCategories}
              color="purple"
            />
          </>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <FilterChips
          options={CATEGORY_OPTIONS}
          selected={categoryFilter}
          onSelect={handleCategoryChange}
        />
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder={t("searchPlaceholder")}
            className="h-9 w-full rounded-lg border border-border bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      {/* Documents Table */}
      {!isLoading && documents.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
          action={
            <Link
              href="/knowledge/upload"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            >
              <Upload className="h-4 w-4" />
              {t("uploadDocument")}
            </Link>
          }
        />
      ) : (
        <DataTable
          headers={tableHeaders}
          isLoading={isLoading}
          isEmpty={documents.length === 0}
          emptyMessage={t("emptyTitle")}
          page={page}
          totalPages={totalPages}
          onPageChange={setPage}
          totalCount={totalCount}
          columnCount={8}
        >
          {documents.map((doc: KnowledgeDocument) => (
            <tr
              key={doc.id}
              className="transition-colors hover:bg-muted/30"
            >
              {/* Title + file type + category */}
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                    <File className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <Link
                      href={`/knowledge/${doc.id}`}
                      className="text-sm font-medium text-foreground transition-colors hover:text-primary"
                    >
                      {doc.title}
                    </Link>
                    <div className="mt-0.5 flex items-center gap-2">
                      <StatusBadge variant="info" size="xs">
                        {doc.category.toUpperCase()}
                      </StatusBadge>
                      <span className="text-xs text-muted-foreground">
                        {formatFileSize(doc.file_size_bytes)}
                      </span>
                    </div>
                  </div>
                </div>
              </td>

              {/* Department */}
              <td className="px-4 py-3 text-sm text-muted-foreground">
                {doc.department ?? "\u2014"}
              </td>

              {/* Status */}
              <td className="px-4 py-3">
                <StatusBadge variant={statusVariant(doc.status)} dot>
                  {capitalize(doc.status)}
                </StatusBadge>
              </td>

              {/* Chunks */}
              <td className="px-4 py-3 text-right tabular-nums text-sm text-foreground">
                {doc.chunk_count}
              </td>

              {/* Pages */}
              <td className="px-4 py-3 text-right tabular-nums text-sm text-foreground">
                {doc.page_count}
              </td>

              {/* Uploaded by */}
              <td className="px-4 py-3 text-sm text-muted-foreground">
                {doc.uploaded_by_name ?? "\u2014"}
              </td>

              {/* Date */}
              <td className="px-4 py-3 text-sm text-muted-foreground">
                {formatDate(doc.created_at)}
              </td>

              {/* Actions */}
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/knowledge/${doc.id}`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  <Eye className="h-3.5 w-3.5" />
                  {tc("view")}
                </Link>
              </td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
