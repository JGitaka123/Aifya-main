"""
Document management API endpoints.
Upload, list, update, delete institutional documents.
"""

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth.dependencies import CurrentUser, get_current_user, require_roles
from app.config import get_settings
from app.database import get_db
from app.models.schemas import (
    ChunkResponse,
    DocumentCategory,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdateRequest,
    IngestStatus,
    IngestStatusResponse,
)
from app.services import document_service
from app.services.ingest_pipeline import run_ingest
from app.services.retrieval_service import delete_document_vectors

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/documents", tags=["documents"])

_EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".rtf": "text/rtf",
}


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an institutional document",
)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=3, max_length=500),
    category: DocumentCategory = Form(...),
    description: str | None = Form(None, max_length=2000),
    department: str | None = Form(None, max_length=100),
    tags: str = Form("", description="Comma-separated tags"),
    access_scope: str = Form("facility"),
    version_label: str | None = Form(None, max_length=50),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "doctor", "nurse", "pharmacist", "lab_tech", "facility_admin")
    ),
) -> DocumentResponse:
    """
    Upload a document for institutional knowledge.
    Accepts PDF, DOCX, DOC, TXT, MD, RTF files up to the configured size limit.
    Triggers async ingestion (parse → chunk → embed → store).

    @param file: Uploaded file
    @param title: Document title
    @param category: Document category
    @param description: Optional description
    @param department: Optional department scope
    @param tags: Comma-separated tags
    @param access_scope: Access scope (facility, department, role)
    @param version_label: Version label
    @param db: Database session
    @param current_user: Authenticated user
    @returns DocumentResponse with processing status
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(settings.allowed_extensions)}",
        )

    content = await file.read()
    file_size = len(content)

    # max_file_size_mb == 0 means "no limit": any size is accepted.
    if (
        settings.max_file_size_mb > 0
        and file_size > settings.max_file_size_mb * 1024 * 1024
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File exceeds maximum size of "
                f"{settings.max_file_size_mb}MB. Raise MAX_FILE_SIZE_MB to "
                f"accept larger documents."
            ),
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    mime_type = _EXT_TO_MIME.get(ext, "application/octet-stream")
    minio_key = f"{current_user.facility_id}/{uuid.uuid4()}{ext}"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        document_service.upload_file(tmp_path, minio_key, mime_type)
    finally:
        os.unlink(tmp_path)

    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else []

    doc = await document_service.create_document(
        db=db,
        facility_id=current_user.facility_id,
        user_id=current_user.user_id,
        user_name=current_user.name,
        title=title,
        category=category,
        file_name=file.filename,
        file_size=file_size,
        mime_type=mime_type,
        minio_key=minio_key,
        description=description,
        department=department,
        tags=tag_list,
        access_scope=access_scope,
        version_label=version_label,
    )

    if settings.ingest_mode == "celery":
        from app.tasks.ingest import ingest_document

        task = ingest_document.delay(
            document_id=str(doc.id),
            facility_id=str(current_user.facility_id),
            object_key=minio_key,
            mime_type=mime_type,
            document_title=title,
            category=category.value,
            department=department,
        )
        await document_service.update_document_status(
            db, doc.id, DocumentStatus.PROCESSING, celery_task_id=task.id
        )
        await db.refresh(doc)
        logger.info(
            "document_upload_initiated",
            doc_id=str(doc.id),
            task_id=task.id,
            user=current_user.email,
        )
    else:
        try:
            await run_ingest(
                session=db,
                document_id=str(doc.id),
                facility_id=str(current_user.facility_id),
                object_key=minio_key,
                mime_type=mime_type,
                document_title=title,
                category=category.value,
                department=department,
            )
        except Exception as exc:
            logger.error(
                "document_ingest_inline_failed",
                doc_id=str(doc.id),
                error=str(exc),
                user=current_user.email,
            )
        await db.refresh(doc)
        logger.info(
            "document_ingested_inline",
            doc_id=str(doc.id),
            status=doc.status,
            chunks=doc.chunk_count,
            user=current_user.email,
        )

    return DocumentResponse.model_validate(doc)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List institutional documents",
)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: DocumentCategory | None = Query(None),
    department: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
    doc_status: DocumentStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentListResponse:
    """
    List documents with pagination and optional filters.
    Always scoped to the user's facility.

    @param page: Page number (1-based)
    @param page_size: Items per page
    @param category: Filter by category
    @param department: Filter by department
    @param search: Search in title
    @param doc_status: Filter by status
    @param db: Database session
    @param current_user: Authenticated user
    @returns Paginated document list
    """
    return await document_service.list_documents(
        db=db,
        facility_id=current_user.facility_id,
        page=page,
        page_size=page_size,
        category=category,
        department=department,
        search=search,
        status=doc_status,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentResponse:
    """
    Get a single document by ID.

    @param document_id: Document UUID
    @param db: Database session
    @param current_user: Authenticated user
    @returns Document details
    """
    doc = await document_service.get_document(db, document_id, current_user.facility_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return DocumentResponse.model_validate(doc)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
)
async def update_document(
    document_id: uuid.UUID,
    updates: DocumentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> DocumentResponse:
    """
    Update document metadata (title, category, tags, etc.).
    Only admins can update documents.

    @param document_id: Document UUID
    @param updates: Fields to update
    @param db: Database session
    @param current_user: Authenticated admin user
    @returns Updated document
    """
    doc = await document_service.update_document_metadata(
        db, document_id, current_user.facility_id, current_user.user_id, updates
    )
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return DocumentResponse.model_validate(doc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> None:
    """
    Soft-delete a document and its vectors.
    Removes embeddings from Qdrant, marks as deleted in PostgreSQL.
    File remains in MinIO for audit trail (20-year retention).

    @param document_id: Document UUID
    @param db: Database session
    @param current_user: Authenticated admin user
    """
    doc = await document_service.get_document(db, document_id, current_user.facility_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await delete_document_vectors(db, current_user.facility_id, document_id)

    deleted = await document_service.soft_delete_document(
        db, document_id, current_user.facility_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    logger.info(
        "document_deleted",
        doc_id=str(document_id),
        user=current_user.email,
    )


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkResponse],
    summary="Get document chunks",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ChunkResponse]:
    """
    List all text chunks for a document.
    Useful for reviewing how the document was parsed.

    @param document_id: Document UUID
    @param db: Database session
    @param current_user: Authenticated user
    @returns List of chunks
    """
    from sqlalchemy import select
    from app.models.document import DocumentChunk

    doc = await document_service.get_document(db, document_id, current_user.facility_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    stmt = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.facility_id == current_user.facility_id,
        )
        .order_by(DocumentChunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return [ChunkResponse.model_validate(c) for c in chunks]


@router.get(
    "/{document_id}/ingest-status",
    response_model=IngestStatusResponse,
    summary="Check document ingestion status",
)
async def get_ingest_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> IngestStatusResponse:
    """
    Check the processing status of a document ingestion task.

    @param document_id: Document UUID
    @param db: Database session
    @param current_user: Authenticated user
    @returns Ingestion status with progress
    """
    doc = await document_service.get_document(db, document_id, current_user.facility_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    task_id = doc.celery_task_id or ""
    progress = 0.0
    ingest_status = IngestStatus.PENDING
    error_msg: str | None = None

    if doc.status == DocumentStatus.READY.value:
        ingest_status = IngestStatus.COMPLETED
        progress = 100.0
    elif doc.status == DocumentStatus.FAILED.value:
        ingest_status = IngestStatus.FAILED
        error_msg = doc.error_message
    elif task_id:
        from celery.result import AsyncResult

        result = AsyncResult(task_id)
        if result.state == "PENDING":
            ingest_status = IngestStatus.PENDING
        elif result.state in ("PROCESSING", "PARSING", "CHUNKING", "EMBEDDING", "STORING", "SAVING_CHUNKS"):
            ingest_status = IngestStatus(result.state.lower()) if result.state.lower() in IngestStatus.__members__ else IngestStatus.STARTED
            meta = result.info or {}
            progress = meta.get("progress", 0.0) if isinstance(meta, dict) else 0.0
        elif result.state == "SUCCESS":
            ingest_status = IngestStatus.COMPLETED
            progress = 100.0
        elif result.state == "FAILURE":
            ingest_status = IngestStatus.FAILED
            error_msg = str(result.info) if result.info else "Unknown error"

    return IngestStatusResponse(
        document_id=doc.id,
        task_id=task_id,
        status=ingest_status,
        progress_pct=progress,
        error_message=error_msg,
        chunks_processed=doc.chunk_count,
        total_chunks=doc.chunk_count,
    )
