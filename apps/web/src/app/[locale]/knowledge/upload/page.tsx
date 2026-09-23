"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Upload,
  FileText,
  X,
  Loader2,
  Lightbulb,
  FileUp,
  AlertCircle,
} from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { useUploadDocument } from "@/hooks/useKnowledge";
import type { DocumentCategory, AccessScope } from "@aifya/shared";

/** Accepted MIME types mapped from file extensions. */
const ACCEPTED_TYPES: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/msword": "DOC",
  "text/plain": "TXT",
  "text/markdown": "MD",
};

/** File extensions accepted by the file input. */
const ACCEPTED_EXTENSIONS = ".pdf,.docx,.doc,.txt,.md";

/** Category options for the category select. */
const CATEGORY_OPTIONS: Array<{ value: DocumentCategory; labelKey: string }> = [
  { value: "policy", labelKey: "categoryPolicy" },
  { value: "sop", labelKey: "categorySop" },
  { value: "guideline", labelKey: "categoryGuideline" },
  { value: "manual", labelKey: "categoryManual" },
  { value: "protocol", labelKey: "categoryProtocol" },
  { value: "formulary", labelKey: "categoryFormulary" },
  { value: "circular", labelKey: "categoryCircular" },
  { value: "training", labelKey: "categoryTraining" },
  { value: "other", labelKey: "categoryOther" },
];

/** Access scope options. */
const ACCESS_SCOPE_OPTIONS: Array<{ value: AccessScope; labelKey: string }> = [
  { value: "facility", labelKey: "scopeFacility" },
  { value: "department", labelKey: "scopeDepartment" },
  { value: "role", labelKey: "scopeRole" },
];

/**
 * Formats a file size in bytes to a human-readable string.
 *
 * @param bytes - File size in bytes
 * @returns Formatted string (e.g. "2.5 MB")
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Returns a display label for a MIME type.
 *
 * @param mimeType - The MIME type string
 * @returns Human-readable type label
 */
function getTypeLabel(mimeType: string): string {
  return ACCEPTED_TYPES[mimeType] ?? "FILE";
}

/**
 * Knowledge document upload page.
 * Provides a drag-and-drop upload zone plus metadata form for uploading
 * institutional knowledge documents to the RAG-powered knowledge base.
 *
 * @returns The upload page component
 */
