"""Tool executor — dispatches tool calls to registered handlers.

Used by the agent worker to execute tool calls from the LLM response.
Routes each tool call to the appropriate handler based on the tool registry,
handles timeouts, and returns structured results.
"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from app.core.budget import BudgetManager
from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry

logger = get_logger(__name__)


class ToolExecutionResult:
    """Result of executing a tool call."""

    __slots__ = ("tool_name", "category", "success", "result", "error", "block")

    def __init__(
        self,
        tool_name: str,
        category: ToolCategory,
        *,
        success: bool = True,
        result: str | dict | None = None,
        error: str | None = None,
        block: dict | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.category = category
        self.success = success
        self.result = result
        self.error = error
        self.block = block  # For block/email tools: the UI block payload

    def to_tool_message(self) -> str:
        """Format as a string suitable for returning to the LLM."""
        if self.error:
            return json.dumps({"error": self.error})
        if isinstance(self.result, dict):
            return json.dumps(self.result)
        return str(self.result) if self.result else ""


async def execute_tool_call(
    *,
    tool_name: str,
    arguments: dict,
    tenant_id: UUID,
    assistant_id: UUID | None = None,
    conversation_id: UUID | None = None,
    collection_ids: list[UUID] | None = None,
    citations: list | None = None,
    budget: BudgetManager | None = None,
    profile: str = "reactive",
    user_context: dict | None = None,
) -> ToolExecutionResult:
    """Execute a single tool call by dispatching to the registered handler.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Parsed arguments from the LLM function call.
        tenant_id: Current tenant.
        assistant_id: Current assistant (for document tools).
        conversation_id: Current conversation.
        collection_ids: Active collection IDs (for retrieval).
        citations: Current citations from prior retrieval.
        budget: Budget manager for delegation reservation.
        profile: Current execution profile.
        user_context: User context dict for calendar tools (tenant_id, user_id).

    Returns:
        ToolExecutionResult with success/error and optional block payload.
    """
    definition = tool_registry.get(tool_name)
    if definition is None:
        logger.warning("tool_not_found", tool_name=tool_name)
        return ToolExecutionResult(
            tool_name=tool_name,
            category=ToolCategory.BLOCK,
            success=False,
            error=f"Unknown tool: {tool_name}",
        )

    handler = tool_registry.get_handler(tool_name)

    # ── Block tools without handlers (generative UI) ────────────
    if handler is None and definition.category == ToolCategory.BLOCK:
        block = {
            "id": arguments.get("id", ""),
            "type": definition.block_type or tool_name,
            "payload": arguments,
        }
        return ToolExecutionResult(
            tool_name=tool_name,
            category=definition.category,
            result=arguments,
            block=block,
        )

    if handler is None:
        logger.warning("tool_handler_not_found", tool_name=tool_name)
        return ToolExecutionResult(
            tool_name=tool_name,
            category=definition.category,
            success=False,
            error=f"No handler registered for tool: {tool_name}",
        )

    # ── Execute with timeout ────────────────────────────────────
    try:
        # Build kwargs based on handler expectations
        kwargs = _build_handler_kwargs(
            definition=definition,
            arguments=arguments,
            tenant_id=tenant_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            collection_ids=collection_ids,
            citations=citations,
            budget=budget,
            profile=profile,
            user_context=user_context,
        )

        result = await asyncio.wait_for(
            handler(**kwargs),
            timeout=definition.timeout_seconds,
        )

        # Determine if result is a block
        block = None
        if isinstance(result, dict) and "type" in result and "payload" in result:
            block = result

        logger.info(
            "tool_executed",
            tool_name=tool_name,
            category=definition.category,
            success=True,
        )

        return ToolExecutionResult(
            tool_name=tool_name,
            category=definition.category,
            result=result,
            block=block,
        )

    except TimeoutError:
        logger.warning(
            "tool_timeout",
            tool_name=tool_name,
            timeout=definition.timeout_seconds,
        )
        return ToolExecutionResult(
            tool_name=tool_name,
            category=definition.category,
            success=False,
            error=f"Tool timed out after {definition.timeout_seconds}s",
        )
    except Exception as e:
        logger.exception("tool_execution_error", tool_name=tool_name)
        return ToolExecutionResult(
            tool_name=tool_name,
            category=definition.category,
            success=False,
            error=str(e),
        )


def _build_handler_kwargs(
    *,
    definition: ToolDefinition,
    arguments: dict,
    tenant_id: UUID,
    assistant_id: UUID | None,
    conversation_id: UUID | None,
    collection_ids: list[UUID] | None,
    citations: list | None,
    budget: BudgetManager | None = None,
    profile: str = "reactive",
    user_context: dict | None = None,
) -> dict:
    """Build kwargs for the tool handler based on tool category."""
    if definition.category == ToolCategory.EMAIL:
        return {
            "args": arguments,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "citations": citations,
        }

    if definition.name == "createDocument":
        return {
            "args": arguments,
            "tenant_id": tenant_id,
            "assistant_id": assistant_id,
            "conversation_id": conversation_id,
            "citations": citations,
        }

    if definition.category == ToolCategory.DELEGATION:
        return {
            "args": arguments,
            "tenant_id": tenant_id,
            "assistant_id": assistant_id,
            "budget": budget,
            "profile": profile,
        }

    if definition.category == ToolCategory.CALENDAR:
        return {
            "args": arguments,
            "tenant_id": tenant_id,
            "user_context": user_context,
        }

    if definition.category == ToolCategory.RETRIEVAL:
        return {
            "query": arguments.get("query", ""),
            "tenant_id": tenant_id,
            "collection_ids": collection_ids,
        }

    # Default: pass arguments directly
    return arguments
