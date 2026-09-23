"""
Pydantic schemas for the Knowledge RAG service.
Request/response models for documents and queries.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentCategory(str, Enum):
    """Classification of institutional documents."""

    POLICY = "policy"
    SOP = "sop"
    GUIDELINE = "guideline"
    MANUAL = "manual"
    PROTOCOL = "protocol"
    FORMULARY = "formulary"
    CIRCULAR = "circular"
    TRAINING = "training"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Processing lifecycle of a document."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class AccessScope(str, Enum):
    """Who can query this document."""

    FACILITY = "facility"
    DEPARTMENT = "department"
    ROLE = "role"


class IngestStatus(str, Enum):
    """Celery task status for document ingestion."""

    PENDING = "pending"
    STARTED = "started"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentUploadRequest(BaseModel):
    """
    Metadata sent alongside the file upload.

    @param title: Human-readable document title
    @param category: Document classification
    @param description: Optional summary of the document
    @param department: Optional department scope (e.g. 'pharmacy', 'nursing')
    @param tags: Free-form tags for search filtering
    @param access_scope: Who can access this document
    @param effective_date: When the document takes effect
    @param expiry_date: When the document expires (for policies with review cycles)
    @param version_label: Human-readable version (e.g. 'v2.3', 'Rev A')
    """

    title: str = Field(
        ..., min_length=3, max_length=500, examples=["Infection Control SOP"]
    )
    category: DocumentCategory = Field(
        ..., examples=[DocumentCategory.SOP]
    )
    description: str | None = Field(
        None,
        max_length=2000,
        examples=["Standard operating procedure for infection prevention and control"],
    )
    department: str | None = Field(
        None, max_length=100, examples=["infection_control"]
    )
    tags: list[str] = Field(
        default_factory=list, max_length=20, examples=[["infection", "hygiene", "ppe"]]
    )
    access_scope: AccessScope = Field(
        default=AccessScope.FACILITY, examples=[AccessScope.FACILITY]
    )
    effective_date: datetime | None = Field(None)
    expiry_date: datetime | None = Field(None)
    version_label: str | None = Field(
        None, max_length=50, examples=["v2.3"]
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, v: list[str]) -> list[str]:
        """Lowercase and deduplicate tags."""
        if isinstance(v, list):
            return list({tag.strip().lower() for tag in v if tag.strip()})
        return v

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """
    Full document metadata returned by the API.

    @param id: Document UUID
    @param facility_id: Owning facility
    @param title: Document title
    @param category: Document classification
    @param status: Processing status
    @param file_name: Original uploaded filename
    @param file_size_bytes: File size in bytes
    @param mime_type: MIME type of the original file
    @param chunk_count: Number of text chunks extracted
    @param page_count: Number of pages (for PDF/DOCX)
    """

    id: uuid.UUID
    facility_id: uuid.UUID
    title: str
    category: DocumentCategory
    status: DocumentStatus
    description: str | None = None
    department: str | None = None
    tags: list[str] = Field(default_factory=list)
    access_scope: AccessScope
    file_name: str
    file_size_bytes: int
    mime_type: str
    chunk_count: int = 0
    page_count: int = 0
    version_label: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    uploaded_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """
    Paginated list of documents.

    @param items: List of documents
    @param total: Total number matching the filter
    @param page: Current page (1-based)
    @param page_size: Items per page
    """

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdateRequest(BaseModel):
    """
    Partial update for document metadata.
    Only provided fields are updated.
    """

    title: str | None = Field(None, min_length=3, max_length=500)
    category: DocumentCategory | None = None
    description: str | None = Field(None, max_length=2000)
    department: str | None = Field(None, max_length=100)
    tags: list[str] | None = None
    access_scope: AccessScope | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    version_label: str | None = Field(None, max_length=50)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Chunk schemas
# ---------------------------------------------------------------------------


class ChunkResponse(BaseModel):
    """
    A single text chunk from a document.

    @param chunk_index: Position in the document (0-based)
    @param text: Chunk text content
    @param page_number: Source page number (if applicable)
    @param section_title: Detected section heading
    @param token_count: Approximate token count
    """

    chunk_index: int
    text: str
    page_number: int | None = None
    section_title: str | None = None
    token_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Query schemas
# ---------------------------------------------------------------------------


class KnowledgeQueryRequest(BaseModel):
    """
    RAG query against the institutional knowledge base.

    @param query: Natural language question
    @param categories: Optional filter by document categories
    @param department: Optional filter by department
    @param document_ids: Optional filter to specific documents
    @param top_k: Number of chunks to retrieve
    @param include_chunks: Whether to return the raw source chunks
    @param language: Response language preference
    """

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        examples=["What is the hand hygiene protocol for ICU staff?"],
    )
    categories: list[DocumentCategory] | None = None
    department: str | None = None
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=4, ge=1, le=20)
    include_chunks: bool = Field(default=True)
    language: str = Field(default="en", pattern="^(en|sw)$")

    model_config = ConfigDict(from_attributes=True)


class CitationSource(BaseModel):
    """
    A citation from a retrieved source chunk.

    @param document_id: Source document UUID
    @param document_title: Human-readable title
    @param category: Document category
    @param section: Section heading (if detected)
    @param page_number: Page number in the original document
    @param chunk_text: The retrieved text passage
    @param relevance_score: Similarity score (0-1)
    """

    document_id: uuid.UUID
    document_title: str
    category: DocumentCategory
    section: str | None = None
    page_number: int | None = None
    chunk_text: str
    relevance_score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)


class KnowledgeQueryResponse(BaseModel):
    """
    RAG-generated answer with citations.

    @param answer: Generated answer text
    @param citations: Source chunks that informed the answer
    @param confidence: Overall answer confidence (0-1)
    @param query: Original query (echoed back)
    @param model_used: LLM model used for generation
    @param retrieval_time_ms: Time spent on vector search
    @param generation_time_ms: Time spent on LLM generation
    """

    answer: str
    citations: list[CitationSource]
    confidence: float = Field(ge=0.0, le=1.0)
    query: str
    model_used: str
    retrieval_time_ms: float
    generation_time_ms: float

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ingest status schema
# ---------------------------------------------------------------------------


class IngestStatusResponse(BaseModel):
    """
    Status of a document ingestion task.

    @param document_id: Document being ingested
    @param task_id: Celery task ID
    @param status: Current processing stage
    @param progress_pct: Estimated progress percentage
    @param error_message: Error details if failed
    @param chunks_processed: Number of chunks embedded so far
    @param total_chunks: Total chunks to embed
    """

    document_id: uuid.UUID
    task_id: str
    status: IngestStatus
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    error_message: str | None = None
    chunks_processed: int = 0
    total_chunks: int = 0

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Health schema
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """
    Service health status.

    @param status: Overall status
    @param service: Service name
    @param components: Individual component statuses
    """

    status: str = Field(..., examples=["ok"])
    service: str = Field(default="aifya-knowledge-rag")
    components: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