export default function KnowledgeUploadPage() {
  const t = useTranslations("knowledge");
  const tc = useTranslations("common");
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadDocument();

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<DocumentCategory | "">("");
  const [description, setDescription] = useState("");
  const [department, setDepartment] = useState("");
  const [tags, setTags] = useState("");
  const [accessScope, setAccessScope] = useState<AccessScope>("facility");
  const [versionLabel, setVersionLabel] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  /**
   * Validates and sets the selected file.
   *
   * @param selectedFile - The file to validate
   */
  const handleFileSelect = useCallback(
    (selectedFile: File) => {
      setFileError(null);

      if (!Object.keys(ACCEPTED_TYPES).includes(selectedFile.type)) {
        setFileError(t("uploadErrorInvalidType"));
        return;
      }

      setFile(selectedFile);

      if (!title) {
        const nameWithoutExt = selectedFile.name.replace(/\.[^.]+$/, "");
        setTitle(nameWithoutExt);
      }
    },
    [t, title]
  );

  /**
   * Handles the drop event on the drag-and-drop zone.
   *
   * @param e - The drag event
   */
  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect]
  );

  /**
   * Handles dragover to allow dropping.
   *
   * @param e - The drag event
   */
  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  /**
   * Handles dragenter to show visual feedback.
   *
   * @param e - The drag event
   */
  const handleDragEnter = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  /**
   * Handles dragleave to remove visual feedback.
   *
   * @param e - The drag event
   */
  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  /**
   * Handles the file input change event.
   *
   * @param e - The change event
   */
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFileSelect(selectedFile);
      }
    },
    [handleFileSelect]
  );

  /** Removes the currently selected file. */
  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setFileError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  /**
   * Submits the upload form.
   *
   * @param e - The form submit event
   */
  const handleSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();

      if (!file || !title || !category) return;

      uploadMutation.mutate(
        {
          file,
          title,
          category: category as DocumentCategory,
          description: description || undefined,
          department: department || undefined,
          tags: tags || undefined,
          access_scope: accessScope,
          version_label: versionLabel || undefined,
        },
        {
          onSuccess: () => {
            router.push("/knowledge");
          },
        }
      );
    },
    [
      file,
      title,
      category,
      description,
      department,
      tags,
      accessScope,
      versionLabel,
      uploadMutation,
      router,
    ]
  );

  const isFormValid = file !== null && title.trim() !== "" && category !== "";

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6">
      <PageHeader
        icon={Upload}
        title={t("uploadTitle")}
        breadcrumbs={[
          { label: t("breadcrumbKnowledge"), href: "/knowledge" },
          { label: t("breadcrumbUpload") },
        ]}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column: Upload form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit}>
            <div className="space-y-6 rounded-xl bg-card p-6 shadow-[var(--shadow-card)]">
              {/* Drag and drop zone */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">
                  {t("uploadFileLabel")} <span className="text-destructive">*</span>
                </label>

                {!file ? (
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onClick={() => fileInputRef.current?.click()}
                    className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
                      isDragOver
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary hover:bg-muted/50"
                    }`}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        fileInputRef.current?.click();
                      }
                    }}
                  >
                    <FileUp className="mb-3 h-10 w-10 text-muted-foreground" />
                    <p className="mb-1 text-sm font-medium text-foreground">
                      {t("uploadDropzone")}
                    </p>
                    <p className="mb-3 text-xs text-muted-foreground">
                      {t("uploadOrBrowse")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("uploadAccepted")}: PDF, DOCX, DOC, TXT, MD
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("uploadMaxSize")}
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center justify-between rounded-lg border border-border bg-muted/50 p-4">
                    <div className="flex items-center gap-3">
                      <FileText className="h-8 w-8 text-primary" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {file.name}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{formatFileSize(file.size)}</span>
                          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
                            {getTypeLabel(file.type)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleRemoveFile}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      aria-label={tc("remove")}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}

                {fileError && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-destructive">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span>{fileError}</span>
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS}
                  onChange={handleInputChange}
                  className="hidden"
                  aria-hidden="true"
                />
              </div>

              {/* Title */}
              <div>
                <label
                  htmlFor="upload-title"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadTitleLabel")} <span className="text-destructive">*</span>
                </label>
                <input
                  id="upload-title"
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={t("uploadTitlePlaceholder")}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Category */}
              <div>
                <label
                  htmlFor="upload-category"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadCategoryLabel")} <span className="text-destructive">*</span>
                </label>
                <select
                  id="upload-category"
                  required
                  value={category}
                  onChange={(e) => setCategory(e.target.value as DocumentCategory)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="" disabled>
                    {t("uploadCategoryPlaceholder")}
                  </option>
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label
                  htmlFor="upload-description"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadDescriptionLabel")}
                </label>
                <textarea
                  id="upload-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("uploadDescriptionPlaceholder")}
                  rows={3}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Department */}
              <div>
                <label
                  htmlFor="upload-department"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadDepartmentLabel")}
                </label>
                <input
                  id="upload-department"
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder={t("uploadDepartmentPlaceholder")}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Tags */}
              <div>
                <label
                  htmlFor="upload-tags"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadTagsLabel")}
                </label>
                <input
                  id="upload-tags"
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder={t("uploadTagsPlaceholder")}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("uploadTagsHint")}
                </p>
              </div>

              {/* Access Scope */}
              <div>
                <label
                  htmlFor="upload-access-scope"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadAccessScopeLabel")}
                </label>
                <select
                  id="upload-access-scope"
                  value={accessScope}
                  onChange={(e) => setAccessScope(e.target.value as AccessScope)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {ACCESS_SCOPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {t(opt.labelKey)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Version label */}
              <div>
                <label
                  htmlFor="upload-version"
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  {t("uploadVersionLabel")}
                </label>
                <input
                  id="upload-version"
                  type="text"
                  value={versionLabel}
                  onChange={(e) => setVersionLabel(e.target.value)}
                  placeholder={t("uploadVersionPlaceholder")}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {/* Error message */}
              {uploadMutation.isError && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>
                    {uploadMutation.error instanceof Error
                      ? uploadMutation.error.message
                      : t("uploadErrorGeneric")}
                  </span>
                </div>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={!isFormValid || uploadMutation.isPending}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                {uploadMutation.isPending
                  ? t("uploadSubmitting")
                  : t("uploadSubmit")}
              </button>
            </div>
          </form>
        </div>

        {/* Right column: Tips card */}
        <div className="lg:col-span-1">
          <div className="rounded-xl bg-card p-6 shadow-[var(--shadow-card)]">
            <div className="mb-4 flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-primary" />
              <h2 className="text-base font-semibold text-foreground">
                {t("uploadGuidelinesTitle")}
              </h2>
            </div>
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipFormats")}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipMaxSize")}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipAutoProcess")}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipProcessTime")}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipTags")}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{t("uploadTipDepartment")}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
