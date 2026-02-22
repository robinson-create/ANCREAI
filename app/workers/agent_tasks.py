"""Agent worker tasks — processes agent runs via Redis Streams.

Dispatches between:
- Reactive profile: short path via chat_service.chat_stream()
- Balanced/pro/exec: planner + multi-turn agent loop
"""

from __future__ import annotations

import time
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.budget import BudgetManager, default_budget_for_profile
from app.core.logging import get_logger, run_id_var, tenant_id_var
from app.core.streams import AgentStreamPublisher
from app.core.tool_registry import tool_registry
from app.database import async_session_maker
from app.models.assistant import Assistant
from app.models.message import Message, MessageRole
from app.services.chat import chat_service
from app.services.run import run_service
from app.services.usage import usage_service

settings = get_settings()
logger = get_logger(__name__)


async def _get_stream_redis(ctx: dict) -> aioredis.Redis:
    """Get or create a redis.asyncio client for streams (separate from Arq's pool)."""
    if "stream_redis" not in ctx:
        ctx["stream_redis"] = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,
        )
    return ctx["stream_redis"]


async def run_agent(ctx: dict, run_id: str) -> dict:
    """Arq task: execute an agent run and publish events to Redis Streams.

    Dispatches between:
    - Reactive: short path via chat_service.chat_stream()
    - Balanced/pro/exec: planner + multi-turn agent loop
    """
    run_uuid = UUID(run_id)

    # Bind context vars for structured logging
    run_id_var.set(run_id)

    redis = await _get_stream_redis(ctx)
    pub = AgentStreamPublisher(redis, run_uuid)
    await pub.setup(ttl=settings.agent_stream_ttl, maxlen=settings.agent_stream_maxlen)

    async with async_session_maker() as db:
        try:
            # ── Load run ────────────────────────────────────────
            run = await run_service.get_run(db, run_uuid)
            if not run:
                await pub.emit_error("run_not_found", f"Run {run_id} not found")
                return {"status": "error", "code": "run_not_found"}

            tenant_id_var.set(str(run.tenant_id))

            # Transition to RUNNING
            await run_service.start_run(db, run_uuid)
            await db.commit()
            await pub.emit_status("starting")

            # ── Load assistant ──────────────────────────────────
            result = await db.execute(
                select(Assistant)
                .options(
                    selectinload(Assistant.collections),
                    selectinload(Assistant.integrations),
                )
                .where(Assistant.id == run.assistant_id)
                .where(Assistant.tenant_id == run.tenant_id)
            )
            assistant = result.scalar_one_or_none()
            if not assistant:
                await _fail_run(db, pub, run_uuid, "assistant_not_found", "Assistant not found")
                return {"status": "error", "code": "assistant_not_found"}

            collection_ids = [c.id for c in assistant.collections]

            # ── Initialize budget manager ─────────────────────────
            profile = run.profile or "reactive"
            budget_total = run.budget_tokens or default_budget_for_profile(profile)
            budget = BudgetManager(total=budget_total)

            # ── Resolve allowed tools for this run ────────────────
            connected_providers = [
                i.provider for i in assistant.integrations
                if i.status == "connected"
            ] or None

            allowed_tools = tool_registry.get_allowed_tools(
                profile=profile,
                providers=connected_providers,
            )

            logger.info(
                "agent_run_tools_resolved",
                run_id=run_id,
                profile=profile,
                budget_total=budget_total,
                tool_count=len(allowed_tools),
                tool_names=[t.name for t in allowed_tools],
            )

            # ── Load conversation history ───────────────────────
            history_result = await db.execute(
                select(Message)
                .where(Message.assistant_id == run.assistant_id)
                .where(Message.conversation_id == run.conversation_id)
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            history = [
                {"role": m.role, "content": m.content}
                for m in reversed(history_result.scalars().all())
            ]

            # ── Build integrations data ─────────────────────────
            integrations_data = [
                {"provider": i.provider, "nango_connection_id": i.nango_connection_id}
                for i in assistant.integrations
                if i.status == "connected"
            ] or None

            # ── Dispatch by profile ────────────────────────────
            from app.core.planner import needs_planning

            if needs_planning(profile):
                return await _run_orchestrated(
                    db=db,
                    pub=pub,
                    run=run,
                    run_uuid=run_uuid,
                    run_id=run_id,
                    assistant=assistant,
                    profile=profile,
                    budget=budget,
                    collection_ids=collection_ids,
                    history=history,
                    integrations_data=integrations_data,
                    allowed_tools=allowed_tools,
                )

            return await _run_reactive(
                db=db,
                pub=pub,
                run=run,
                run_uuid=run_uuid,
                run_id=run_id,
                assistant=assistant,
                profile=profile,
                budget=budget,
                collection_ids=collection_ids,
                history=history,
                integrations_data=integrations_data,
            )

        except Exception as e:
            logger.exception("agent_run_failed", run_id=run_id, error=str(e))
            await _fail_run(db, pub, run_uuid, "worker_exception", str(e))
            return {"status": "error", "code": "worker_exception", "message": str(e)}


async def _run_reactive(
    *,
    db: AsyncSession,
    pub: AgentStreamPublisher,
    run,
    run_uuid: UUID,
    run_id: str,
    assistant,
    profile: str,
    budget: BudgetManager,
    collection_ids: list,
    history: list[dict],
    integrations_data: list[dict] | None,
) -> dict:
    """Reactive profile: short path via chat_service.chat_stream()."""
    await pub.emit_status("searching")

    full_response = ""
    citations_for_db: list = []
    blocks_for_db: list = []
    tokens_input = 0
    tokens_output = 0
    delta_buffer = ""
    last_flush_time = time.time()

    async with async_session_maker() as retrieval_db:
        async for event in chat_service.chat_stream(
            message=run.input_text,
            tenant_id=run.tenant_id,
            collection_ids=collection_ids,
            system_prompt=assistant.system_prompt,
            conversation_history=history,
            integrations=integrations_data,
            db=retrieval_db,
            conversation_id=run.conversation_id,
        ):
            if event.event == "start":
                await pub.emit_status("analyzing")

            elif event.event == "token":
                full_response += event.data
                delta_buffer += event.data
                now = time.time()
                if (now - last_flush_time) * 1000 >= settings.agent_delta_batch_ms:
                    await pub.emit_delta(delta_buffer)
                    delta_buffer = ""
                    last_flush_time = now

            elif event.event == "block":
                blocks_for_db.append(event.data)
                block_type = event.data.get("type", "unknown") if isinstance(event.data, dict) else "unknown"
                await pub.emit_tool({"tool": block_type, "status": "completed"})
                await pub.emit_block(event.data)

            elif event.event == "citations":
                from uuid import UUID as _UUID
                citations_for_db = [
                    c.model_dump(mode="json") if hasattr(c, "model_dump")
                    else {k: str(v) if isinstance(v, _UUID) else v for k, v in c.items()}
                    if isinstance(c, dict) else c
                    for c in event.data
                ]
                await pub.emit_citations(citations_for_db)

            elif event.event == "done":
                tokens_input = event.data.get("tokens_input", 0)
                tokens_output = event.data.get("tokens_output", 0)

            elif event.event == "error":
                await pub.emit_error("llm_error", str(event.data))

    # Flush remaining delta buffer
    if delta_buffer:
        await pub.emit_delta(delta_buffer)

    # Source coverage heuristic for reactive
    from app.core.source_coverage import check_source_coverage_heuristic

    coverage = check_source_coverage_heuristic(full_response, len(citations_for_db))
    if coverage.needs_disclaimer and coverage.disclaimer:
        full_response += coverage.disclaimer
        await pub.emit_delta(coverage.disclaimer)

    # Track budget
    budget.consume_safe(tokens_input + tokens_output)

    return await _finalize_run(
        db=db,
        pub=pub,
        run=run,
        run_uuid=run_uuid,
        run_id=run_id,
        profile=profile,
        budget=budget,
        full_response=full_response,
        citations_for_db=citations_for_db,
        blocks_for_db=blocks_for_db,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )


async def _run_orchestrated(
    *,
    db: AsyncSession,
    pub: AgentStreamPublisher,
    run,
    run_uuid: UUID,
    run_id: str,
    assistant,
    profile: str,
    budget: BudgetManager,
    collection_ids: list,
    history: list[dict],
    integrations_data: list[dict] | None,
    allowed_tools: list,
) -> dict:
    """Balanced/pro/exec: planner + multi-turn agent loop."""
    from app.core.agent_loop import AgentContext, run_agent_loop
    from app.core.planner import generate_plan
    from app.core.source_coverage import analyze_source_coverage

    # ── Planning phase ───────────────────────────────────────
    await pub.emit_status("planning")

    plan = await generate_plan(
        message=run.input_text,
        profile=profile,
        available_tools=[t.name for t in allowed_tools],
    )

    logger.info(
        "agent_plan_generated",
        run_id=run_id,
        profile=profile,
        step_count=len(plan.steps),
    )

    # ── Build user context for calendar tools ─────────────────
    user_context = {"tenant_id": str(run.tenant_id)}
    if run.metadata_ and isinstance(run.metadata_, dict):
        user_id = run.metadata_.get("user_id")
        if user_id:
            user_context["user_id"] = user_id

    # ── Agent loop ───────────────────────────────────────────
    agent_ctx = AgentContext(
        tenant_id=run.tenant_id,
        assistant_id=run.assistant_id,
        conversation_id=run.conversation_id,
        message=run.input_text,
        system_prompt=assistant.system_prompt or "",
        conversation_history=history,
        collection_ids=collection_ids if collection_ids else None,
        integrations=integrations_data,
        profile=profile,
        budget=budget,
        plan=plan,
        allowed_tools=allowed_tools,
        user_context=user_context,
    )

    full_response = ""
    citations_for_db: list = []
    blocks_for_db: list = []
    tokens_input = 0
    tokens_output = 0
    delta_buffer = ""
    last_flush_time = time.time()

    async for event in run_agent_loop(agent_ctx):
        if event.event == "status":
            await pub.emit_status(event.data)

        elif event.event == "token":
            full_response += event.data
            delta_buffer += event.data
            now = time.time()
            if (now - last_flush_time) * 1000 >= settings.agent_delta_batch_ms:
                await pub.emit_delta(delta_buffer)
                delta_buffer = ""
                last_flush_time = now

        elif event.event == "block":
            blocks_for_db.append(event.data)
            await pub.emit_block(event.data)

        elif event.event == "citations":
            citations_for_db = event.data if isinstance(event.data, list) else []
            await pub.emit_citations(citations_for_db)

        elif event.event == "tool":
            await pub.emit_tool(event.data)

        elif event.event == "plan":
            await pub.emit_tool({"tool": "planner", "status": "completed", "plan": event.data})

        elif event.event == "done":
            if isinstance(event.data, dict):
                tokens_input = event.data.get("tokens_input", 0)
                tokens_output = event.data.get("tokens_output", 0)

        elif event.event == "error":
            await pub.emit_error("agent_loop_error", str(event.data))

    # Flush remaining deltas
    if delta_buffer:
        await pub.emit_delta(delta_buffer)

    # ── Source coverage (explicit step for balanced/pro/exec) ──
    coverage = analyze_source_coverage(full_response, citations_for_db)
    if coverage.needs_disclaimer and coverage.disclaimer:
        full_response += coverage.disclaimer
        await pub.emit_delta(coverage.disclaimer)

    return await _finalize_run(
        db=db,
        pub=pub,
        run=run,
        run_uuid=run_uuid,
        run_id=run_id,
        profile=profile,
        budget=budget,
        full_response=full_response,
        citations_for_db=citations_for_db,
        blocks_for_db=blocks_for_db,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )


async def _finalize_run(
    *,
    db: AsyncSession,
    pub: AgentStreamPublisher,
    run,
    run_uuid: UUID,
    run_id: str,
    profile: str,
    budget: BudgetManager,
    full_response: str,
    citations_for_db: list,
    blocks_for_db: list,
    tokens_input: int,
    tokens_output: int,
) -> dict:
    """Save message, complete run, record trace, emit done — shared by both paths."""
    assistant_message = Message(
        assistant_id=run.assistant_id,
        conversation_id=run.conversation_id,
        role=MessageRole.ASSISTANT.value,
        content=full_response,
        citations=citations_for_db or None,
        blocks=blocks_for_db or None,
        tokens_output=tokens_output,
    )
    db.add(assistant_message)
    await usage_service.record_chat(db, run.tenant_id, tokens_input, tokens_output)

    await run_service.complete_run(
        db,
        run_uuid,
        output_text=full_response,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        budget_tokens_remaining=budget.remaining,
    )

    await run_service.record_llm_trace(
        db,
        model=settings.llm_model,
        provider="mistral",
        prompt_tokens=tokens_input,
        completion_tokens=tokens_output,
        tenant_id=run.tenant_id,
        run_id=run_uuid,
    )

    await db.commit()

    await pub.emit_done(
        tokens_input=tokens_input,
        tokens_output=tokens_output,
    )

    logger.info(
        "agent_run_completed",
        run_id=run_id,
        profile=profile,
        tokens_in=tokens_input,
        tokens_out=tokens_output,
        response_len=len(full_response),
        budget_remaining=budget.remaining,
    )

    return {
        "status": "completed",
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
    }


async def _fail_run(
    db: AsyncSession,
    pub: AgentStreamPublisher,
    run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    """Mark run as failed in DB and emit error event."""
    try:
        await run_service.fail_run(db, run_id, error_code=error_code, error_message=error_message)
        await db.commit()
    except Exception:
        logger.exception("failed_to_update_run_status", run_id=str(run_id))
    await pub.emit_error(error_code, error_message)


# ── Arq hooks for crash recovery ─────────────────────────────────────


async def on_agent_job_abort(ctx: dict, job: dict) -> None:
    """Called when an agent job is aborted (e.g. worker shutdown, timeout)."""
    run_id = job.get("args", [None])[0]
    if not run_id:
        return

    logger.warning("agent_job_aborted", run_id=run_id)

    redis = await _get_stream_redis(ctx)
    pub = AgentStreamPublisher(redis, run_id)

    async with async_session_maker() as db:
        await _fail_run(
            db, pub, UUID(run_id),
            error_code="worker_aborted",
            error_message="Agent job was aborted (worker shutdown or timeout)",
        )


# ── Watchdog for stuck runs ──────────────────────────────────────────


async def watchdog_stuck_runs(ctx: dict) -> int:
    """Cron task: detect and timeout runs stuck in RUNNING state.

    Returns the number of runs timed out.
    """
    from datetime import UTC, datetime, timedelta

    threshold = datetime.now(UTC) - timedelta(seconds=settings.agent_stuck_run_threshold)
    timed_out = 0

    async with async_session_maker() as db:
        stuck_runs = await run_service.find_stuck_runs(db, running_since_before=threshold)

        for run in stuck_runs:
            logger.warning("watchdog_timeout_run", run_id=str(run.id), started_at=str(run.started_at))

            redis = await _get_stream_redis(ctx)
            pub = AgentStreamPublisher(redis, run.id)
            await _fail_run(
                db, pub, run.id,
                error_code="watchdog_timeout",
                error_message=f"Run stuck since {run.started_at}",
            )
            timed_out += 1

        if timed_out:
            await db.commit()

    return timed_out
