/** Document categories for institutional knowledge. */
export type DocumentCategory =
  | "policy"
  | "sop"
  | "guideline"
  | "manual"
  | "protocol"
  | "formulary"
  | "circular"
  | "training"
  | "other";

/** Processing lifecycle of a document. */
export type DocumentStatus =
  | "uploading"
  | "processing"
  | "chunking"
  | "embedding"
  | "ready"
  | "failed"
  | "archived";

/** Who can query this document. */
export type AccessScope = "facility" | "department" | "role";

/** Celery task status for document ingestion. */
export type IngestStatus =
  | "pending"
  | "started"
  | "parsing"
  | "chunking"
  | "embedding"
  | "completed"
  | "failed";

/** Institutional knowledge document. */
export interface KnowledgeDocument {
  id: string;
  facility_id: string;
  title: string;
  category: DocumentCategory;
  status: DocumentStatus;
  description: string | null;
  department: string | null;
  tags: string[];
  access_scope: AccessScope;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  chunk_count: number;
  page_count: number;
  version_label: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  uploaded_by_name: string | null;
}

/** Paginated document list. */
export interface KnowledgeDocumentList {
  items: KnowledgeDocument[];
  total: number;
  page: number;
  page_size: number;
}

/** A text chunk from a document. */
export interface DocumentChunk {
  chunk_index: number;
  text: string;
  page_number: number | null;
  section_title: string | null;
  token_count: number;
}

/** Document upload form data. */
export interface DocumentUploadData {
  file: File;
  title: string;
  category: DocumentCategory;
  description?: string;
  department?: string;
  tags?: string;
  access_scope?: AccessScope;
  version_label?: string;
}

/** Document metadata update. */
export interface DocumentUpdateData {
  title?: string;
  category?: DocumentCategory;
  description?: string;
  department?: string;
  tags?: string[];
  access_scope?: AccessScope;
  version_label?: string;
}

/** RAG query request. */
export interface KnowledgeQueryRequest {
  query: string;
  categories?: DocumentCategory[];
  department?: string;
  document_ids?: string[];
  top_k?: number;
  include_chunks?: boolean;
  language?: "en" | "sw";
}

/** Citation from a retrieved source chunk. */
export interface CitationSource {
  document_id: string;
  document_title: string;
  category: DocumentCategory;
  section: string | null;
  page_number: number | null;
  chunk_text: string;
  relevance_score: number;
}

/** RAG query response with generated answer. */
export interface KnowledgeQueryResponse {
  answer: string;
  citations: CitationSource[];
  confidence: number;
  query: string;
  model_used: string;
  retrieval_time_ms: number;
  generation_time_ms: number;
}

/** Document ingestion status. */
export interface IngestStatusResponse {
  document_id: string;
  task_id: string;
  status: IngestStatus;
  progress_pct: number;
  error_message: string | null;
  chunks_processed: number;
  total_chunks: number;
}
