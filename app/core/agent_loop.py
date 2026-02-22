"""Agent loop — multi-turn tool calling for balanced/pro/exec profiles.

The agent loop replaces chat_service.chat_stream() for non-reactive profiles.
It manages:
- LLM calls with tool schemas from the registry
- Tool call accumulation from streaming chunks
- Tool execution via the tool executor
- Budget tracking per round
- Plan step progression
- Block/citation/delta emission via callback

The reactive profile continues to use chat_service.chat_stream() directly.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.budget import BudgetManager
from app.core.logging import get_logger
from app.core.planner import AgentPlan, PlanStepStatus, max_tool_rounds
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry
from app.core.tools.executor import execute_tool_call

logger = get_logger(__name__)
settings = get_settings()


# ── Events emitted by the agent loop ────────────────────────────────


@dataclass
class AgentEvent:
    """Event emitted by the agent loop to the caller."""

    event: str  # "token", "block", "citations", "tool", "plan", "status", "done", "error"
    data: str | dict | list | None = None


# ── Agent loop context ──────────────────────────────────────────────


@dataclass
class AgentContext:
    """All state needed for the agent loop."""

    tenant_id: UUID
    assistant_id: UUID
    conversation_id: UUID
    message: str
    system_prompt: str
    conversation_history: list[dict] = field(default_factory=list)
    collection_ids: list[UUID] | None = None
    integrations: list[dict] | None = None
    profile: str = "balanced"
    budget: BudgetManager | None = None
    plan: AgentPlan | None = None
    allowed_tools: list[ToolDefinition] | None = None
    user_context: dict | None = None


# ── Main loop ───────────────────────────────────────────────────────


async def run_agent_loop(ctx: AgentContext) -> AsyncIterator[AgentEvent]:
    """Run the multi-turn agent loop for balanced/pro/exec profiles.

    Yields AgentEvent objects that the worker publishes to Redis Streams.
    """
    client = AsyncOpenAI(
        api_key=settings.mistral_api_key,
        base_url="https://api.mistral.ai/v1",
    )

    budget = ctx.budget or BudgetManager(total=30_000)
    max_rounds = max_tool_rounds(ctx.profile)
    tool_schemas = tool_registry.get_openai_schemas(tools=ctx.allowed_tools)

    # Build initial messages
    messages: list[dict] = [{"role": "system", "content": ctx.system_prompt}]
    messages.extend(ctx.conversation_history)
    messages.append({"role": "user", "content": ctx.message})

    # If we have a plan, inject it into system context
    if ctx.plan:
        yield AgentEvent(event="plan", data=ctx.plan.model_dump(mode="json"))
        plan_section = ctx.plan.to_prompt_summary()
        messages[0]["content"] += f"\n\n{plan_section}"

    yield AgentEvent(event="status", data="analyzing")

    full_response = ""
    all_blocks: list[dict] = []
    all_citations: list[dict] = []
    total_tokens_in = 0
    total_tokens_out = 0

    for round_num in range(max_rounds):
        # ── Budget check ────────────────────────────────────────
        if not budget.check(500):  # minimum tokens for a round
            logger.warning(
                "budget_low_stopping",
                round=round_num,
                remaining=budget.remaining,
            )
            break

        # ── LLM call (streaming) ────────────────────────────────
        try:
            stream = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                max_tokens=settings.llm_max_tokens,
                stream=True,
            )
        except Exception as e:
            yield AgentEvent(event="error", data=str(e))
            return

        # ── Accumulate streamed response ────────────────────────
        streamed_content = ""
        tool_calls_acc: dict[int, dict] = {}
        round_tokens_in = 0
        round_tokens_out = 0

        try:
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta

                # Text content
                if delta.content:
                    streamed_content += delta.content
                    full_response += delta.content
                    yield AgentEvent(event="token", data=delta.content)

                # Tool calls (incremental accumulation)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_acc[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

                # Usage info (last chunk)
                if hasattr(chunk, "usage") and chunk.usage:
                    round_tokens_in = chunk.usage.prompt_tokens or 0
                    round_tokens_out = chunk.usage.completion_tokens or 0

        except Exception as e:
            yield AgentEvent(event="error", data=f"Stream error: {e}")
            return

        total_tokens_in += round_tokens_in
        total_tokens_out += round_tokens_out
        budget.consume_safe(round_tokens_in + round_tokens_out)

        # ── No tool calls → done ────────────────────────────────
        if not tool_calls_acc:
            break

        # ── Process tool calls ──────────────────────────────────
        # Build assistant message with tool_calls for message history
        assistant_tool_calls = [
            {
                "id": tc_data["id"],
                "type": "function",
                "function": {
                    "name": tc_data["name"],
                    "arguments": tc_data["arguments"],
                },
            }
            for tc_data in tool_calls_acc.values()
        ]
        messages.append({
            "role": "assistant",
            "content": streamed_content or None,
            "tool_calls": assistant_tool_calls,
        })

        has_continuation_tools = False

        for tc_data in tool_calls_acc.values():
            tool_name = tc_data["name"]
            try:
                args = json.loads(tc_data["arguments"])
            except json.JSONDecodeError:
                args = {}

            yield AgentEvent(
                event="tool",
                data={"tool": tool_name, "status": "calling"},
            )

            # Execute the tool
            result = await execute_tool_call(
                tool_name=tool_name,
                arguments=args,
                tenant_id=ctx.tenant_id,
                assistant_id=ctx.assistant_id,
                conversation_id=ctx.conversation_id,
                collection_ids=ctx.collection_ids,
                citations=all_citations,
                budget=budget,
                profile=ctx.profile,
                user_context=ctx.user_context,
            )

            yield AgentEvent(
                event="tool",
                data={
                    "tool": tool_name,
                    "status": "completed" if result.success else "failed",
                },
            )

            # Handle block results
            if result.block:
                all_blocks.append(result.block)
                yield AgentEvent(event="block", data=result.block)

            # Determine if tool requires loop continuation
            definition = tool_registry.get(tool_name)
            if definition and definition.continues_loop:
                has_continuation_tools = True

            # Build tool response message
            tool_content = result.to_tool_message()

            # Special handling for retrieval tools
            if definition and definition.category == ToolCategory.RETRIEVAL and result.success:
                # Internal RAG: result is list[RetrievedChunk]
                if isinstance(result.result, list):
                    from app.core.tools.retrieval_tool import format_chunks_for_llm
                    tool_content = format_chunks_for_llm(result.result)
                    for chunk in result.result:
                        all_citations.append({
                            "chunk_id": chunk.chunk_id,
                            "document_id": chunk.document_id,
                            "document_filename": chunk.document_filename,
                            "page_number": chunk.page_number,
                            "excerpt": chunk.content[:200],
                            "score": chunk.score,
                        })
                    if all_citations:
                        yield AgentEvent(event="citations", data=all_citations)

                # Web search: result is dict with _formatted + _web_results
                elif isinstance(result.result, dict) and "_formatted" in result.result:
                    tool_content = result.result["_formatted"]
                    web_results = result.result.get("_web_results", [])
                    for wr in web_results:
                        all_citations.append({
                            "chunk_id": f"web_{wr.url[:60]}",
                            "document_id": f"web:{wr.url}",
                            "document_filename": wr.source_label,
                            "page_number": None,
                            "excerpt": wr.snippet[:200],
                            "score": wr.score,
                            "url": wr.url,
                        })
                    if web_results:
                        yield AgentEvent(event="citations", data=all_citations)

            # Special handling for delegation results
            if (definition and definition.category == ToolCategory.DELEGATION
                    and result.success and isinstance(result.result, dict)):
                delegation = result.result
                # Format delegation answer for LLM
                target_name = delegation.get("target_assistant_name", "assistant")
                answer = delegation.get("answer_text", "")
                tool_content = f"[Réponse de l'assistant '{target_name}']\n{answer}"
                # Merge delegation citations
                for cit in delegation.get("citations", []):
                    all_citations.append(cit)
                if delegation.get("citations"):
                    yield AgentEvent(event="citations", data=all_citations)

            # Special handling for calendar results
            if (definition and definition.category == ToolCategory.CALENDAR
                    and result.success and isinstance(result.result, dict)):
                cal_result = result.result
                if cal_result.get("type") == "error":
                    tool_content = json.dumps({"error": cal_result.get("message", "Calendar error")})
                else:
                    tool_content = json.dumps(cal_result, ensure_ascii=False)

            messages.append({
                "role": "tool",
                "tool_call_id": tc_data["id"],
                "content": tool_content,
            })

        # If only non-continuation tools (blocks), stop the loop
        if not has_continuation_tools:
            break

        # Update plan step if applicable
        if ctx.plan:
            step = ctx.plan.current_step()
            if step:
                ctx.plan.mark_step(step.id, PlanStepStatus.COMPLETED)

    # ── Emit done ───────────────────────────────────────────────
    yield AgentEvent(
        event="done",
        data={
            "tokens_input": total_tokens_in,
            "tokens_output": total_tokens_out,
            "tool_rounds": min(round_num + 1, max_rounds),
            "blocks_count": len(all_blocks),
            "citations_count": len(all_citations),
        },
    )
