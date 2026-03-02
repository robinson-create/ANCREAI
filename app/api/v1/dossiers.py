"""Dossier endpoints — personal workspaces within an organization.

All routes are scoped to the current user: a user can only see/manage
their own dossiers. There is no admin override — dossiers are private.
"""

import asyncio
import json
import logging
from uuid import UUID, uuid4

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.database import async_session_maker
from app.deps import CurrentMember, CurrentUser, DbSession
from app.models.dossier import Dossier
from app.models.dossier_document import DossierDocument, DossierDocumentStatus
from app.models.conversation import Conversation
from app.models.enums import ContentScope
from app.models.message import Message, MessageRole
from app.schemas.dossier import (
    DossierCreate,
    DossierDocumentRead,
    DossierDocumentUploadResponse,
    DossierRead,
    DossierReadWithStats,
    DossierUpdate,
)
from app.core.vector_store import vector_store
from app.services.chat import chat_service
from app.services.storage import storage_service
from app.services.usage import usage_service
from app.services.quota import quota_service
from app.workers.settings import redis_settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_arq_pool() -> ArqRedis:
    return await create_pool(redis_settings)


def _ensure_owner(dossier: Dossier, user_id: UUID) -> None:
    """Hard ownership check — even admins cannot see other users' dossiers."""
    if dossier.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dossier not found",
        )


# ---------------------------------------------------------------------------
# Dossier CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DossierReadWithStats])
async def list_dossiers(
    user: CurrentUser,
    _member: CurrentMember,  # ensures active seat
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List the current user's dossiers with stats."""
    result = await db.execute(
        select(
            Dossier,
            func.count(DossierDocument.id).label("documents_count"),
        )
        .outerjoin(DossierDocument, DossierDocument.dossier_id == Dossier.id)
        .where(Dossier.user_id == user.id)
        .where(Dossier.tenant_id == user.tenant_id)
        .group_by(Dossier.id)
        .order_by(Dossier.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )

    items = []
    for row in result.all():
        dossier = row[0]
        doc_count = row[1]

        # Count personal conversations in this dossier
        conv_result = await db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.dossier_id == dossier.id)
            .where(Conversation.scope == ContentScope.PERSONAL.value)
        )
        conv_count = conv_result.scalar_one() or 0

        items.append({
            **DossierRead.model_validate(dossier).model_dump(),
            "documents_count": doc_count,
            "conversations_count": conv_count,
        })

    return items


