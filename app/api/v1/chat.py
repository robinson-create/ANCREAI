"""Chat endpoints with SSE streaming."""

import asyncio
import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.deps import CurrentUser, DbSession
from app.models.assistant import Assistant
from app.models.message import Message, MessageRole
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import chat_service
from app.services.usage import usage_service
from app.services.quota import quota_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Sentinel to signal the SSE consumer that the producer is done
_STREAM_END = object()


async def format_sse(event: str, data: str) -> str:
    """Format SSE message.

    Per the SSE spec, multi-line data must use separate 'data:' lines.
    The client reassembles them by joining with newlines.
    """
    lines = data.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


async def _run_llm_producer(
    queue: asyncio.Queue,
    *,
    request_message: str,
    tenant_id: UUID,
    collection_ids: list[UUID],
    system_prompt: str | None,
    history: list[dict],
    integrations_data: list[dict] | None,
    assistant_id: UUID,
    conversation_id: UUID,
    user_message_id: UUID,
):
    """Consume chat_service.chat_stream(), push events to queue, and save to DB.

    Runs as an independent asyncio.Task so that client disconnects (which only
    tear down the SSE generator) do not prevent the LLM call from completing or
    the result from being persisted.
    """
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
                collection_ids=collection_ids,
                system_prompt=system_prompt,
                conversation_history=history,
                integrations=integrations_data,
                db=retrieval_db,
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
                        else {k: str(v) if isinstance(v, UUID) else v for k, v in c.items()} if isinstance(c, dict)
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
        logger.error("LLM producer error: %s", e)
        await queue.put(("error", str(e)))

    finally:
        # Always save assistant message, even if client disconnected
        if full_response or blocks_for_db:
            try:
                async with async_session_maker() as save_db:
                    await save_db.execute(
                        update(Message)
                        .where(Message.id == user_message_id)
                        .values(tokens_input=tokens_input)
                    )
                    assistant_message = Message(
                        assistant_id=assistant_id,
                        conversation_id=conversation_id,
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
                    logger.info(
                        "Saved assistant message for conversation %s (%d chars)",
                        conversation_id,
                        len(full_response),
                    )
            except Exception as save_err:
                logger.error("Failed to save assistant message: %s", save_err)

        # Signal the consumer that we are done
        await queue.put(_STREAM_END)


@router.post("/{assistant_id}", response_model=ChatResponse)
async def chat(
    assistant_id: UUID,
    request: ChatRequest,
    user: CurrentUser,
    db: DbSession,
) -> ChatResponse:
    """Chat with an assistant (non-streaming)."""
    tenant_id = user.tenant_id
    
    # Get assistant with collections and integrations
    result = await db.execute(
        select(Assistant)
        .options(
            selectinload(Assistant.collections),
            selectinload(Assistant.integrations),
        )
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == tenant_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    if not assistant.collections and not assistant.integrations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'assistant n'a ni collections ni outils connectés.",
        )

    collection_ids = [c.id for c in assistant.collections]
    conversation_id = request.conversation_id or uuid4()

    # Build integrations list for the chat service
    integrations_data = [
        {"provider": i.provider, "nango_connection_id": i.nango_connection_id}
        for i in assistant.integrations
        if i.status == "connected"
    ]

    # Check chat quota (free tier limit)
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )

    # Get conversation history if requested
    history = []
    if request.include_history and request.conversation_id:
        result = await db.execute(
            select(Message)
            .where(Message.assistant_id == assistant_id)
            .where(Message.conversation_id == request.conversation_id)
            .order_by(Message.created_at.desc())
            .limit(request.max_history_messages)
        )
        messages = list(reversed(result.scalars().all()))
        history = [{"role": m.role, "content": m.content} for m in messages]

    # Call chat service (pass db for hybrid search)
    response_text, citations, blocks, tokens_input, tokens_output = await chat_service.chat(
        message=request.message,
        tenant_id=tenant_id,
        collection_ids=collection_ids,
        system_prompt=assistant.system_prompt,
        conversation_history=history,
        integrations=integrations_data or None,
        db=db,
    )

    # Save user message
    user_message = Message(
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        role=MessageRole.USER.value,
        content=request.message,
        tokens_input=tokens_input,
    )
    db.add(user_message)

    # Save assistant message
    assistant_message = Message(
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT.value,
        content=response_text,
        citations=[c.model_dump() for c in citations],
        blocks=blocks or None,
        tokens_output=tokens_output,
    )
    db.add(assistant_message)

    # Record usage (both quota tracking and usage tracking)
    await quota_service.record_chat_request(db, user.id)
    await usage_service.record_chat(db, tenant_id, tokens_input, tokens_output)

    await db.commit()

    return ChatResponse(
        message=response_text,
        conversation_id=conversation_id,
        citations=citations,
        blocks=blocks,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )


