"""Document endpoints."""

from uuid import UUID

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.storage import storage_service
from app.services.usage import usage_service
from app.services.quota import quota_service
from app.workers.settings import redis_settings

router = APIRouter()


async def get_arq_pool() -> ArqRedis:
    """Get Arq Redis connection pool."""
    return await create_pool(redis_settings)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    collection_id: UUID | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Document]:
    """List documents for tenant, optionally filtered by collection."""
    tenant_id = user.tenant_id
    
    # Get collections for tenant
    query = (
        select(Document)
        .join(Collection)
        .where(Collection.tenant_id == tenant_id)
    )
    
    if collection_id:
        query = query.where(Document.collection_id == collection_id)
    
    if status:
        query = query.where(Document.status == status)
    
    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> Document:
    """Get a specific document."""
    result = await db.execute(
        select(Document)
        .join(Collection)
        .where(Document.id == document_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return document


@router.post("/upload/{collection_id}", response_model=DocumentUploadResponse)
async def upload_document(
    collection_id: UUID,
    user: CurrentUser,
    db: DbSession,
    file: UploadFile,
) -> DocumentUploadResponse:
    """Upload a document to a collection."""
    tenant_id = user.tenant_id
    
    # Check file limit for free tier
    allowed, error = await quota_service.check_upload_allowed(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )
    
    # Verify collection belongs to tenant
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
        .where(Collection.tenant_id == tenant_id)
    )
    collection = result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )
    
    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    
    # Check storage quota
    allowed, error = await usage_service.check_storage_quota(db, tenant_id, len(content))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )
    
    # Check for duplicate by hash
    content_hash = storage_service.compute_hash(content)
    result = await db.execute(
        select(Document)
        .where(Document.collection_id == collection_id)
        .where(Document.content_hash == content_hash)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return DocumentUploadResponse(
            id=existing.id,
            filename=existing.filename,
            status=DocumentStatus(existing.status),
            message="Document already exists (duplicate content)",
        )
    
    # Upload to S3
    filename = file.filename or "unnamed"
    content_type = file.content_type or "application/octet-stream"
    
    s3_key, _, file_size = await storage_service.upload_file(
        tenant_id=tenant_id,
        collection_id=collection_id,
        filename=filename,
        content=content,
        content_type=content_type,
    )
    
    # Create document record
    document = Document(
        collection_id=collection_id,
        filename=filename,
        content_type=content_type,
        s3_key=s3_key,
        content_hash=content_hash,
        file_size=file_size,
        status=DocumentStatus.PENDING.value,
    )
    db.add(document)
    await db.flush()
    
    # Record storage usage (tokens will be updated by worker after processing)
    await usage_service.record_ingestion(db, tenant_id, tokens=0, file_size=file_size)
    
    # Queue processing job
    pool = await get_arq_pool()
    await pool.enqueue_job("process_document", str(document.id))
    await pool.close()
    
    await db.commit()
    
    return DocumentUploadResponse(
        id=document.id,
        filename=filename,
        status=DocumentStatus.PENDING,
        message="Document queued for processing",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a document and its chunks."""
    from app.core.vector_store import vector_store
    
    result = await db.execute(
        select(Document)
        .join(Collection)
        .where(Document.id == document_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Delete from vector store
    await vector_store.delete_by_document(document_id)
    
    # Delete from S3
    await storage_service.delete_file(document.s3_key)
    
    # Reduce storage usage
    # Get tenant_id from collection
    from sqlalchemy import select as sql_select
    from app.models.collection import Collection as Coll
    coll_result = await db.execute(sql_select(Coll).where(Coll.id == document.collection_id))
    coll = coll_result.scalar_one()
    await usage_service.reduce_storage(db, coll.tenant_id, document.file_size)
    
    # Delete from DB (cascades to chunks)
    await db.delete(document)
    await db.commit()


@router.post("/{document_id}/reprocess", response_model=DocumentUploadResponse)
async def reprocess_document(
    document_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> DocumentUploadResponse:
    """Reprocess a failed document."""
    from app.core.vector_store import vector_store
    
    result = await db.execute(
        select(Document)
        .join(Collection)
        .where(Document.id == document_id)
        .where(Collection.tenant_id == user.tenant_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Delete existing chunks from vector store
    await vector_store.delete_by_document(document_id)
    
    # Reset status
    document.status = DocumentStatus.PENDING.value
    document.error_message = None
    
    # Queue processing job
    pool = await get_arq_pool()
    await pool.enqueue_job("process_document", str(document.id))
    await pool.close()
    
    await db.commit()
    
    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=DocumentStatus.PENDING,
        message="Document queued for reprocessing",
    )