@router.post("", response_model=DossierRead, status_code=status.HTTP_201_CREATED)
async def create_dossier(
    data: DossierCreate,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> Dossier:
    """Create a new personal dossier."""
    dossier = Dossier(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=data.name,
        description=data.description,
        color=data.color,
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.get("/{dossier_id}", response_model=DossierReadWithStats)
async def get_dossier(
    dossier_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> dict:
    """Get a specific dossier with stats."""
    result = await db.execute(
        select(Dossier).where(Dossier.id == dossier_id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found")
    _ensure_owner(dossier, user.id)

    doc_result = await db.execute(
        select(func.count(DossierDocument.id))
        .where(DossierDocument.dossier_id == dossier_id)
    )
    conv_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.dossier_id == dossier_id)
        .where(Conversation.scope == ContentScope.PERSONAL.value)
    )

    return {
        **DossierRead.model_validate(dossier).model_dump(),
        "documents_count": doc_result.scalar_one() or 0,
        "conversations_count": conv_result.scalar_one() or 0,
    }


@router.patch("/{dossier_id}", response_model=DossierRead)
async def update_dossier(
    dossier_id: UUID,
    data: DossierUpdate,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> Dossier:
    """Update a dossier."""
    result = await db.execute(
        select(Dossier).where(Dossier.id == dossier_id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found")
    _ensure_owner(dossier, user.id)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(dossier, key, value)

    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.delete("/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dossier(
    dossier_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> None:
    """Delete a dossier and all its documents/conversations."""
    result = await db.execute(
        select(Dossier).where(Dossier.id == dossier_id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found")
    _ensure_owner(dossier, user.id)

    # Delete personal vectors from Qdrant
    await vector_store.delete_by_dossier(dossier_id, user.tenant_id)

    await db.delete(dossier)
    await db.commit()


# ---------------------------------------------------------------------------
# Dossier Documents
# ---------------------------------------------------------------------------


@router.get("/{dossier_id}/documents", response_model=list[DossierDocumentRead])
async def list_dossier_documents(
    dossier_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[DossierDocument]:
    """List documents in a dossier."""
    # Ownership check via user_id filter
    result = await db.execute(
        select(DossierDocument)
        .where(DossierDocument.dossier_id == dossier_id)
        .where(DossierDocument.user_id == user.id)
        .order_by(DossierDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post(
    "/{dossier_id}/documents",
    response_model=DossierDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dossier_document(
    dossier_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
    file: UploadFile,
) -> DossierDocumentUploadResponse:
    """Upload a personal document into a dossier."""
    # Verify dossier ownership
    result = await db.execute(
        select(Dossier).where(Dossier.id == dossier_id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found")
    _ensure_owner(dossier, user.id)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    content_hash = storage_service.compute_hash(content)

    # Check duplicate within this dossier
    dup_result = await db.execute(
        select(DossierDocument)
        .where(DossierDocument.dossier_id == dossier_id)
        .where(DossierDocument.content_hash == content_hash)
    )
    existing = dup_result.scalar_one_or_none()
    if existing:
        return DossierDocumentUploadResponse(
            id=existing.id,
            filename=existing.filename,
            status=existing.status,
            message="Document already exists (duplicate content)",
        )

    # Upload to S3 with personal prefix
    filename = file.filename or "unnamed"
    content_type = file.content_type or "application/octet-stream"
    s3_key = f"personal/{user.id}/{dossier_id}/{filename}"

    await storage_service.upload_file_raw(
        s3_key=s3_key,
        content=content,
        content_type=content_type,
    )

    doc = DossierDocument(
        dossier_id=dossier_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        filename=filename,
        content_type=content_type,
        s3_key=s3_key,
        content_hash=content_hash,
        file_size=len(content),
        status=DossierDocumentStatus.PENDING,
    )
    db.add(doc)
    await db.flush()

    # Queue processing job (same worker, different scope)
    pool = await get_arq_pool()
    await pool.enqueue_job("process_dossier_document", str(doc.id))
    await pool.close()

    await db.commit()

    return DossierDocumentUploadResponse(
        id=doc.id,
        filename=filename,
        status=DossierDocumentStatus.PENDING,
        message="Document queued for processing",
    )


@router.delete(
    "/{dossier_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dossier_document(
    dossier_id: UUID,
    document_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> None:
    """Delete a personal document from a dossier."""
    result = await db.execute(
        select(DossierDocument)
        .where(DossierDocument.id == document_id)
        .where(DossierDocument.dossier_id == dossier_id)
        .where(DossierDocument.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete from S3
    await storage_service.delete_file(doc.s3_key)

    # Delete personal vectors from Qdrant
    await vector_store.delete_by_dossier_document(doc.id, user.tenant_id)

    await db.delete(doc)
    await db.commit()


# ---------------------------------------------------------------------------
# Dossier Chat (personal conversations)
# ---------------------------------------------------------------------------

_STREAM_END = object()

PERSONAL_SYSTEM_PROMPT = (
    "Tu es un assistant personnel. Tu aides l'utilisateur en t'appuyant "
    "sur les documents de son dossier personnel. Réponds de manière claire, "
    "concise et structurée. Si tu ne trouves pas l'information dans les "
    "documents fournis, dis-le honnêtement."
)


class DossierChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    include_history: bool = True
    max_history_messages: int = 10


async def _format_sse(event: str, data: str) -> str:
    lines = data.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


async def _get_dossier_for_chat(
    dossier_id: UUID, user_id: UUID, db,
) -> Dossier:
    """Fetch dossier with ownership check."""
    result = await db.execute(
        select(Dossier).where(Dossier.id == dossier_id)
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found"
        )
    _ensure_owner(dossier, user_id)
    return dossier


async def _get_or_create_conversation(
    db, *, conversation_id: UUID | None, dossier_id: UUID,
    tenant_id: UUID, user_id: UUID,
) -> Conversation:
    """Get existing or create new personal conversation."""
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.dossier_id == dossier_id)
            .where(Conversation.user_id == user_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    # Create new conversation
    conv = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        scope=ContentScope.PERSONAL.value,
        dossier_id=dossier_id,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _run_dossier_llm_producer(
    queue: asyncio.Queue,
    *,
    request_message: str,
    tenant_id: UUID,
    dossier_id: UUID,
    system_prompt: str | None,
    history: list[dict],
    conversation_ref_id: UUID,
    user_message_id: UUID,
):
    """Streaming LLM producer for dossier chat (personal scope)."""
    logger.info("dossier_chat_started", extra={
        "tenant_id": str(tenant_id),
        "dossier_id": str(dossier_id),
        "conversation_ref_id": str(conversation_ref_id),
    })
    full_response = ""
    citations_for_db: list = []
    blocks_for_db: list = []
    tokens_input = 0
    tokens_output = 0

    try:
        async with async_session_maker() as retrieval_db:
            async for event in chat_service.chat_stream(
                message=request_message,
                tenant_id=tenant_id,
                collection_ids=[],
                system_prompt=system_prompt,
                conversation_history=history,
                db=retrieval_db,
                dossier_ids=[dossier_id],
            ):
                if event.event == "token":
                    full_response += event.data
                    await queue.put(("token", event.data))
                elif event.event == "block":
                    blocks_for_db.append(event.data)
                    await queue.put(("block", event.data))
                elif event.event == "citations":
                    citations_for_db = [
                        c.model_dump(mode="json") if hasattr(c, "model_dump")
                        else c
                        for c in event.data
                    ]
                    await queue.put(("citations", citations_for_db))
                elif event.event == "done":
                    tokens_input = event.data.get("tokens_input", 0)
                    tokens_output = event.data.get("tokens_output", 0)
                    await queue.put(("done", event.data))
                elif event.event == "error":
                    await queue.put(("error", event.data))
                else:
                    await queue.put((event.event, event.data))

    except Exception as e:
        logger.error("dossier_chat_error", extra={
            "tenant_id": str(tenant_id),
            "dossier_id": str(dossier_id),
            "error": str(e),
        })
        await queue.put(("error", str(e)))

    finally:
        if full_response or blocks_for_db:
            try:
                async with async_session_maker() as save_db:
                    await save_db.execute(
                        update(Message)
                        .where(Message.id == user_message_id)
                        .values(tokens_input=tokens_input)
                    )
                    assistant_message = Message(
                        conversation_ref_id=conversation_ref_id,
                        role=MessageRole.ASSISTANT.value,
                        content=full_response,
                        citations=citations_for_db or None,
                        blocks=blocks_for_db or None,
                        tokens_output=tokens_output,
                    )
                    save_db.add(assistant_message)
                    await usage_service.record_chat(
                        save_db, tenant_id, tokens_input, tokens_output
                    )
                    await save_db.commit()
                    logger.info("dossier_chat_completed", extra={
                        "tenant_id": str(tenant_id),
                        "dossier_id": str(dossier_id),
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                    })
            except Exception as save_err:
                logger.error("dossier_chat_save_error", extra={
                    "tenant_id": str(tenant_id),
                    "dossier_id": str(dossier_id),
                    "error": str(save_err),
                })
                await queue.put(("error", "Failed to save message"))

        await queue.put(_STREAM_END)


@router.post("/{dossier_id}/chat/stream")
async def dossier_chat_stream(
    dossier_id: UUID,
    request: DossierChatRequest,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> StreamingResponse:
    """Chat within a personal dossier (SSE streaming).

    RAG scope: only the dossier's personal documents.
    """
    dossier = await _get_dossier_for_chat(dossier_id, user.id, db)
    tenant_id = user.tenant_id

    # Quota check
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
    await quota_service.record_chat_request(db, user.id)

    # Get or create conversation
    conv = await _get_or_create_conversation(
        db,
        conversation_id=request.conversation_id,
        dossier_id=dossier_id,
        tenant_id=tenant_id,
        user_id=user.id,
    )

    # History
    history: list[dict] = []
    if request.include_history and request.conversation_id:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_ref_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(request.max_history_messages)
        )
        messages = list(reversed(result.scalars().all()))
        history = [{"role": m.role, "content": m.content} for m in messages]

    await db.commit()  # commit conversation creation

    # Save user message
    async with async_session_maker() as save_db:
        user_message = Message(
            conversation_ref_id=conv.id,
            role=MessageRole.USER.value,
            content=request.message,
            tokens_input=0,
        )
        save_db.add(user_message)
        await save_db.commit()
        user_message_id = user_message.id

    # Launch producer
    queue: asyncio.Queue = asyncio.Queue()
    producer_task = asyncio.create_task(
        _run_dossier_llm_producer(
            queue,
            request_message=request.message,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            system_prompt=PERSONAL_SYSTEM_PROMPT,
            history=history,
            conversation_ref_id=conv.id,
            user_message_id=user_message_id,
        )
    )
    producer_task.add_done_callback(
        lambda t: t.exception() if not t.cancelled() else None
    )

    async def event_generator():
        yield await _format_sse("conversation_id", str(conv.id))
        while True:
            item = await queue.get()
            if item is _STREAM_END:
                break
            event_type, event_data = item
            if event_type == "token":
                yield await _format_sse("token", event_data)
            elif event_type in ("block", "citations", "done"):
                yield await _format_sse(event_type, json.dumps(event_data))
            elif event_type == "error":
                yield await _format_sse("error", event_data)
            else:
                yield await _format_sse(
                    event_type,
                    json.dumps(event_data) if isinstance(event_data, dict) else str(event_data),
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{dossier_id}/conversations")
async def list_dossier_conversations(
    dossier_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """List conversations in a personal dossier."""
    await _get_dossier_for_chat(dossier_id, user.id, db)

    result = await db.execute(
        select(Conversation)
        .where(Conversation.dossier_id == dossier_id)
        .where(Conversation.user_id == user.id)
        .where(Conversation.scope == ContentScope.PERSONAL.value)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        # Get first user message as title
        first_msg_result = await db.execute(
            select(Message.content)
            .where(Message.conversation_ref_id == conv.id)
            .where(Message.role == "user")
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        first_msg = first_msg_result.scalar_one_or_none()
        title = conv.title or (
            (first_msg[:50] + "...") if first_msg and len(first_msg) > 50
            else first_msg or "Conversation"
        )

        # Message count
        count_result = await db.execute(
            select(func.count(Message.id))
            .where(Message.conversation_ref_id == conv.id)
        )
        msg_count = count_result.scalar_one() or 0

        items.append({
            "id": str(conv.id),
            "title": title,
            "message_count": msg_count,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        })

    return items


@router.get("/{dossier_id}/conversations/{conversation_id}")
async def get_dossier_conversation(
    dossier_id: UUID,
    conversation_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """Get messages for a dossier conversation."""
    await _get_dossier_for_chat(dossier_id, user.id, db)

    # Verify conversation belongs to this dossier + user
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.dossier_id == dossier_id)
        .where(Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    result = await db.execute(
        select(Message)
        .where(Message.conversation_ref_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "blocks": m.blocks,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
