"""Workspace documents API endpoints — CRUD, AI actions, PDF export."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUser, DbSession
from app.schemas.workspace_document import (
    AddLineItemRequest,
    AiActionResponse,
    CheckDocumentRequest,
    DocModel,
    GenerateRequest,
    RewriteBlockRequest,
    WorkspaceDocumentCreate,
    WorkspaceDocumentListItem,
    WorkspaceDocumentPatch,
    WorkspaceDocumentRead,
    WorkspaceDocumentUpdate,
)
from app.services.workspace_document import workspace_document_service

router = APIRouter()


# ── CRUD ──


@router.get("", response_model=list[WorkspaceDocumentListItem])
async def list_workspace_documents(
    user: CurrentUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkspaceDocumentListItem]:
    """List workspace documents for the current tenant."""
    docs = await workspace_document_service.list(
        db, user.tenant_id, status=status_filter, limit=limit, offset=offset
    )
    return [WorkspaceDocumentListItem.model_validate(d) for d in docs]


@router.post("", response_model=WorkspaceDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_workspace_document(
    data: WorkspaceDocumentCreate,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Create a new workspace document."""
    doc = await workspace_document_service.create(db, user.tenant_id, data)
    return WorkspaceDocumentRead.model_validate(doc)


@router.get("/{doc_id}", response_model=WorkspaceDocumentRead)
async def get_workspace_document(
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Get a workspace document by ID."""
    doc = await workspace_document_service.get(db, user.tenant_id, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )
    return WorkspaceDocumentRead.model_validate(doc)


@router.patch("/{doc_id}", response_model=WorkspaceDocumentRead)
async def update_workspace_document(
    doc_id: UUID,
    data: WorkspaceDocumentUpdate,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Update a workspace document (metadata, status, etc.)."""
    doc = await workspace_document_service.update(db, user.tenant_id, doc_id, data)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )
    return WorkspaceDocumentRead.model_validate(doc)


@router.patch("/{doc_id}/content", response_model=WorkspaceDocumentRead)
async def patch_content(
    doc_id: UUID,
    data: WorkspaceDocumentPatch,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Patch content_json only (autosave endpoint)."""
    doc = await workspace_document_service.patch_content(
        db, user.tenant_id, doc_id, data.content_json
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )
    return WorkspaceDocumentRead.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_document(
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a workspace document."""
    deleted = await workspace_document_service.delete(db, user.tenant_id, doc_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )


@router.post("/{doc_id}/duplicate", response_model=WorkspaceDocumentRead, status_code=status.HTTP_201_CREATED)
async def duplicate_workspace_document(
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Duplicate a workspace document."""
    doc = await workspace_document_service.duplicate(db, user.tenant_id, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )
    return WorkspaceDocumentRead.model_validate(doc)


# ── AI Actions ──


@router.post("/{doc_id}/ai/generate", response_model=AiActionResponse)
async def ai_generate(
    doc_id: UUID,
    request: GenerateRequest,
    user: CurrentUser,
    db: DbSession,
) -> AiActionResponse:
    """Generate document content using RAG."""
    return await workspace_document_service.generate(db, user.tenant_id, doc_id, request)


@router.post("/{doc_id}/ai/rewrite", response_model=AiActionResponse)
async def ai_rewrite(
    doc_id: UUID,
    request: RewriteBlockRequest,
    user: CurrentUser,
    db: DbSession,
) -> AiActionResponse:
    """Rewrite a specific block using AI."""
    return await workspace_document_service.rewrite_block(
        db, user.tenant_id, doc_id, request
    )


@router.post("/{doc_id}/ai/check", response_model=AiActionResponse)
async def ai_check(
    doc_id: UUID,
    request: CheckDocumentRequest,
    user: CurrentUser,
    db: DbSession,
) -> AiActionResponse:
    """Check document for consistency / compliance."""
    return await workspace_document_service.check_document(
        db, user.tenant_id, doc_id, request
    )


@router.post("/{doc_id}/ai/add-line-item", response_model=AiActionResponse)
async def ai_add_line_item(
    doc_id: UUID,
    request: AddLineItemRequest,
    user: CurrentUser,
    db: DbSession,
) -> AiActionResponse:
    """Add a line item to a line_items block using AI."""
    return await workspace_document_service.add_line_item(
        db, user.tenant_id, doc_id, request
    )


@router.post("/{doc_id}/ai/suggest-title", response_model=WorkspaceDocumentRead)
async def ai_suggest_title(
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceDocumentRead:
    """Generate a summary title from document content and update the doc."""
    doc = await workspace_document_service.suggest_title(
        db, user.tenant_id, doc_id
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )
    return WorkspaceDocumentRead.model_validate(doc)


# ── Export ──


@router.post("/{doc_id}/export/pdf")
async def export_pdf(
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Export document as PDF. Returns presigned URL."""
    from app.services.pdf_export import pdf_export_service

    doc = await workspace_document_service.get(db, user.tenant_id, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )

    doc_model = DocModel.model_validate(doc.content_json)
    url = await pdf_export_service.export(
        doc_id=doc.id,
        title=doc.title,
        doc_model=doc_model,
        tenant_id=user.tenant_id,
    )

    # Update last_exported_url
    doc.last_exported_url = url
    await db.flush()

    return {"url": url}
