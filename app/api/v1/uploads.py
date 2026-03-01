"""Upload endpoints — dedicated section for document ingestion with OCR."""

from uuid import UUID

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.schemas.upload import (
    UploadDocumentDetail,
    UploadDocumentRead,
    UploadDownloadUrlResponse,
    UploadPageRead,
)
from app.services.storage import storage_service
from app.services.usage import usage_service
from app.services.quota import quota_service
from app.workers.settings import redis_settings

router = APIRouter()

# Special collection name for user uploads
UPLOADS_COLLECTION_NAME = "__uploads__"
UPLOADS_COLLECTION_DESCRIPTION = "Documents importés via la section Uploads"


async def get_arq_pool() -> ArqRedis:
    """Get Arq Redis connection pool."""
    return await create_pool(redis_settings)


async def _get_or_create_uploads_collection(
    db, tenant_id: UUID
) -> Collection:
    """Get or create the __uploads__ collection for a tenant."""
    result = await db.execute(
        select(Collection)
        .where(Collection.tenant_id == tenant_id)
        .where(Collection.name == UPLOADS_COLLECTION_NAME)
    )
    collection = result.scalar_one_or_none()

    if collection:
        return collection

    collection = Collection(
        tenant_id=tenant_id,
        name=UPLOADS_COLLECTION_NAME,
        description=UPLOADS_COLLECTION_DESCRIPTION,
    )
    db.add(collection)
    await db.flush()
    return collection


