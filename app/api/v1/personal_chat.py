"""Personal global chat — search across ALL of a user's personal content.

RAG scope: every personal dossier + every project owned by the user.
No assistant_id, no dossier_id, no project_id needed.
"""

import asyncio
import json
import logging
from uuid import UUID

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.database import async_session_maker
from app.deps import CurrentMember, CurrentUser, DbSession
from app.models.conversation import Conversation
from app.models.enums import ContentScope
from app.models.message import Message, MessageRole
from app.services.chat import chat_service
from app.services.usage import usage_service
from app.services.quota import quota_service
from app.workers.settings import redis_settings

logger = logging.getLogger(__name__)

router = APIRouter()

_STREAM_END = object()

# Trigger memory extraction every N messages in a conversation
MEMORY_EXTRACTION_INTERVAL = 10

PERSONAL_GLOBAL_SYSTEM_PROMPT = (
    "Tu es un assistant personnel. Tu aides l'utilisateur en t'appuyant "
    "sur l'ensemble de ses documents personnels (dossiers et projets). "
    "Réponds de manière claire, concise et structurée. Si tu ne trouves pas "
    "l'information dans les documents fournis, dis-le honnêtement."
)


class PersonalChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    include_history: bool = True
    max_history_messages: int = 10


async def _format_sse(event: str, data: str) -> str:
    lines = data.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


async def _get_or_create_personal_global_conversation(
    db,
    *,
    conversation_id: UUID | None,
    tenant_id: UUID,
    user_id: UUID,
) -> Conversation:
    """Get existing or create new personal global conversation."""
    if conversation_id:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
            .where(Conversation.scope == ContentScope.PERSONAL.value)
            .where(Conversation.dossier_id.is_(None))
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        scope=ContentScope.PERSONAL.value,
        # dossier_id=None → global personal chat
        # assistant_id=None, project_id=None → CHECK constraint OK
    )
    db.add(conv)
    await db.flush()
    return conv


async def _run_personal_global_llm_producer(
    queue: asyncio.Queue,
    *,
    request_message: str,
    tenant_id: UUID,
    user_id: UUID,
    system_prompt: str | None,
    history: list[dict],
    conversation_ref_id: UUID,
    user_message_id: UUID,
):
    """Streaming LLM producer for personal global chat."""
    logger.info("personal_global_chat_started", extra={
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
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
                dossier_ids=None,
                project_ids=None,
                user_id=user_id,
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
        logger.error("personal_global_chat_error", extra={
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
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

                    # Check if we should trigger memory extraction
                    msg_count_result = await save_db.execute(
                        select(func.count(Message.id))
                        .where(Message.conversation_ref_id == conversation_ref_id)
                    )
                    msg_count = msg_count_result.scalar_one() or 0
                    if msg_count > 0 and msg_count % MEMORY_EXTRACTION_INTERVAL == 0:
                        try:
                            pool: ArqRedis = await create_pool(redis_settings)
                            await pool.enqueue_job(
                                "extract_conversation_memory",
                                str(conversation_ref_id),
                                str(tenant_id),
                                str(user_id),
                            )
                            await pool.close()
                            logger.info("memory_extraction_enqueued", extra={
                                "conversation_id": str(conversation_ref_id),
                                "message_count": msg_count,
                            })
                        except Exception as enqueue_err:
                            logger.warning("memory_extraction_enqueue_failed", extra={
                                "error": str(enqueue_err),
                            })

                    logger.info("personal_global_chat_completed", extra={
                        "tenant_id": str(tenant_id),
                        "user_id": str(user_id),
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                    })
            except Exception as save_err:
                logger.error("personal_global_chat_save_error", extra={
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "error": str(save_err),
                })
                await queue.put(("error", "Failed to save message"))

        await queue.put(_STREAM_END)


@router.post("/stream")
async def personal_global_chat_stream(
    request: PersonalChatRequest,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> StreamingResponse:
    """Chat across ALL personal content (dossiers + projects).

    RAG scope: everything owned by the authenticated user.
    No assistant_id, no dossier_id, no project_id needed.
    """
    tenant_id = user.tenant_id

    # Quota check
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
    await quota_service.record_chat_request(db, user.id)

    # Get or create conversation
    conv = await _get_or_create_personal_global_conversation(
        db,
        conversation_id=request.conversation_id,
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

    await db.commit()

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
        _run_personal_global_llm_producer(
            queue,
            request_message=request.message,
            tenant_id=tenant_id,
            user_id=user.id,
            system_prompt=PERSONAL_GLOBAL_SYSTEM_PROMPT,
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
# Conversations listing
# ---------------------------------------------------------------------------


@router.get("/conversations")
async def list_personal_global_conversations(
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """List personal global conversations (scope=personal, dossier_id=NULL)."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .where(Conversation.tenant_id == user.tenant_id)
        .where(Conversation.scope == ContentScope.PERSONAL.value)
        .where(Conversation.dossier_id.is_(None))
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
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


@router.get("/conversations/{conversation_id}")
async def get_personal_global_conversation(
    conversation_id: UUID,
    user: CurrentUser,
    _member: CurrentMember,
    db: DbSession,
) -> list[dict]:
    """Get messages for a personal global conversation."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == user.id)
        .where(Conversation.scope == ContentScope.PERSONAL.value)
        .where(Conversation.dossier_id.is_(None))
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
