"""Project endpoints — private per-user knowledge bases.

All routes are scoped to the current user: a user can only see/manage
their own projects. There is no admin override — projects are private.
Strict tenant isolation via double filter (tenant_id in SQL + user_id check).
"""

import asyncio
import json
import logging
from uuid import UUID, uuid4

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update

from app.database import async_session_maker
from app.deps import CurrentMember, CurrentUser, DbSession
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.enums import ContentScope
from app.models.message import Message, MessageRole
from app.models.project import Project
from app.models.project_document import ProjectDocument, ProjectDocumentStatus
from app.models.project_knowledge import ProjectKnowledge
from app.schemas.project import (
    ProjectChatRequest,
    ProjectCreate,
    ProjectDocumentRead,
    ProjectDocumentUploadResponse,
    ProjectKnowledgeRead,
    ProjectRead,
    ProjectReadWithStats,
    ProjectSummarizeRequest,
    ProjectUpdate,
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


async def _get_project(
    project_id: UUID, user_id: UUID, tenant_id: UUID, db,
) -> Project:
    """Fetch project with tenant + ownership check (404 = not found OR unauthorized)."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.tenant_id == tenant_id)  # Cross-tenant block
    )
    project = result.scalar_one_or_none()
    if not project or project.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProjectReadWithStats])
async def list_projects(
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List the current user's projects with stats."""
    result = await db.execute(
        select(
            Project,
            func.count(ProjectDocument.id).label("documents_count"),
        )
        .outerjoin(ProjectDocument, ProjectDocument.project_id == Project.id)
        .where(Project.user_id == user.id)
        .where(Project.tenant_id == user.tenant_id)
        .group_by(Project.id)
        .order_by(Project.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )

    items = []
    for row in result.all():
        project = row[0]
        doc_count = row[1]

        # Count project conversations
        conv_result = await db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.project_id == project.id)
            .where(Conversation.scope == ContentScope.PROJECT.value)
        )
        conv_count = conv_result.scalar_one() or 0

        # Count knowledge entries
        knowledge_result = await db.execute(
            select(func.count(ProjectKnowledge.id))
            .where(ProjectKnowledge.project_id == project.id)
        )
        knowledge_count = knowledge_result.scalar_one() or 0

        items.append({
            **ProjectRead.model_validate(project).model_dump(),
            "documents_count": doc_count,
            "conversations_count": conv_count,
            "knowledge_count": knowledge_count,
        })

    return items


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> Project:
    """Create a new project."""
    project = Project(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=data.name,
        description=data.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectReadWithStats)
async def get_project(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> dict:
    """Get a specific project with stats."""
    project = await _get_project(project_id, user.id, user.tenant_id, db)

    doc_result = await db.execute(
        select(func.count(ProjectDocument.id))
        .where(ProjectDocument.project_id == project_id)
    )
    conv_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.project_id == project_id)
        .where(Conversation.scope == ContentScope.PROJECT.value)
    )
    knowledge_result = await db.execute(
        select(func.count(ProjectKnowledge.id))
        .where(ProjectKnowledge.project_id == project_id)
    )

    return {
        **ProjectRead.model_validate(project).model_dump(),
        "documents_count": doc_result.scalar_one() or 0,
        "conversations_count": conv_result.scalar_one() or 0,
        "knowledge_count": knowledge_result.scalar_one() or 0,
    }


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> Project:
    """Update a project."""
    project = await _get_project(project_id, user.id, user.tenant_id, db)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> None:
    """Delete a project and all its documents/conversations/knowledge.

    Order: Qdrant FIRST, then DB cascade.
    """
    project = await _get_project(project_id, user.id, user.tenant_id, db)

    # 1. Delete project vectors from Qdrant
    await vector_store.delete_by_project(project_id, user.tenant_id)

    # 2. DB cascade (documents, chunks, conversations, knowledge)
    await db.delete(project)
    await db.commit()


# ---------------------------------------------------------------------------
# Project Documents
# ---------------------------------------------------------------------------


