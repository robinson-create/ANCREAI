"""
Calendar tool handlers for ChatService.

These handlers execute calendar tools and return structured responses
that can be rendered as UI blocks in the chat.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.calendar import (
    CalendarIntentService,
    CalendarExecutorService,
    CalendarProviderService,
)
from app.schemas.calendar import CalendarCommand

logger = logging.getLogger(__name__)


async def handle_calendar_parse_command(
    args: Dict[str, Any],
    db: AsyncSession,
    current_user: dict,
) -> Dict[str, Any]:
    """
    Handle calendar_parse_command tool call.

    Returns:
        - If successful parse: {"type": "calendar_command", "command": {...}}
        - If clarification needed: {"type": "calendar_clarification", "clarification": {...}}
        - If no providers: {"type": "calendar_connect_cta"}
        - If error: {"type": "error", "message": "..."}
    """
    try:
        intent_service = CalendarIntentService(db, current_user)

        result = await intent_service.parse_intent(
            text=args.get("text", ""),
            timezone=args.get("timezone", "Europe/Paris"),
            now_iso=args.get("now_iso"),
            assistant_id=UUID(args["assistant_id"]) if args.get("assistant_id") else None,
            provider_preference=args.get("provider_preference"),
        )

        if not result.success:
            # No providers connected or error
            if "connecter" in (result.error or "").lower():
                return {
                    "type": "calendar_connect_cta",
                    "message": result.error,
                }

            return {
                "type": "error",
                "message": result.error or "Erreur lors du parsing",
            }

        if result.clarification:
            # Needs clarification - return structured question
            return {
                "type": "calendar_clarification",
                "clarification": result.clarification.model_dump(mode="json"),
            }

        if result.command:
            # Successful parse - return command
            return {
                "type": "calendar_command",
                "command": result.command.model_dump(mode="json"),
            }

        return {
            "type": "error",
            "message": "Résultat de parsing inattendu",
        }

    except Exception as e:
        logger.error(f"Error in calendar_parse_command: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Erreur: {str(e)}",
        }


async def handle_calendar_execute_command(
    args: Dict[str, Any],
    db: AsyncSession,
    current_user: dict,
) -> Dict[str, Any]:
    """
    Handle calendar_execute_command tool call.

    Returns:
        - If successful: {"type": "calendar_event_card", "event": {...}, "message": "..."}
        - If confirmation needed: {"type": "calendar_confirmation", "message": "..."}
        - If error: {"type": "error", "message": "..."}
    """
    try:
        executor_service = CalendarExecutorService(db, current_user)

        command_data = args.get("command", {})
        command = CalendarCommand(**command_data)

        result = await executor_service.execute(
            command=command,
            assistant_id=UUID(args["assistant_id"]) if args.get("assistant_id") else None,
            skip_confirmation=args.get("skip_confirmation", False),
        )

        if not result.success:
            # Check if confirmation is needed
            if result.error == "confirmation_required":
                return {
                    "type": "calendar_confirmation",
                    "message": result.message,
                    "command": command_data,
                }

            return {
                "type": "error",
                "message": result.message or "Erreur lors de l'exécution",
            }

        # Success - return event card
        if result.event:
            return {
                "type": "calendar_event_card",
                "event": result.event.model_dump(mode="json"),
                "message": result.message,
                "operation": result.operation.value,
            }

        # For list/find operations, return events list
        if result.events:
            return {
                "type": "calendar_event_list",
                "events": [e.model_dump(mode="json") for e in result.events],
                "message": result.message,
            }

        return {
            "type": "success",
            "message": result.message,
        }

    except Exception as e:
        logger.error(f"Error in calendar_execute_command: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Erreur: {str(e)}",
        }


async def handle_calendar_list_events(
    args: Dict[str, Any],
    db: AsyncSession,
    current_user: dict,
) -> Dict[str, Any]:
    """
    Handle calendar_list_events tool call.

    Returns:
        - {"type": "calendar_event_choices", "events": [...], "message": "..."}
    """
    try:
        provider_service = CalendarProviderService(db, current_user)

        from datetime import datetime

        events = await provider_service.list_events(
            range_start=datetime.fromisoformat(args["range_start"]),
            range_end=datetime.fromisoformat(args["range_end"]),
            provider=args.get("provider"),
            query=args.get("query"),
        )

        if not events:
            return {
                "type": "info",
                "message": "Aucun événement trouvé dans cette période.",
            }

        # Return as choices for disambiguation
        return {
            "type": "calendar_event_choices",
            "events": [e.model_dump(mode="json") for e in events],
            "message": f"{len(events)} événement(s) trouvé(s)",
        }

    except Exception as e:
        logger.error(f"Error in calendar_list_events: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Erreur: {str(e)}",
        }


async def handle_calendar_find_events(
    args: Dict[str, Any],
    db: AsyncSession,
    current_user: dict,
) -> Dict[str, Any]:
    """
    Handle calendar_find_events tool call.

    Returns:
        - {"type": "calendar_event_choices", "events": [...], "message": "..."}
    """
    try:
        provider_service = CalendarProviderService(db, current_user)

        from datetime import datetime

        range_start = (
            datetime.fromisoformat(args["range_start"]) if args.get("range_start") else None
        )
        range_end = datetime.fromisoformat(args["range_end"]) if args.get("range_end") else None

        events = await provider_service.find_events(
            title_query=args.get("title_query"),
            range_start=range_start,
            range_end=range_end,
            provider=args.get("provider"),
        )

        if not events:
            return {
                "type": "info",
                "message": "Aucun événement correspondant trouvé.",
            }

        return {
            "type": "calendar_event_choices",
            "events": [e.model_dump(mode="json") for e in events],
            "message": f"{len(events)} événement(s) correspondant(s)",
        }

    except Exception as e:
        logger.error(f"Error in calendar_find_events: {e}", exc_info=True)
        return {
            "type": "error",
            "message": f"Erreur: {str(e)}",
        }


# Calendar tool handlers registry
CALENDAR_TOOL_HANDLERS = {
    "calendar_parse_command": handle_calendar_parse_command,
    "calendar_execute_command": handle_calendar_execute_command,
    "calendar_list_events": handle_calendar_list_events,
    "calendar_find_events": handle_calendar_find_events,
}


def is_calendar_tool(tool_name: str) -> bool:
    """Check if a tool name is a calendar tool."""
    return tool_name in CALENDAR_TOOL_HANDLERS


async def execute_calendar_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    db: AsyncSession,
    current_user: dict,
) -> str:
    """
    Execute a calendar tool and return JSON result.

    Args:
        tool_name: Name of the calendar tool
        arguments: Tool arguments
        db: Database session
        current_user: Current user context

    Returns:
        JSON string with result
    """
    import json

    handler = CALENDAR_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"type": "error", "message": f"Unknown calendar tool: {tool_name}"})

    result = await handler(arguments, db, current_user)
    return json.dumps(result, ensure_ascii=False)
