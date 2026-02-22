"""Agent-first chat endpoint — creates a run, enqueues to worker, streams via Redis."""

import json
from uuid import UUID, uuid4

from arq.connections import create_pool
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.budget import default_budget_for_profile
from app.core.logging import get_logger
from app.core.streams import AgentStreamConsumer, get_redis
from app.database import async_session_maker
from app.deps import CurrentUser, DbSession
from app.models.assistant import Assistant
from app.models.message import Message, MessageRole
from app.schemas.chat import ChatRequest
from app.services.quota import quota_service
from app.services.run import run_service
from app.workers.settings import redis_settings

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


async def _format_sse(event: str, data: str) -> str:
    """Format SSE message with multi-line support."""
    lines = data.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


@router.post("/{assistant_id}/agent-stream")
async def agent_stream(
    assistant_id: UUID,
    request: ChatRequest,
    user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Chat with an assistant via the agent runtime (SSE streaming).

    Flow:
    1. Validate request, load assistant
    2. Save user message
    3. Create agent_run in DB
    4. Enqueue run_agent Arq job
    5. Return SSE that reads from Redis Streams
    """
    tenant_id = user.tenant_id
    user_id = user.id

    # ── Load assistant ───────────────────────────────────────────
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

    # ── Quota check ──────────────────────────────────────────────
    allowed, error = await quota_service.check_chat_allowed(db, user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )
    await quota_service.record_chat_request(db, user_id)

    conversation_id = request.conversation_id or uuid4()

    # ── Save user message ────────────────────────────────────────
    async with async_session_maker() as save_db:
        user_message = Message(
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            role=MessageRole.USER.value,
            content=request.message,
            tokens_input=0,
        )
        save_db.add(user_message)
        await save_db.commit()

    # ── Create agent run ─────────────────────────────────────────
    profile = assistant.agent_profile or "reactive"

    async with async_session_maker() as run_db:
        run = await run_service.create_run(
            run_db,
            tenant_id=tenant_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            input_text=request.message,
            profile=profile,
            budget_tokens=default_budget_for_profile(profile),
            metadata_={"user_id": str(user_id)},
        )
        run_id = run.id

        await run_service.log_audit(
            run_db,
            action="run_created",
            tenant_id=tenant_id,
            run_id=run_id,
            user_id=user_id,
            entity_type="assistant",
            entity_id=assistant_id,
            detail={"profile": profile, "conversation_id": str(conversation_id)},
        )
        await run_db.commit()

    # ── Enqueue worker job ───────────────────────────────────────
    pool = await create_pool(redis_settings)
    try:
        await pool.enqueue_job("run_agent", str(run_id))
    finally:
        await pool.aclose()

    logger.info(
        "agent_run_enqueued",
        run_id=str(run_id),
        assistant_id=str(assistant_id),
        profile=profile,
    )

    # ── SSE generator (reads from Redis Streams) ─────────────────
    redis = await get_redis()

    async def event_generator():
        # Emit run metadata first
        yield await _format_sse("conversation_id", str(conversation_id))
        yield await _format_sse("run_id", str(run_id))

        consumer = AgentStreamConsumer(
            redis,
            run_id,
            heartbeat_interval=settings.agent_sse_heartbeat_interval,
            hard_timeout=settings.agent_sse_hard_timeout,
        )

        seen_seqs: set[str] = set()

        async for raw_event in consumer:
            seq = raw_event.get("seq", "")
            event_type = raw_event.get("type", "")

            # Idempotence: skip already-seen events (reconnect scenario)
            if seq in seen_seqs and seq != "-1":
                continue
            seen_seqs.add(seq)

            # Parse data payload
            data_str = raw_event.get("data", "{}")
            try:
                data = json.loads(data_str)
            except (json.JSONDecodeError, TypeError):
                data = {"raw": data_str}

            # Map stream event types to SSE events
            if event_type == "status":
                yield await _format_sse("status", json.dumps(data))

            elif event_type == "delta":
                text = data.get("text", "")
                yield await _format_sse("token", text)

            elif event_type == "block":
                yield await _format_sse("block", json.dumps(data))

            elif event_type == "citations":
                yield await _format_sse("citations", json.dumps(data.get("citations", [])))

            elif event_type == "tool":
                yield await _format_sse("tool", json.dumps(data))

            elif event_type == "done":
                yield await _format_sse("done", json.dumps(data))
                return

            elif event_type == "error":
                yield await _format_sse("error", json.dumps(data))
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