@router.get("", response_model=list[UploadDocumentRead])
async def list_uploads(
    user: CurrentUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[UploadDocumentRead]:
    """List documents in the uploads section."""
    tenant_id = user.tenant_id

    # Find the uploads collection
    col_result = await db.execute(
        select(Collection)
        .where(Collection.tenant_id == tenant_id)
        .where(Collection.name == UPLOADS_COLLECTION_NAME)
    )
    collection = col_result.scalar_one_or_none()

    if not collection:
        return []

    query = (
        select(Document)
        .where(Document.collection_id == collection.id)
    )

    if status_filter:
        query = query.where(Document.status == status_filter)

    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    documents = list(result.scalars().all())

    return [UploadDocumentRead.from_document(doc) for doc in documents]


@router.get("/{document_id}", response_model=UploadDocumentDetail)
async def get_upload(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> UploadDocumentDetail:
    """Get a specific uploaded document with its pages."""
    doc = await _get_upload_document(document_id, user.tenant_id, db)

    # Get pages
    pages_result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    pages = [
        UploadPageRead(
            page_number=p.page_number,
            text=p.text,
            meta=p.meta,
        )
        for p in pages_result.scalars().all()
    ]

    detail = UploadDocumentRead.from_document(doc)
    return UploadDocumentDetail(
        **detail.model_dump(),
        pages=pages,
    )


@router.get("/{document_id}/pages", response_model=list[UploadPageRead])
async def get_upload_pages(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[UploadPageRead]:
    """Get extracted pages/text for a document (reader view)."""
    await _get_upload_document(document_id, user.tenant_id, db)

    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )

    return [
        UploadPageRead(
            page_number=p.page_number,
            text=p.text,
            meta=p.meta,
        )
        for p in result.scalars().all()
    ]


@router.get("/{document_id}/download-url", response_model=UploadDownloadUrlResponse)
async def get_download_url(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> UploadDownloadUrlResponse:
    """Get a presigned URL to download the original file."""
    doc = await _get_upload_document(document_id, user.tenant_id, db)

    url = await storage_service.get_presigned_url(doc.s3_key, expires_in=3600)

    return UploadDownloadUrlResponse(
        url=url,
        filename=doc.filename,
        content_type=doc.content_type,
    )


@router.post("", response_model=list[UploadDocumentRead])
async def upload_documents(
    user: CurrentUser,
    db: DbSession,
    files: list[UploadFile],
) -> list[UploadDocumentRead]:
    """Upload one or more documents to the uploads section.

    Supports PDF, images (JPG, PNG, TIFF, WebP), DOCX, XLSX, PPTX, TXT, HTML, MD.
    Documents are queued for processing (Docling + OCR if needed) and indexed in RAG.
    """
    tenant_id = user.tenant_id

    # Check file limit for free tier
    allowed, error = await quota_service.check_upload_allowed(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )

    # Get or create the uploads collection
    collection = await _get_or_create_uploads_collection(db, tenant_id)

    results: list[UploadDocumentRead] = []
    pool = await get_arq_pool()

    try:
        for file in files:
            content = await file.read()
            if not content:
                continue

            # Check storage quota
            allowed, error = await usage_service.check_storage_quota(
                db, tenant_id, len(content)
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error,
                )

            # Check for duplicate
            content_hash = storage_service.compute_hash(content)
            dup_result = await db.execute(
                select(Document)
                .where(Document.collection_id == collection.id)
                .where(Document.content_hash == content_hash)
            )
            existing = dup_result.scalar_one_or_none()

            if existing:
                results.append(UploadDocumentRead.from_document(existing))
                continue

            # Upload to S3
            filename = file.filename or "unnamed"
            content_type = file.content_type or "application/octet-stream"

            s3_key, _, file_size = await storage_service.upload_file(
                tenant_id=tenant_id,
                collection_id=collection.id,
                filename=filename,
                content=content,
                content_type=content_type,
            )

            # Create document record with rich metadata
            document = Document(
                collection_id=collection.id,
                filename=filename,
                content_type=content_type,
                s3_key=s3_key,
                content_hash=content_hash,
                file_size=file_size,
                status=DocumentStatus.PENDING.value,
                doc_metadata={
                    "source": "uploads",
                    "uploaded_via": "global_uploads",
                    "origin": "uploads",
                    "ocr_used": False,
                    "parser_used": "pending",
                },
            )
            db.add(document)
            await db.flush()

            # Record storage usage
            await usage_service.record_ingestion(
                db, tenant_id, tokens=0, file_size=file_size
            )

            # Queue processing job
            await pool.enqueue_job("process_document", str(document.id))

            results.append(UploadDocumentRead.from_document(document))
    finally:
        await pool.close()

    await db.commit()
    return results


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an uploaded document (ordered: status → vectors → S3 → DB)."""
    from app.core.vector_store import vector_store

    doc = await _get_upload_document(document_id, user.tenant_id, db)

    # 1. Mark as deleting
    doc.status = "deleting"
    await db.flush()

    # 2. Delete from vector store
    await vector_store.delete_by_document(document_id)

    # 3. Delete from S3
    await storage_service.delete_file(doc.s3_key)

    # 4. Reduce storage usage
    col_result = await db.execute(
        select(Collection).where(Collection.id == doc.collection_id)
    )
    col = col_result.scalar_one()
    await usage_service.reduce_storage(db, col.tenant_id, doc.file_size)

    # 5. Delete from DB (cascades to chunks + pages)
    await db.delete(doc)
    await db.commit()


@router.post("/{document_id}/reprocess", response_model=UploadDocumentRead)
async def reprocess_upload(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> UploadDocumentRead:
    """Reprocess a failed uploaded document."""
    from app.core.vector_store import vector_store

    doc = await _get_upload_document(document_id, user.tenant_id, db)

    # Delete existing chunks from vector store
    await vector_store.delete_by_document(document_id)

    # Reset status
    doc.status = DocumentStatus.PENDING.value
    doc.error_message = None

    # Queue processing job
    pool = await get_arq_pool()
    await pool.enqueue_job("process_document", str(doc.id))
    await pool.close()

    await db.commit()
    return UploadDocumentRead.from_document(doc)


async def _get_upload_document(
    document_id: UUID, tenant_id: UUID, db
) -> Document:
    """Get an uploaded document, verifying tenant ownership."""
    result = await db.execute(
        select(Document)
        .join(Collection)
        .where(Document.id == document_id)
        .where(Collection.tenant_id == tenant_id)
        .where(Collection.name == UPLOADS_COLLECTION_NAME)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded document not found",
        )

    return document
