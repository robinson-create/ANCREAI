"""
Calendar Provider Service.

Handles:
- Listing events from Google/Microsoft across providers
- Finding events by search criteria
- Converting provider formats to unified EventSummary
- Getting provider connection status
"""

from datetime import datetime
from typing import Optional, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar import NangoConnection
from app.schemas.calendar import (
    CalendarProvider,
    EventSummary,
    ProviderInfo,
)
from app.services.calendar.nango_client import NangoCalendarClient

logger = logging.getLogger(__name__)


class CalendarProviderService:
    """Service for provider-level calendar operations"""

    def __init__(self, db: AsyncSession, current_user: dict):
        self.db = db
        self.tenant_id = current_user["tenant_id"]
        self.user_id = current_user["user_id"]
        self.nango_client = NangoCalendarClient()

    async def list_connected_providers(self) -> List[ProviderInfo]:
        """
        List all connected calendar providers for this user.

        Returns:
            List of ProviderInfo with connection details
        """
        stmt = select(NangoConnection).where(
            NangoConnection.tenant_id == self.tenant_id,
            NangoConnection.user_id == self.user_id,
            NangoConnection.provider.in_(["google_calendar", "microsoft_calendar"]),
        )

        result = await self.db.execute(stmt)
        connections = result.scalars().all()

        providers = []
        for conn in connections:
            # Map provider string to enum
            if "google" in conn.provider.lower():
                provider_enum = CalendarProvider.GOOGLE
            elif "microsoft" in conn.provider.lower():
                provider_enum = CalendarProvider.MICROSOFT
            else:
                continue

            # Extract user email from metadata
            user_email = None
            if conn.connection_metadata:
                user_email = conn.connection_metadata.get("email") or conn.connection_metadata.get("userPrincipalName")

            providers.append(
                ProviderInfo(
                    provider=provider_enum,
                    nango_connection_id=conn.nango_connection_id,
                    is_active=conn.is_active,
                    user_email=user_email,
                    connected_at=conn.created_at,
                )
            )

        return providers

    async def list_events(
        self,
        range_start: datetime,
        range_end: datetime,
        provider: Optional[CalendarProvider] = None,
        query: Optional[str] = None,
    ) -> List[EventSummary]:
        """
        List calendar events across providers.

        Args:
            range_start: Start of time range
            range_end: End of time range
            provider: Optional provider filter (otherwise queries all)
            query: Optional text search query

        Returns:
            List of EventSummary, sorted by start time
        """
        all_events = []

        # Get providers to query
        connected_providers = await self.list_connected_providers()

        if provider:
            # Filter to specific provider
            connected_providers = [p for p in connected_providers if p.provider == provider]

        if not connected_providers:
            logger.warning("No connected providers to query")
            return []

        # Query each provider
        for provider_info in connected_providers:
            try:
                events = await self._list_events_from_provider(
                    provider=provider_info.provider,
                    nango_connection_id=provider_info.nango_connection_id,
                    time_min=range_start.isoformat(),
                    time_max=range_end.isoformat(),
                    query=query,
                )
                all_events.extend(events)

            except Exception as e:
                logger.error(f"Failed to list events from {provider_info.provider}: {e}", exc_info=True)
                # Continue with other providers

        # Sort by start time
        all_events.sort(key=lambda e: e.starts_at)

        return all_events

    async def find_events(
        self,
        title_query: Optional[str] = None,
        range_start: Optional[datetime] = None,
        range_end: Optional[datetime] = None,
        provider: Optional[CalendarProvider] = None,
    ) -> List[EventSummary]:
        """
        Find events matching search criteria.

        More flexible than list_events - supports fuzzy title search.

        Args:
            title_query: Search in event title (case-insensitive)
            range_start: Optional start time filter
            range_end: Optional end time filter
            provider: Optional provider filter

        Returns:
            List of matching EventSummary
        """
        # Use list_events with query
        if not range_start:
            # Default to past 7 days
            from datetime import timedelta
            range_start = datetime.now() - timedelta(days=7)

        if not range_end:
            # Default to next 30 days
            from datetime import timedelta
            range_end = datetime.now() + timedelta(days=30)

        events = await self.list_events(
            range_start=range_start,
            range_end=range_end,
            provider=provider,
            query=title_query,
        )

        # Additional filtering (client-side) if needed
        if title_query:
            title_lower = title_query.lower()
            events = [e for e in events if title_lower in e.title.lower()]

        return events

    async def get_busy_slots(
        self,
        range_start: datetime,
        range_end: datetime,
        provider: Optional[CalendarProvider] = None,
    ) -> List[dict]:
        """
        Get busy time slots (for availability calculation).

        Returns list of {starts_at, ends_at, event_title} dicts.
        """
        events = await self.list_events(range_start, range_end, provider)

        return [
            {
                "starts_at": event.starts_at,
                "ends_at": event.ends_at,
                "event_title": event.title,
            }
            for event in events
        ]

    # ========== Private Helpers ==========

    async def _list_events_from_provider(
        self,
        provider: CalendarProvider,
        nango_connection_id: str,
        time_min: str,
        time_max: str,
        query: Optional[str],
    ) -> List[EventSummary]:
        """List events from a specific provider and convert to EventSummary"""

        raw_events = await self.nango_client.list_events(
            provider=provider,
            nango_connection_id=nango_connection_id,
            time_min=time_min,
            time_max=time_max,
            query=query,
        )

        # Convert provider-specific format to EventSummary
        if provider == CalendarProvider.GOOGLE:
            return [self._google_event_to_summary(e, provider) for e in raw_events]
        elif provider == CalendarProvider.MICROSOFT:
            return [self._microsoft_event_to_summary(e, provider) for e in raw_events]
        else:
            return []

    def _google_event_to_summary(self, event: dict, provider: CalendarProvider) -> EventSummary:
        """Convert Google Calendar event to EventSummary"""

        # Extract start/end times
        start = event.get("start", {})
        end = event.get("end", {})

        starts_at = self._parse_datetime(start.get("dateTime") or start.get("date"))
        ends_at = self._parse_datetime(end.get("dateTime") or end.get("date"))
        timezone = start.get("timeZone", "UTC")

        # Extract attendees
        attendees = [att.get("email", "") for att in event.get("attendees", []) if att.get("email")]

        # Extract video link
        video_link = None
        conference_data = event.get("conferenceData", {})
        for entry_point in conference_data.get("entryPoints", []):
            if entry_point.get("entryPointType") == "video":
                video_link = entry_point.get("uri")
                break

        return EventSummary(
            id=event["id"],
            title=event.get("summary", "(Sans titre)"),
            starts_at=starts_at,
            ends_at=ends_at,
            timezone=timezone,
            provider=provider,
            calendar_id="primary",
            attendees=attendees,
            video_conference_link=video_link,
            html_link=event.get("htmlLink"),
            description=event.get("description"),
        )

    def _microsoft_event_to_summary(self, event: dict, provider: CalendarProvider) -> EventSummary:
        """Convert Microsoft Calendar event to EventSummary"""

        # Extract start/end times
        start = event.get("start", {})
        end = event.get("end", {})

        starts_at = self._parse_datetime(start.get("dateTime"))
        ends_at = self._parse_datetime(end.get("dateTime"))
        timezone = start.get("timeZone", "UTC")

        # Extract attendees
        attendees = [
            att.get("emailAddress", {}).get("address", "")
            for att in event.get("attendees", [])
            if att.get("emailAddress", {}).get("address")
        ]

        # Extract video link (Teams)
        video_link = event.get("onlineMeeting", {}).get("joinUrl")

        # Extract description
        body = event.get("body", {})
        description = body.get("content", "") if body.get("contentType") == "text" else None

        return EventSummary(
            id=event["id"],
            title=event.get("subject", "(Sans titre)"),
            starts_at=starts_at,
            ends_at=ends_at,
            timezone=timezone,
            provider=provider,
            calendar_id="primary",
            attendees=attendees,
            video_conference_link=video_link,
            html_link=event.get("webLink"),
            description=description,
        )

    def _parse_datetime(self, dt_str: Optional[str]) -> datetime:
        """Parse ISO datetime string"""
        if not dt_str:
            return datetime.now()

        try:
            # Handle different formats
            if "T" in dt_str:
                # ISO 8601 with time
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                # Date only (all-day event)
                from datetime import date
                d = date.fromisoformat(dt_str)
                return datetime.combine(d, datetime.min.time())
        except Exception as e:
            logger.error(f"Failed to parse datetime '{dt_str}': {e}")
            return datetime.now()
