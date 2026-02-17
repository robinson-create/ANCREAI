"""
Calendar API endpoints.

Provides REST API for:
- Parsing user text into calendar commands
- Executing calendar operations
- Listing events and providers
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, CurrentUser
from app.schemas.calendar import (
    CalendarParseRequest,
    CalendarParseResponse,
    CalendarExecuteRequest,
    CalendarResult,
    ProvidersListResponse,
    CalendarEventsResponse,
    CalendarProvider,
)
from app.services.calendar import (
    CalendarIntentService,
    CalendarExecutorService,
    CalendarProviderService,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calendar"])


@router.post("/parse", response_model=CalendarParseResponse)
async def parse_calendar_command(
    request: CalendarParseRequest,
    user: CurrentUser,
    db: DbSession,
):
    """
    Parse user natural language text into structured CalendarCommand.

    Uses Mistral LLM to understand intent, resolve temporal expressions,
    and detect ambiguities.

    **Returns:**
    - Either a `command` (ready to execute)
    - Or a `clarification` (needs user input)

    **Example:**
    ```json
    {
        "text": "Ajoute une visio avec Marie demain à 14h",
        "timezone": "Europe/Paris"
    }
    ```
    """
    try:
        current_user = {"tenant_id": user.tenant_id, "user_id": str(user.id)}
        intent_service = CalendarIntentService(db, current_user)

        result = await intent_service.parse_intent(
            text=request.text,
            timezone=request.timezone,
            now_iso=request.now_iso,
            assistant_id=request.assistant_id,
            provider_preference=request.provider_preference,
        )

        return result

    except Exception as e:
        logger.error(f"Error in /calendar/parse: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'analyse: {str(e)}",
        )


@router.post("/execute", response_model=CalendarResult)
async def execute_calendar_command(
    request: CalendarExecuteRequest,
    user: CurrentUser,
    db: DbSession,
):
    """
    Execute a validated CalendarCommand.

    Creates, updates, or deletes calendar events via Google/Microsoft APIs.

    **Example:**
    ```json
    {
        "command": {
            "action": "create",
            "provider": "google",
            "title": "Réunion avec Marie",
            "starts_at": "2026-02-20T14:00:00+01:00",
            "ends_at": "2026-02-20T14:30:00+01:00",
            "add_video_conference": true
        }
    }
    ```
    """
    try:
        current_user = {"tenant_id": user.tenant_id, "user_id": str(user.id)}
        executor_service = CalendarExecutorService(db, current_user)

        result = await executor_service.execute(
            command=request.command,
            assistant_id=request.assistant_id,
            skip_confirmation=request.skip_confirmation,
        )

        return result

    except ValueError as e:
        # Known errors (e.g., provider not connected)
        logger.warning(f"Validation error in /calendar/execute: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in /calendar/execute: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution: {str(e)}",
        )


@router.get("/providers", response_model=ProvidersListResponse)
async def list_connected_providers(
    user: CurrentUser,
    db: DbSession,
):
    """
    List connected calendar providers for current user.

    Returns information about Google Calendar and/or Microsoft Calendar connections.

    **Response:**
    ```json
    {
        "providers": [
            {
                "provider": "google",
                "nango_connection_id": "conn_123",
                "is_active": true,
                "user_email": "user@example.com",
                "connected_at": "2026-02-15T10:00:00Z"
            }
        ],
        "has_google": true,
        "has_microsoft": false
    }
    ```
    """
    try:
        current_user = {"tenant_id": user.tenant_id, "user_id": str(user.id)}
        provider_service = CalendarProviderService(db, current_user)
        providers = await provider_service.list_connected_providers()

        return ProvidersListResponse(
            providers=providers,
            has_google=any(p.provider == CalendarProvider.GOOGLE for p in providers),
            has_microsoft=any(p.provider == CalendarProvider.MICROSOFT for p in providers),
        )

    except Exception as e:
        logger.error(f"Error in /calendar/providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des providers: {str(e)}",
        )


@router.get("/events", response_model=CalendarEventsResponse)
async def list_calendar_events(
    user: CurrentUser,
    db: DbSession,
    range_start: datetime = Query(..., description="Start of time range (ISO 8601)"),
    range_end: datetime = Query(..., description="End of time range (ISO 8601)"),
    provider: Optional[CalendarProvider] = Query(None, description="Filter by provider"),
    query: Optional[str] = Query(None, description="Search query for event titles"),
):
    """
    List calendar events within a date range.

    Queries Google Calendar and/or Microsoft Calendar and returns unified results.

    **Query Parameters:**
    - `range_start`: Start datetime (ISO 8601, e.g., "2026-02-17T00:00:00+01:00")
    - `range_end`: End datetime
    - `provider`: Optional filter ("google" or "microsoft")
    - `query`: Optional text search in event titles

    **Example:**
    ```
    GET /calendar/events?range_start=2026-02-17T00:00:00+01:00&range_end=2026-02-20T23:59:59+01:00
    ```

    **Response:**
    ```json
    {
        "events": [
            {
                "id": "evt_123",
                "title": "Standup équipe",
                "starts_at": "2026-02-17T09:00:00+01:00",
                "ends_at": "2026-02-17T09:30:00+01:00",
                "provider": "google",
                "video_conference_link": "https://meet.google.com/xxx"
            }
        ],
        "range_start": "2026-02-17T00:00:00+01:00",
        "range_end": "2026-02-20T23:59:59+01:00",
        "providers_queried": ["google"]
    }
    ```
    """
    try:
        current_user = {"tenant_id": user.tenant_id, "user_id": str(user.id)}
        provider_service = CalendarProviderService(db, current_user)

        events = await provider_service.list_events(
            range_start=range_start,
            range_end=range_end,
            provider=provider,
            query=query,
        )

        # Determine which providers were queried
        if provider:
            providers_queried = [provider]
        else:
            # All connected providers
            connected = await provider_service.list_connected_providers()
            providers_queried = [p.provider for p in connected]

        return CalendarEventsResponse(
            events=events,
            range_start=range_start,
            range_end=range_end,
            providers_queried=providers_queried,
        )

    except Exception as e:
        logger.error(f"Error in /calendar/events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des événements: {str(e)}",
        )
