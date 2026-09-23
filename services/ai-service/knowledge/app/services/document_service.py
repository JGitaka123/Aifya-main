"""
Document service — orchestrates upload, storage, and metadata management.
File storage (MinIO or local disk) and PostgreSQL metadata operations.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.config import get_settings
from app.models.document import DocumentChunk, KnowledgeDocument
from app.models.schemas import (
    DocumentCategory,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdateRequest,
)
from app.services import storage


logger = get_logger(__name__)
settings = get_settings()


def ensure_bucket() -> None:
    """
    Prepare document storage: the MinIO bucket, or the local directory.
    """
    storage.ensure_bucket()


def upload_file(file_path: str, object_key: str, content_type: str) -> None:
    """
    Store an uploaded file.

    @param file_path: Local file path
    @param object_key: Storage object key
    @param content_type: MIME type
    """
    storage.put_file(file_path, object_key, content_type)


def download_file(object_key: str, dest_path: str) -> None:
    """
    Copy a stored file back to a local path.

    @param object_key: Storage object key
    @param dest_path: Local destination path
    """
    storage.get_file(object_key, dest_path)


def delete_file(object_key: str) -> None:
    """
    Remove a stored file.

    @param object_key: Storage object key
    """
    storage.delete_file(object_key)

async def create_document(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID,
    user_name: str,
    title: str,
    category: DocumentCategory,
    file_name: str,
    file_size: int,
    mime_type: str,
    minio_key: str,
    description: str | None = None,
    department: str | None = None,
    tags: list[str] | None = None,
    access_scope: str = "facility",
    version_label: str | None = None,
    effective_date: datetime | None = None,
    expiry_date: datetime | None = None,
) -> KnowledgeDocument:
    """
    Create a new document metadata record in PostgreSQL.

    @param db: Async database session
    @param facility_id: Owning facility
    @param user_id: Uploading user
    @param user_name: Uploading user's display name
    @param title: Document title
    @param category: Document category
    @param file_name: Original filename
    @param file_size: File size in bytes
    @param mime_type: MIME type
    @param minio_key: MinIO object key
    @param description: Optional description
    @param department: Optional department scope
    @param tags: Optional tags
    @param access_scope: Access scope (facility, department, role)
    @param version_label: Version label
    @param effective_date: Effective date
    @param expiry_date: Expiry date
    @returns Created KnowledgeDocument
    """
    doc = KnowledgeDocument(
        facility_id=facility_id,
        title=title,
        category=category.value,
        status=DocumentStatus.UPLOADING.value,
        description=description,
        department=department,
        tags=tags or [],
        access_scope=access_scope,
        file_name=file_name,
        file_size_bytes=file_size,
        mime_type=mime_type,
        minio_object_key=minio_key,
        version_label=version_label,
        effective_date=effective_date,
        expiry_date=expiry_date,
        created_by=user_id,
        uploaded_by_name=user_name,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    logger.info("document_created", doc_id=str(doc.id), title=title)
    return doc


async def update_document_status(
    db: AsyncSession,
    document_id: uuid.UUID,
    status: DocumentStatus,
    error_message: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
    celery_task_id: str | None = None,
) -> None:
    """
    Update a document's processing status.

    @param db: Async database session
    @param document_id: Document UUID
    @param status: New status
    @param error_message: Error message if failed
    @param chunk_count: Number of chunks processed
    @param page_count: Number of pages detected
    @param celery_task_id: Celery task ID
    """
    values: dict = {"status": status.value}
    if error_message is not None:
        values["error_message"] = error_message
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if page_count is not None:
        values["page_count"] = page_count
    if celery_task_id is not None:
        values["celery_task_id"] = celery_task_id

    stmt = (
        update(KnowledgeDocument)
        .where(KnowledgeDocument.id == document_id)
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()


async def get_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> KnowledgeDocument | None:
    """
    Get a document by ID, scoped to facility.

    @param db: Async database session
    @param document_id: Document UUID
    @param facility_id: Facility UUID (multi-tenant guard)
    @returns KnowledgeDocument or None
    """
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.facility_id == facility_id,
        KnowledgeDocument.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    facility_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    category: DocumentCategory | None = None,
    department: str | None = None,
    search: str | None = None,
    status: DocumentStatus | None = None,
) -> DocumentListResponse:
    """
    List documents for a facility with pagination and filters.

    @param db: Async database session
    @param facility_id: Facility UUID
    @param page: Page number (1-based)
    @param page_size: Items per page
    @param category: Optional category filter
    @param department: Optional department filter
    @param search: Optional title search string
    @param status: Optional status filter
    @returns DocumentListResponse with items and total count
    """
    base = select(KnowledgeDocument).where(
        KnowledgeDocument.facility_id == facility_id,
        KnowledgeDocument.is_deleted == False,  # noqa: E712
    )

    if category:
        base = base.where(KnowledgeDocument.category == category.value)
    if department:
        base = base.where(KnowledgeDocument.department == department)
    if status:
        base = base.where(KnowledgeDocument.status == status.value)
    if search:
        base = base.where(KnowledgeDocument.title.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    items_stmt = (
        base.order_by(KnowledgeDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(items_stmt)
    items = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_document_metadata(
    db: AsyncSession,
    document_id: uuid.UUID,
    facility_id: uuid.UUID,
    user_id: uuid.UUID,
    updates: DocumentUpdateRequest,
) -> KnowledgeDocument | None:
    """
    Update document metadata.

    @param db: Async database session
    @param document_id: Document UUID
    @param facility_id: Facility UUID
    @param user_id: User making the update
    @param updates: Fields to update
    @returns Updated document or None if not found
    """
    doc = await get_document(db, document_id, facility_id)
    if doc is None:
        return None

    update_data = updates.model_dump(exclude_unset=True)
    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = update_data["category"].value

    for field, value in update_data.items():
        setattr(doc, field, value)

    doc.updated_by = user_id
    await db.commit()
    await db.refresh(doc)
    return doc


async def soft_delete_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> bool:
    """
    Soft-delete a document (never hard-delete per CLAUDE.md).

    @param db: Async database session
    @param document_id: Document UUID
    @param facility_id: Facility UUID
    @returns True if document was found and deleted
    """
    doc = await get_document(db, document_id, facility_id)
    if doc is None:
        return False

    doc.is_deleted = True
    doc.deleted_at = datetime.utcnow()
    await db.commit()
    logger.info("document_soft_deleted", doc_id=str(document_id))
    return True


async def save_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    facility_id: uuid.UUID,
    chunks: list[dict],
) -> None:
    """
    Save text chunks to PostgreSQL.

    @param db: Async database session
    @param document_id: Parent document UUID
    @param facility_id: Facility UUID
    @param chunks: List of chunk dicts with text, chunk_index, page_number, section_title, token_count, qdrant_point_id
    """
    db_chunks = [
        DocumentChunk(
            document_id=document_id,
            facility_id=facility_id,
            chunk_index=c["chunk_index"],
            text=c["text"],
            page_number=c.get("page_number"),
            section_title=c.get("section_title"),
            token_count=c.get("token_count", 0),
            qdrant_point_id=c.get("qdrant_point_id"),
        )
        for c in chunks
    ]
    db.add_all(db_chunks)
    await db.commit()
    logger.info(
        "chunks_saved",
        document_id=str(document_id),
        count=len(db_chunks),
    )


def check_storage_health() -> str:
    """
    Check document storage connectivity.

    @returns Status string: 'connected' or 'disconnected'
    """
    return storage.health()