@router.post("/{assistant_id}/stream")
async def chat_stream(
    assistant_id: UUID,
    request: ChatRequest,
    user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Chat with an assistant (SSE streaming)."""
    tenant_id = user.tenant_id
    user_id = user.id
    
    # Get assistant with collections and integrations
    result = await db.execute(
        select(Assistant)
        .options(
            selectinload(Assistant.collections),
            selectinload(Assistant.integrations),
        )
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == tenant_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    if not assistant.collections and not assistant.integrations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'assistant n'a ni collections ni outils connectés.",
        )

    collection_ids = [c.id for c in assistant.collections]
    conversation_id = request.conversation_id or uuid4()

    # Build integrations list for the chat service
    integrations_data = [
        {"provider": i.provider, "nango_connection_id": i.nango_connection_id}
        for i in assistant.integrations
        if i.status == "connected"
    ]

    # Check chat quota (free tier limit)
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )

    # Record quota usage immediately (before streaming)
    await quota_service.record_chat_request(db, user_id)

    # Get conversation history if requested
    history = []
    if request.include_history and request.conversation_id:
        result = await db.execute(
            select(Message)
            .where(Message.assistant_id == assistant_id)
            .where(Message.conversation_id == request.conversation_id)
            .order_by(Message.created_at.desc())
            .limit(request.max_history_messages)
        )
        messages = list(reversed(result.scalars().all()))
        history = [{"role": m.role, "content": m.content} for m in messages]

    # Save user message BEFORE streaming so conversation appears in list immediately
    async with async_session_maker() as save_db:
        user_message = Message(
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            role=MessageRole.USER.value,
            content=request.message,
            tokens_input=0,  # Will be updated after streaming
        )
        save_db.add(user_message)
        await save_db.commit()
        user_message_id = user_message.id

    # --- Task + Queue: decouple LLM generation from SSE delivery ---
    # The producer task runs independently so that client disconnects
    # (which only tear down the SSE generator) cannot prevent the LLM
    # call from completing or the result from being saved to DB.
    queue: asyncio.Queue = asyncio.Queue()

    producer_task = asyncio.create_task(
        _run_llm_producer(
            queue,
            request_message=request.message,
            tenant_id=tenant_id,
            collection_ids=collection_ids,
            system_prompt=assistant.system_prompt,
            history=history,
            integrations_data=integrations_data or None,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
        )
    )
    # Suppress "Task exception was never retrieved" warnings
    producer_task.add_done_callback(
        lambda t: t.exception() if not t.cancelled() else None
    )

    async def event_generator():
        """Read events from the producer queue and yield SSE strings."""
        yield await format_sse("conversation_id", str(conversation_id))

        while True:
            item = await queue.get()
            if item is _STREAM_END:
                break

            event_type, event_data = item

            if event_type == "token":
                yield await format_sse("token", event_data)
            elif event_type == "block":
                yield await format_sse("block", json.dumps(event_data))
            elif event_type == "citations":
                yield await format_sse("citations", json.dumps(event_data))
            elif event_type == "done":
                yield await format_sse("done", json.dumps(event_data))
            elif event_type == "error":
                yield await format_sse("error", event_data)
            else:
                yield await format_sse(
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


@router.get("/{assistant_id}/conversations")
async def list_conversations(
    assistant_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """List all conversations for an assistant."""
    from sqlalchemy import func, distinct
    
    # Verify assistant belongs to user's tenant
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )
    
    # Get distinct conversation IDs with first message and timestamp
    # Using a subquery to get conversation metadata
    result = await db.execute(
        select(
            Message.conversation_id,
            func.min(Message.created_at).label("started_at"),
            func.max(Message.created_at).label("last_message_at"),
            func.count(Message.id).label("message_count"),
        )
        .where(Message.assistant_id == assistant_id)
        .group_by(Message.conversation_id)
        .order_by(func.max(Message.created_at).desc())
        .limit(50)
    )
    conversations = result.all()
    
    # Get first user message for each conversation to use as title
    conversation_list = []
    for conv in conversations:
        # Get first user message as title
        first_msg_result = await db.execute(
            select(Message.content)
            .where(Message.conversation_id == conv.conversation_id)
            .where(Message.role == "user")
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        first_msg = first_msg_result.scalar_one_or_none()
        title = first_msg[:50] + "..." if first_msg and len(first_msg) > 50 else first_msg or "Conversation"
        
        conversation_list.append({
            "id": str(conv.conversation_id),
            "title": title,
            "started_at": conv.started_at.isoformat(),
            "last_message_at": conv.last_message_at.isoformat(),
            "message_count": conv.message_count,
        })
    
    return conversation_list


@router.get("/{assistant_id}/conversations/{conversation_id}")
async def get_conversation(
    assistant_id: UUID,
    conversation_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """Get conversation history."""
    # Verify assistant belongs to user's tenant
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )
    
    result = await db.execute(
        select(Message)
        .where(Message.assistant_id == assistant_id)
        .where(Message.conversation_id == conversation_id)
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
