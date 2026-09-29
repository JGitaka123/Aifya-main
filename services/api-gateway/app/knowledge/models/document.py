"""
SQLAlchemy models for institutional knowledge documents.
Uses the same AuditMixin pattern as api-gateway.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for knowledge service models."""

    pass


class KnowledgeDocument(Base):
    """
    Institutional document metadata.
    Stores metadata about uploaded documents — actual files live in MinIO,
    vector embeddings live in Qdrant. Multi-tenant via facility_id.

    @param id: Primary key UUID
    @param facility_id: Owning facility (multi-tenant isolation)
    @param title: Human-readable document title
    @param category: Document classification (policy, sop, guideline, etc.)
    @param status: Processing lifecycle status
    @param file_name: Original uploaded filename
    @param minio_object_key: Object key in MinIO bucket
    @param chunk_count: Number of text chunks extracted
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_kdocs_facility_category", "facility_id", "category"),
        Index("ix_kdocs_facility_status", "facility_id", "status"),
        Index("ix_kdocs_facility_department", "facility_id", "department"),
        Index(
            "ix_kdocs_facility_created",
            "facility_id",
            "created_at",
        ),
    )

    # --- Primary key ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Multi-tenant isolation ---
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )

    # --- Document metadata ---
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="uploading"
    )
    description: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    access_scope: Mapped[str] = mapped_column(
        String(30), nullable=False, default="facility"
    )

    # --- File info ---
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(1000), nullable=False)

    # --- Processing results ---
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(50))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Ingest task tracking ---
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    processing_metadata: Mapped[dict | None] = mapped_column(JSONB)

    # --- Audit trail ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    uploaded_by_name: Mapped[str | None] = mapped_column(String(200))
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    """
    Text chunk extracted from a document.
    Stored in PostgreSQL for metadata/search; vectors stored in Qdrant.

    @param id: Primary key UUID
    @param document_id: Parent document FK
    @param chunk_index: Position within the document (0-based)
    @param text: Chunk text content
    @param page_number: Page number in source document
    @param section_title: Detected section heading
    @param token_count: Approximate token count
    @param qdrant_point_id: Corresponding Qdrant point ID
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_kchunks_document", "document_id"),
        Index("ix_kchunks_facility", "facility_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Link to Qdrant
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
