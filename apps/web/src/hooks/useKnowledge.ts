"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  KnowledgeDocument,
  KnowledgeDocumentList,
  DocumentChunk,
  DocumentUploadData,
  DocumentUpdateData,
  KnowledgeQueryRequest,
  KnowledgeQueryResponse,
  CitationSource,
  IngestStatusResponse,
  DocumentCategory,
  DocumentStatus,
} from "@aifya/shared";

// Same-origin proxy that swaps the httpOnly session cookie for the
// Bearer header the knowledge service expects (see app/api/knowledge).
const KNOWLEDGE_API = "/api/knowledge";

/**
 * Hook for listing knowledge documents with pagination and filters.
 *
 * @param page - Page number (1-based)
 * @param pageSize - Items per page
 * @param category - Optional category filter
 * @param department - Optional department filter
 * @param search - Optional search term
 * @param status - Optional status filter
 * @returns Query result with paginated document list
 */
export function useKnowledgeDocuments(
  page: number = 1,
  pageSize: number = 20,
  category?: DocumentCategory,
  department?: string,
  search?: string,
  status?: DocumentStatus
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (category) params["category"] = category;
  if (department) params["department"] = department;
  if (search) params["search"] = search;
  if (status) params["status"] = status;

  return useOfflineQuery<KnowledgeDocumentList>({
    queryKey: ["knowledge", "documents", page, pageSize, category, department, search, status],
    queryFn: async () => {
      const search = new URLSearchParams(params);
      const resp = await fetch(`${KNOWLEDGE_API}/documents?${search}`, {
        credentials: "include",
      });
      if (!resp.ok) throw new Error("Failed to fetch documents");
      return resp.json();
    },
  });
}

/**
 * Hook for fetching a single knowledge document.
 *
 * @param documentId - Document UUID
 * @returns Query result with document data
 */
export function useKnowledgeDocument(documentId: string) {
  return useOfflineQuery<KnowledgeDocument>({
    queryKey: ["knowledge", "documents", documentId],
    queryFn: async () => {
      const resp = await fetch(`${KNOWLEDGE_API}/documents/${documentId}`, {
        credentials: "include",
      });
      if (!resp.ok) throw new Error("Failed to fetch document");
      return resp.json();
    },
    enabled: !!documentId,
  });
}

/**
 * Hook for fetching document chunks.
 *
 * @param documentId - Document UUID
 * @returns Query result with chunks
 */
export function useDocumentChunks(documentId: string) {
  return useOfflineQuery<DocumentChunk[]>({
    queryKey: ["knowledge", "documents", documentId, "chunks"],
    queryFn: async () => {
      const resp = await fetch(
        `${KNOWLEDGE_API}/documents/${documentId}/chunks`,
        { credentials: "include" }
      );
      if (!resp.ok) throw new Error("Failed to fetch chunks");
      return resp.json();
    },
    enabled: !!documentId,
  });
}

/**
 * Hook for checking document ingestion status.
 *
 * @param documentId - Document UUID
 * @param enabled - Whether to poll
 * @returns Query result with ingestion status
 */
export function useIngestStatus(documentId: string, enabled: boolean = true) {
  return useOfflineQuery<IngestStatusResponse>({
    queryKey: ["knowledge", "documents", documentId, "ingest-status"],
    queryFn: async () => {
      const resp = await fetch(
        `${KNOWLEDGE_API}/documents/${documentId}/ingest-status`,
        { credentials: "include" }
      );
      if (!resp.ok) throw new Error("Failed to fetch ingest status");
      return resp.json();
    },
    enabled: enabled && !!documentId,
    refetchInterval: enabled ? 3000 : false,
  });
}

/**
 * Hook for uploading a document.
 *
 * @returns Mutation for uploading a document
 */
export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation<KnowledgeDocument, Error, DocumentUploadData>({
    mutationFn: async (data: DocumentUploadData) => {
      const formData = new FormData();
      formData.append("file", data.file);
      formData.append("title", data.title);
      formData.append("category", data.category);
      if (data.description) formData.append("description", data.description);
      if (data.department) formData.append("department", data.department);
      if (data.tags) formData.append("tags", data.tags);
      if (data.access_scope) formData.append("access_scope", data.access_scope);
      if (data.version_label) formData.append("version_label", data.version_label);

      const resp = await fetch(`${KNOWLEDGE_API}/documents/upload`, {
        method: "POST",
        credentials: "include",
        headers: { "X-Idempotency-Key": generateId() },
        body: formData,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }
      return resp.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
    },
  });
}

/**
 * Hook for updating document metadata.
 *
 * @returns Mutation for updating a document
 */
export function useUpdateDocument() {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    KnowledgeDocument,
    { documentId: string; updates: DocumentUpdateData }
  >(
    {
      mutationFn: async ({ documentId, updates }) => {
        const resp = await fetch(`${KNOWLEDGE_API}/documents/${documentId}`, {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Idempotency-Key": generateId(),
          },
          body: JSON.stringify(updates),
        });
        if (!resp.ok) throw new Error("Failed to update document");
        return resp.json();
      },
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({
          queryKey: ["knowledge", "documents", variables.documentId],
        });
        queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      },
    },
    {
      url: ({ documentId }) => `${KNOWLEDGE_API}/documents/${documentId}`,
      method: "PATCH",
      body: ({ updates }) => updates,
    },
  );
}

/**
 * Hook for deleting a document.
 *
 * @returns Mutation for deleting a document
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useOfflineMutation<void, string>(
    {
      mutationFn: async (documentId: string) => {
        const resp = await fetch(`${KNOWLEDGE_API}/documents/${documentId}`, {
          method: "DELETE",
          credentials: "include",
          headers: { "X-Idempotency-Key": generateId() },
        });
        if (!resp.ok) throw new Error("Failed to delete document");
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      },
    },
    {
      url: (documentId) => `${KNOWLEDGE_API}/documents/${documentId}`,
      method: "DELETE",
      body: () => null,
    },
  );
}

/**
 * Hook for querying the knowledge base (RAG).
 *
 * @returns Mutation for querying (uses mutation for on-demand execution)
 */
export function useKnowledgeQuery() {
  return useMutation<KnowledgeQueryResponse, Error, KnowledgeQueryRequest>({
    mutationFn: async (request: KnowledgeQueryRequest) => {
      const resp = await fetch(`${KNOWLEDGE_API}/query`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      if (!resp.ok) throw new Error("Failed to query knowledge base");
      return resp.json();
    },
  });
}

/**
 * Hook for fetching relevant context without generation.
 * Used by the contextual sidebar widget.
 *
 * @param query - Query text
 * @param enabled - Whether to execute
 * @returns Query result with citations
 */
export function useKnowledgeContext(query: string, enabled: boolean = false) {
  return useOfflineQuery<CitationSource[]>({
    queryKey: ["knowledge", "context", query],
    queryFn: async () => {
      const resp = await fetch(`${KNOWLEDGE_API}/query/context`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 3, include_chunks: true }),
      });
      if (!resp.ok) throw new Error("Failed to fetch context");
      return resp.json();
    },
    enabled: enabled && query.length >= 3,
  });
}
