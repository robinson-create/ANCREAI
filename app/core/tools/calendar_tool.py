"""Calendar tool wrappers — adapt calendar handlers for the agent executor.

The existing calendar handlers in chat_tools/calendar_handlers.py expect
(args, db, current_user). This module wraps them to match the executor's
pattern: each wrapper creates its own DB session (like email/delegation tools)
and builds a minimal current_user dict from user_context.
"""

from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger
from app.core.tool_registry import ToolCategory, ToolDefinition, tool_registry

logger = get_logger(__name__)


async def _dispatch_calendar(
    tool_name: str,
    *,
    args: dict,
    tenant_id: UUID,
    user_context: dict | None = None,
) -> dict:
    """Dispatch to the appropriate calendar handler with a fresh DB session."""
    from app.database import async_session_maker
    from app.services.chat_tools.calendar_handlers import CALENDAR_TOOL_HANDLERS

    handler = CALENDAR_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"type": "error", "message": f"Unknown calendar tool: {tool_name}"}

    current_user = user_context or {"tenant_id": str(tenant_id)}

    async with async_session_maker() as db:
        return await handler(args, db, current_user)


# ── Thin wrappers (one per calendar tool) ─────────────────────────


async def handle_calendar_parse_command(
    *, args: dict, tenant_id: UUID, user_context: dict | None = None,
) -> dict:
    return await _dispatch_calendar(
        "calendar_parse_command", args=args, tenant_id=tenant_id, user_context=user_context,
    )


async def handle_calendar_execute_command(
    *, args: dict, tenant_id: UUID, user_context: dict | None = None,
) -> dict:
    return await _dispatch_calendar(
        "calendar_execute_command", args=args, tenant_id=tenant_id, user_context=user_context,
    )


async def handle_calendar_list_events(
    *, args: dict, tenant_id: UUID, user_context: dict | None = None,
) -> dict:
    return await _dispatch_calendar(
        "calendar_list_events", args=args, tenant_id=tenant_id, user_context=user_context,
    )


async def handle_calendar_find_events(
    *, args: dict, tenant_id: UUID, user_context: dict | None = None,
) -> dict:
    return await _dispatch_calendar(
        "calendar_find_events", args=args, tenant_id=tenant_id, user_context=user_context,
    )


# ── Handler lookup ────────────────────────────────────────────────

_HANDLER_MAP = {
    "calendar_parse_command": handle_calendar_parse_command,
    "calendar_execute_command": handle_calendar_execute_command,
    "calendar_list_events": handle_calendar_list_events,
    "calendar_find_events": handle_calendar_find_events,
}


# ── Registration ──────────────────────────────────────────────────


def register_calendar_tools() -> None:
    """Register all calendar tools with schemas + handlers."""
    from app.services.chat_tools.calendar_tools import get_calendar_tools

    for schema in get_calendar_tools():
        name = schema["function"]["name"]
        handler = _HANDLER_MAP.get(name)

        tool_registry.register(
            ToolDefinition(
                name=name,
                category=ToolCategory.CALENDAR,
                provider="calendar",
                description=schema["function"].get("description", name),
                openai_schema=schema,
                continues_loop=True,
                min_profile="balanced",
                timeout_seconds=15,
            ),
            handler=handler,
        )
