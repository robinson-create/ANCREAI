"""
Calendar Executor Service.

Executes structured CalendarCommands by:
1. Calling Nango proxy to interact with Google/Microsoft APIs
2. Creating/updating CalendarEventLink records
3. Logging operations for audit and debugging
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
import hashlib
import time
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete

from app.models.calendar import CalendarEventLink, CalendarOperationLog, NangoConnection
from app.schemas.calendar import (
    CalendarCommand,
    CalendarResult,
    EventSummary,
    CalendarOperationType,
    CalendarProvider,
)
from app.services.calendar.nango_client import NangoCalendarClient
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CalendarExecutorService:
    """Service to execute calendar commands"""

    def __init__(self, db: AsyncSession, current_user: dict):
        self.db = db
        self.tenant_id = current_user["tenant_id"]
        self.user_id = current_user["user_id"]
        self.nango_client = NangoCalendarClient()

    async def execute(
        self,
        command: CalendarCommand,
        assistant_id: Optional[UUID] = None,
        skip_confirmation: bool = False,
    ) -> CalendarResult:
        """
        Execute a calendar command.

        Args:
            command: Structured calendar command
            assistant_id: Assistant ID if triggered from assistant
            skip_confirmation: Skip confirmation for delete operations

        Returns:
            CalendarResult with success status and event data
        """
        start_time = time.time()

        try:
            # Validation: confirmation required?
            if command.requires_confirmation and not skip_confirmation:
                return CalendarResult(
                    success=False,
                    operation=command.action,
                    message="⚠️ Confirmation requise. Confirmes-tu cette action ?",
                    error="confirmation_required",
                )

            # Route to appropriate handler
            if command.action == CalendarOperationType.CREATE:
                result = await self._create_event(command, assistant_id)
            elif command.action == CalendarOperationType.UPDATE:
                result = await self._update_event(command, assistant_id)
            elif command.action == CalendarOperationType.DELETE:
                result = await self._delete_event(command, assistant_id)
            elif command.action == CalendarOperationType.LIST:
                result = await self._list_events(command)
            elif command.action == CalendarOperationType.FIND:
                result = await self._find_events(command)
            else:
                raise ValueError(f"Unsupported action: {command.action}")

            # Log success
            await self._log_operation(
                op_type=command.action.value,
                status="success",
                provider=command.provider.value if command.provider else None,
                request_payload=command.model_dump(mode="json"),
                response_payload=result.model_dump(mode="json"),
                execution_time_ms=int((time.time() - start_time) * 1000),
                assistant_id=assistant_id,
            )

            return result

        except Exception as e:
            logger.error(f"Error executing calendar command: {e}", exc_info=True)

            # Log error
            await self._log_operation(
                op_type=command.action.value,
                status="error",
                provider=command.provider.value if command.provider else None,
                request_payload=command.model_dump(mode="json"),
                error_message=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
                assistant_id=assistant_id,
            )

            return CalendarResult(
                success=False,
                operation=command.action,
                message=f"❌ Erreur: {str(e)}",
                error=str(e),
            )

    # ========== CREATE ==========

    async def _create_event(
        self, command: CalendarCommand, assistant_id: Optional[UUID]
    ) -> CalendarResult:
        """Create a new calendar event"""

        # Get Nango connection
        nango_conn = await self._get_nango_connection(command.provider)

        # Build event data
        event_data = {
            "summary": command.title,
            "start": {
                "dateTime": command.starts_at.isoformat(),
                "timeZone": command.timezone,
            },
            "end": {
                "dateTime": command.ends_at.isoformat(),
                "timeZone": command.timezone,
            },
            "attendees": [{"email": email} for email in command.attendees],
            "description": command.description or "",
        }

        # Add video conference if requested
        if command.add_video_conference:
            if command.provider == CalendarProvider.GOOGLE:
                # Google Meet: requires conferenceData
                event_data["conferenceData"] = {
                    "createRequest": {"requestId": f"ancre-{self.tenant_id}-{int(time.time())}"}
                }

        # Call Nango
        created_event = await self.nango_client.create_event(
            provider=command.provider,
            nango_connection_id=nango_conn.nango_connection_id,
            event_data=event_data,
            add_video=command.add_video_conference,
        )

        # Save CalendarEventLink
        attendees_hash = self._hash_attendees(command.attendees)

        event_link = CalendarEventLink(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            assistant_id=assistant_id,
            provider=command.provider.value,
            external_event_id=created_event["id"],
            external_calendar_id=created_event.get("calendar_id", "primary"),
            title_snapshot=command.title,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            timezone=command.timezone,
            attendees_hash=attendees_hash,
            has_video_conference=command.add_video_conference,
        )
        self.db.add(event_link)
        await self.db.commit()

        # Build response
        event_summary = EventSummary(
            id=created_event["id"],
            title=command.title,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            timezone=command.timezone,
            provider=command.provider,
            calendar_id=created_event.get("calendar_id", "primary"),
            attendees=command.attendees,
            video_conference_link=created_event.get("video_link"),
            html_link=created_event.get("html_link"),
            description=command.description,
        )

        title_indicator = "🤖 " if command.title_autogenerated else ""
        video_indicator = "📹 " if command.add_video_conference else ""

        return CalendarResult(
            success=True,
            operation=CalendarOperationType.CREATE,
            provider=command.provider,
            event=event_summary,
            message=f"✅ {title_indicator}{video_indicator}Événement créé: {command.title} le {command.starts_at.strftime('%d/%m à %H:%M')}",
        )

    # ========== UPDATE ==========

    async def _update_event(
        self, command: CalendarCommand, assistant_id: Optional[UUID]
    ) -> CalendarResult:
        """Update an existing calendar event"""

        # Find the event link
        event_link = await self._find_event_link(command)

        if not event_link:
            return CalendarResult(
                success=False,
                operation=CalendarOperationType.UPDATE,
                message="❌ Événement introuvable. Précise le titre ou la date.",
                error="event_not_found",
            )

        # Get Nango connection
        nango_conn = await self._get_nango_connection(CalendarProvider(event_link.provider))

        # Build update data
        update_data = {}
        if command.title:
            update_data["summary"] = command.title
        if command.starts_at:
            update_data["start"] = {
                "dateTime": command.starts_at.isoformat(),
                "timeZone": command.timezone,
            }
        if command.ends_at:
            update_data["end"] = {
                "dateTime": command.ends_at.isoformat(),
                "timeZone": command.timezone,
            }
        if command.attendees:
            update_data["attendees"] = [{"email": email} for email in command.attendees]
        if command.description is not None:
            update_data["description"] = command.description

        # Call Nango
        updated_event = await self.nango_client.update_event(
            provider=CalendarProvider(event_link.provider),
            nango_connection_id=nango_conn.nango_connection_id,
            event_id=event_link.external_event_id,
            calendar_id=event_link.external_calendar_id,
            update_data=update_data,
        )

        # Update event_link
        if command.title:
            event_link.title_snapshot = command.title
        if command.starts_at:
            event_link.starts_at = command.starts_at
        if command.ends_at:
            event_link.ends_at = command.ends_at
        if command.attendees:
            event_link.attendees_hash = self._hash_attendees(command.attendees)
        event_link.last_synced_at = datetime.utcnow()

        await self.db.commit()

        # Build response
        event_summary = EventSummary(
            id=event_link.external_event_id,
            title=event_link.title_snapshot,
            starts_at=event_link.starts_at,
            ends_at=event_link.ends_at,
            timezone=event_link.timezone,
            provider=CalendarProvider(event_link.provider),
            calendar_id=event_link.external_calendar_id,
            attendees=command.attendees or [],
            video_conference_link=updated_event.get("video_link"),
            html_link=updated_event.get("html_link"),
        )

        return CalendarResult(
            success=True,
            operation=CalendarOperationType.UPDATE,
            provider=CalendarProvider(event_link.provider),
            event=event_summary,
            message=f"✅ Événement modifié: {event_link.title_snapshot}",
        )

    # ========== DELETE ==========

    async def _delete_event(
        self, command: CalendarCommand, assistant_id: Optional[UUID]
    ) -> CalendarResult:
        """Delete a calendar event"""

        # Find the event link
        event_link = await self._find_event_link(command)

        if not event_link:
            return CalendarResult(
                success=False,
                operation=CalendarOperationType.DELETE,
                message="❌ Événement introuvable.",
                error="event_not_found",
            )

        # Get Nango connection
        nango_conn = await self._get_nango_connection(CalendarProvider(event_link.provider))

        # Call Nango to delete
        await self.nango_client.delete_event(
            provider=CalendarProvider(event_link.provider),
            nango_connection_id=nango_conn.nango_connection_id,
            event_id=event_link.external_event_id,
            calendar_id=event_link.external_calendar_id,
        )

        # Delete event_link
        title_snapshot = event_link.title_snapshot
        await self.db.delete(event_link)
        await self.db.commit()

        return CalendarResult(
            success=True,
            operation=CalendarOperationType.DELETE,
            provider=CalendarProvider(event_link.provider),
            message=f"✅ Événement supprimé: {title_snapshot}",
        )

    # ========== LIST/FIND ==========

    async def _list_events(self, command: CalendarCommand) -> CalendarResult:
        """List events (delegated to provider service)"""
        from app.services.calendar.provider_service import CalendarProviderService

        provider_service = CalendarProviderService(self.db, {"tenant_id": self.tenant_id, "user_id": self.user_id})

        events = await provider_service.list_events(
            range_start=command.range_start,
            range_end=command.range_end,
            provider=command.provider,
            query=command.query,
        )

        return CalendarResult(
            success=True,
            operation=CalendarOperationType.LIST,
            provider=command.provider,
            events=events,
            message=f"📅 {len(events)} événement(s) trouvé(s)",
        )

    async def _find_events(self, command: CalendarCommand) -> CalendarResult:
        """Find events matching search criteria"""
        from app.services.calendar.provider_service import CalendarProviderService

        provider_service = CalendarProviderService(self.db, {"tenant_id": self.tenant_id, "user_id": self.user_id})

        events = await provider_service.find_events(
            title_query=command.search_title,
            range_start=command.search_range_start,
            range_end=command.search_range_end,
            provider=command.provider,
        )

        return CalendarResult(
            success=True,
            operation=CalendarOperationType.FIND,
            provider=command.provider,
            events=events,
            message=f"🔍 {len(events)} événement(s) correspondant(s)",
        )

    # ========== Helpers ==========

    async def _find_event_link(self, command: CalendarCommand) -> Optional[CalendarEventLink]:
        """Find CalendarEventLink from command search criteria"""

        stmt = select(CalendarEventLink).where(
            CalendarEventLink.tenant_id == self.tenant_id,
            CalendarEventLink.user_id == self.user_id,
        )

        # Search by explicit event_id (most precise)
        if command.event_id:
            stmt = stmt.where(CalendarEventLink.external_event_id == command.event_id)

        # Search by title (fuzzy)
        elif command.search_title:
            stmt = stmt.where(CalendarEventLink.title_snapshot.ilike(f"%{command.search_title}%"))

        # Add time range filter if provided
        if command.search_range_start:
            stmt = stmt.where(CalendarEventLink.starts_at >= command.search_range_start)
        if command.search_range_end:
            stmt = stmt.where(CalendarEventLink.ends_at <= command.search_range_end)

        # Provider filter
        if command.provider:
            stmt = stmt.where(CalendarEventLink.provider == command.provider.value)

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_nango_connection(self, provider: CalendarProvider) -> NangoConnection:
        """Get active Nango connection for provider"""

        provider_key = f"{provider.value}_calendar"

        stmt = select(NangoConnection).where(
            NangoConnection.tenant_id == self.tenant_id,
            NangoConnection.user_id == self.user_id,
            NangoConnection.provider == provider_key,
            NangoConnection.is_active == True,
        )

        result = await self.db.execute(stmt)
        conn = result.scalars().first()

        if not conn:
            raise ValueError(
                f"Aucune connexion {provider.value.title()} Calendar active. "
                f"Connecte ton calendrier dans les paramètres."
            )

        return conn

    def _hash_attendees(self, attendees: list[str]) -> str:
        """Hash attendee emails for change detection"""
        sorted_emails = sorted(attendees)
        return hashlib.md5(",".join(sorted_emails).encode()).hexdigest()

    async def _log_operation(
        self,
        op_type: str,
        status: str,
        provider: Optional[str],
        request_payload: Optional[dict] = None,
        response_payload: Optional[dict] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        assistant_id: Optional[UUID] = None,
    ):
        """Log calendar operation for audit"""

        log = CalendarOperationLog(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            assistant_id=assistant_id,
            op_type=op_type,
            status=status,
            provider=provider,
            request_payload=self._sanitize_payload(request_payload),
            response_payload=self._sanitize_payload(response_payload),
            error_message=error_message,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)
        await self.db.commit()

    def _sanitize_payload(self, payload: Optional[dict]) -> Optional[dict]:
        """Sanitize sensitive data in logs (mask full emails)"""
        if not payload:
            return None

        sanitized = payload.copy()

        # Mask attendee emails (keep domain only)
        if "attendees" in sanitized and isinstance(sanitized["attendees"], list):
            sanitized["attendees"] = [
                email.split("@")[1] if "@" in email else "***" for email in sanitized["attendees"]
            ]

        return sanitized