@router.get("/{project_id}/documents", response_model=list[ProjectDocumentRead])
async def list_project_documents(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[ProjectDocument]:
    """List documents in a project."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    result = await db.execute(
        select(ProjectDocument)
        .where(ProjectDocument.project_id == project_id)
        .where(ProjectDocument.user_id == user.id)
        .order_by(ProjectDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/documents",
    response_model=ProjectDocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_document(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
    file: UploadFile,
) -> ProjectDocumentUploadResponse:
    """Upload a document into a project."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    content_hash = storage_service.compute_hash(content)

    # Check duplicate within this project
    dup_result = await db.execute(
        select(ProjectDocument)
        .where(ProjectDocument.project_id == project_id)
        .where(ProjectDocument.content_hash == content_hash)
    )
    existing = dup_result.scalar_one_or_none()
    if existing:
        return ProjectDocumentUploadResponse(
            id=existing.id,
            filename=existing.filename,
            status=existing.status,
            message="Document already exists (duplicate content)",
        )

    # Upload to S3 with project prefix
    filename = file.filename or "unnamed"
    content_type = file.content_type or "application/octet-stream"
    s3_key = f"projects/{user.id}/{project_id}/{filename}"

    await storage_service.upload_file_raw(
        s3_key=s3_key,
        content=content,
        content_type=content_type,
    )

    doc = ProjectDocument(
        project_id=project_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        filename=filename,
        content_type=content_type,
        s3_key=s3_key,
        content_hash=content_hash,
        file_size=len(content),
        status=ProjectDocumentStatus.PENDING,
    )
    db.add(doc)
    await db.flush()

    # Queue processing job
    pool = await get_arq_pool()
    await pool.enqueue_job("process_project_document", str(doc.id))
    await pool.close()

    await db.commit()

    return ProjectDocumentUploadResponse(
        id=doc.id,
        filename=filename,
        status=ProjectDocumentStatus.PENDING,
        message="Document queued for processing",
    )


@router.delete(
    "/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_document(
    project_id: UUID,
    document_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> None:
    """Delete a document from a project. Qdrant FIRST, then DB."""
    result = await db.execute(
        select(ProjectDocument)
        .where(ProjectDocument.id == document_id)
        .where(ProjectDocument.project_id == project_id)
        .where(ProjectDocument.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete from S3
    await storage_service.delete_file(doc.s3_key)

    # Delete project vectors from Qdrant
    await vector_store.delete_by_project_document(doc.id, user.tenant_id)

    await db.delete(doc)
    await db.commit()


# ---------------------------------------------------------------------------
# Project Chat (project-scoped conversations)
# ---------------------------------------------------------------------------

_STREAM_END = object()

PROJECT_SYSTEM_PROMPT = (
    "Tu es un assistant de projet. Tu aides l'utilisateur en t'appuyant "
    "sur les documents et les connaissances accumulées dans ce projet. "
    "Réponds de manière claire, concise et structurée. Si tu ne trouves "
    "pas l'information dans les documents fournis, dis-le honnêtement."
)


async def _format_sse(event: str, data: str) -> str:
    lines = data.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


async def _get_or_create_project_conversation(
    db, *, conversation_id: UUID | None, project_id: UUID,
    tenant_id: UUID, user_id: UUID,
) -> Conversation:
    """Get existing or create new project conversation."""
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.project_id == project_id)
            .where(Conversation.user_id == user_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    # Create new conversation
    conv = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        scope=ContentScope.PROJECT.value,
        project_id=project_id,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _run_project_llm_producer(
    queue: asyncio.Queue,
    *,
    request_message: str,
    tenant_id: UUID,
    project_id: UUID,
    system_prompt: str | None,
    history: list[dict],
    conversation_ref_id: UUID,
    user_message_id: UUID,
):
    """Streaming LLM producer for project chat (project scope ONLY)."""
    logger.info("project_chat_started", extra={
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "conversation_ref_id": str(conversation_ref_id),
    })
    full_response = ""
    citations_for_db: list = []
    blocks_for_db: list = []
    tokens_input = 0
    tokens_output = 0

    try:
        async with async_session_maker() as retrieval_db:
            # STRICT: only project scope — no org, no personal
            async for event in chat_service.chat_stream(
                message=request_message,
                tenant_id=tenant_id,
                collection_ids=[],       # Empty explicitly
                system_prompt=system_prompt,
                conversation_history=history,
                db=retrieval_db,
                dossier_ids=None,        # Null explicitly
                project_ids=[project_id],  # Only project scope
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
        logger.error("project_chat_error", extra={
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
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
                    logger.info("project_chat_completed", extra={
                        "tenant_id": str(tenant_id),
                        "project_id": str(project_id),
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                    })
            except Exception as save_err:
                logger.error("project_chat_save_error", extra={
                    "tenant_id": str(tenant_id),
                    "project_id": str(project_id),
                    "error": str(save_err),
                })
                await queue.put(("error", "Failed to save message"))

        await queue.put(_STREAM_END)


@router.post("/{project_id}/chat/stream")
async def project_chat_stream(
    project_id: UUID,
    request: ProjectChatRequest,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> StreamingResponse:
    """Chat within a project (SSE streaming).

    RAG scope: only the project's documents and knowledge.
    """
    await _get_project(project_id, user.id, user.tenant_id, db)
    tenant_id = user.tenant_id

    # Quota check
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
    await quota_service.record_chat_request(db, user.id)

    # Get or create conversation
    conv = await _get_or_create_project_conversation(
        db,
        conversation_id=request.conversation_id,
        project_id=project_id,
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
        _run_project_llm_producer(
            queue,
            request_message=request.message,
            tenant_id=tenant_id,
            project_id=project_id,
            system_prompt=PROJECT_SYSTEM_PROMPT,
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


# ---------------------------------------------------------------------------
# Project Conversations
# ---------------------------------------------------------------------------


@router.get("/{project_id}/conversations")
async def list_project_conversations(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """List conversations in a project."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    result = await db.execute(
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .where(Conversation.user_id == user.id)
        .where(Conversation.scope == ContentScope.PROJECT.value)
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


@router.get("/{project_id}/conversations/{conversation_id}")
async def get_project_conversation(
    project_id: UUID,
    conversation_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """Get messages for a project conversation."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    # Verify conversation belongs to this project + user
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.project_id == project_id)
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


# ---------------------------------------------------------------------------
# Project Knowledge (conversation summaries)
# ---------------------------------------------------------------------------


@router.post("/{project_id}/summarize")
async def summarize_project_conversation(
    project_id: UUID,
    request: ProjectSummarizeRequest,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> dict:
    """Summarize a conversation and index it as project knowledge.

    Enqueues an async worker task.
    """
    await _get_project(project_id, user.id, user.tenant_id, db)

    # Verify conversation belongs to this project + user
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == request.conversation_id)
        .where(Conversation.project_id == project_id)
        .where(Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Queue summarization job
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "summarize_project_conversation",
        str(project_id),
        str(request.conversation_id),
    )
    await pool.close()

    return {"message": "Summarization queued", "conversation_id": str(request.conversation_id)}


@router.get("/{project_id}/knowledge", response_model=list[ProjectKnowledgeRead])
async def list_project_knowledge(
    project_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[ProjectKnowledge]:
    """List knowledge entries for a project."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    result = await db.execute(
        select(ProjectKnowledge)
        .where(ProjectKnowledge.project_id == project_id)
        .where(ProjectKnowledge.user_id == user.id)
        .order_by(ProjectKnowledge.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete(
    "/{project_id}/knowledge/{knowledge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_knowledge(
    project_id: UUID,
    knowledge_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> None:
    """Delete a knowledge entry and its chunks. Qdrant FIRST, then DB."""
    await _get_project(project_id, user.id, user.tenant_id, db)

    result = await db.execute(
        select(ProjectKnowledge)
        .where(ProjectKnowledge.id == knowledge_id)
        .where(ProjectKnowledge.project_id == project_id)
        .where(ProjectKnowledge.user_id == user.id)
    )
    knowledge = result.scalar_one_or_none()
    if not knowledge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge entry not found",
        )

    # 1. Delete knowledge chunks from Qdrant (by source_id)
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    await vector_store.client.delete(
        collection_name=vector_store.collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=str(user.tenant_id))),
                FieldCondition(key="scope", match=MatchValue(value="project")),
                FieldCondition(key="source_id", match=MatchValue(value=str(knowledge_id))),
            ]
        ),
    )

    # 2. Delete chunks from DB
    from sqlalchemy import delete as sa_delete

    await db.execute(
        sa_delete(Chunk)
        .where(Chunk.source_id == knowledge_id)
        .where(Chunk.scope == "project")
        .where(Chunk.tenant_id == user.tenant_id)
    )

    # 3. Delete knowledge entry
    await db.delete(knowledge)
    await db.commit()
