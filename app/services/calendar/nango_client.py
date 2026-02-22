"""
Nango Calendar Client.

Handles communication with Google Calendar and Microsoft Calendar APIs
via Nango proxy. Abstracts provider-specific differences.
"""

from typing import Optional, List
import httpx
from datetime import datetime

from app.schemas.calendar import CalendarProvider
from app.config import get_settings

settings = get_settings()


class NangoCalendarClient:
    """Client for calendar operations via Nango proxy"""

    def __init__(self):
        self.nango_url = settings.nango_url
        self.nango_secret = settings.nango_secret_key
        self.timeout = 30.0

    # ========== Public API ==========

    async def create_event(
        self,
        provider: CalendarProvider,
        nango_connection_id: str,
        event_data: dict,
        add_video: bool = False,
    ) -> dict:
        """Create a calendar event"""
        if provider == CalendarProvider.GOOGLE:
            return await self._create_google_event(nango_connection_id, event_data, add_video)
        elif provider == CalendarProvider.MICROSOFT:
            return await self._create_microsoft_event(nango_connection_id, event_data, add_video)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def update_event(
        self,
        provider: CalendarProvider,
        nango_connection_id: str,
        event_id: str,
        calendar_id: str,
        update_data: dict,
    ) -> dict:
        """Update an existing event"""
        if provider == CalendarProvider.GOOGLE:
            return await self._update_google_event(nango_connection_id, event_id, calendar_id, update_data)
        elif provider == CalendarProvider.MICROSOFT:
            return await self._update_microsoft_event(nango_connection_id, event_id, update_data)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def delete_event(
        self,
        provider: CalendarProvider,
        nango_connection_id: str,
        event_id: str,
        calendar_id: str = "primary",
    ):
        """Delete an event"""
        if provider == CalendarProvider.GOOGLE:
            await self._delete_google_event(nango_connection_id, event_id, calendar_id)
        elif provider == CalendarProvider.MICROSOFT:
            await self._delete_microsoft_event(nango_connection_id, event_id)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def list_events(
        self,
        provider: CalendarProvider,
        nango_connection_id: str,
        time_min: str,
        time_max: str,
        calendar_id: str = "primary",
        query: Optional[str] = None,
    ) -> List[dict]:
        """List events in a time range"""
        if provider == CalendarProvider.GOOGLE:
            return await self._list_google_events(nango_connection_id, time_min, time_max, calendar_id, query)
        elif provider == CalendarProvider.MICROSOFT:
            return await self._list_microsoft_events(nango_connection_id, time_min, time_max, query)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    # ========== Google Calendar ==========

    async def _create_google_event(
        self, connection_id: str, event_data: dict, add_video: bool
    ) -> dict:
        """Create Google Calendar event"""
        url = f"{self.nango_url}/proxy/google-calendar/calendar/v3/calendars/primary/events"

        params = {}
        if add_video:
            params["conferenceDataVersion"] = 1

        headers = self._get_nango_headers(connection_id, "google-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=event_data, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

        return {
            "id": result["id"],
            "calendar_id": "primary",
            "html_link": result.get("htmlLink"),
            "video_link": self._extract_google_meet_link(result),
        }

    async def _update_google_event(
        self, connection_id: str, event_id: str, calendar_id: str, update_data: dict
    ) -> dict:
        """Update Google Calendar event"""
        url = f"{self.nango_url}/proxy/google-calendar/calendar/v3/calendars/{calendar_id}/events/{event_id}"

        headers = self._get_nango_headers(connection_id, "google-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(url, json=update_data, headers=headers)
            response.raise_for_status()
            result = response.json()

        return {
            "id": result["id"],
            "html_link": result.get("htmlLink"),
            "video_link": self._extract_google_meet_link(result),
        }

    async def _delete_google_event(self, connection_id: str, event_id: str, calendar_id: str):
        """Delete Google Calendar event"""
        url = f"{self.nango_url}/proxy/google-calendar/calendar/v3/calendars/{calendar_id}/events/{event_id}"

        headers = self._get_nango_headers(connection_id, "google-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()

    async def _list_google_events(
        self,
        connection_id: str,
        time_min: str,
        time_max: str,
        calendar_id: str,
        query: Optional[str],
    ) -> List[dict]:
        """List Google Calendar events"""
        url = f"{self.nango_url}/proxy/google-calendar/calendar/v3/calendars/{calendar_id}/events"

        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 100,
        }
        if query:
            params["q"] = query

        headers = self._get_nango_headers(connection_id, "google-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

        return result.get("items", [])

    # ========== Microsoft Calendar ==========

    async def _create_microsoft_event(
        self, connection_id: str, event_data: dict, add_video: bool
    ) -> dict:
        """Create Microsoft Calendar event"""
        url = f"{self.nango_url}/proxy/microsoft-calendar/v1.0/me/events"

        # Transform Google format → Microsoft format
        ms_event = {
            "subject": event_data.get("summary", ""),
            "start": {
                "dateTime": event_data["start"]["dateTime"],
                "timeZone": event_data["start"]["timeZone"],
            },
            "end": {
                "dateTime": event_data["end"]["dateTime"],
                "timeZone": event_data["end"]["timeZone"],
            },
            "attendees": [
                {"emailAddress": {"address": att["email"]}, "type": "required"}
                for att in event_data.get("attendees", [])
            ],
            "body": {"contentType": "text", "content": event_data.get("description", "")},
        }

        if add_video:
            ms_event["isOnlineMeeting"] = True
            ms_event["onlineMeetingProvider"] = "teamsForBusiness"

        headers = self._get_nango_headers(connection_id, "microsoft-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=ms_event, headers=headers)
            response.raise_for_status()
            result = response.json()

        return {
            "id": result["id"],
            "calendar_id": "primary",
            "html_link": result.get("webLink"),
            "video_link": result.get("onlineMeeting", {}).get("joinUrl"),
        }

    async def _update_microsoft_event(
        self, connection_id: str, event_id: str, update_data: dict
    ) -> dict:
        """Update Microsoft Calendar event"""
        url = f"{self.nango_url}/proxy/microsoft-calendar/v1.0/me/events/{event_id}"

        # Transform updates
        ms_update = {}
        if "summary" in update_data:
            ms_update["subject"] = update_data["summary"]
        if "start" in update_data:
            ms_update["start"] = update_data["start"]
        if "end" in update_data:
            ms_update["end"] = update_data["end"]
        if "attendees" in update_data:
            ms_update["attendees"] = [
                {"emailAddress": {"address": att["email"]}, "type": "required"}
                for att in update_data["attendees"]
            ]

        headers = self._get_nango_headers(connection_id, "microsoft-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(url, json=ms_update, headers=headers)
            response.raise_for_status()
            result = response.json()

        return {
            "id": result["id"],
            "html_link": result.get("webLink"),
            "video_link": result.get("onlineMeeting", {}).get("joinUrl"),
        }

    async def _delete_microsoft_event(self, connection_id: str, event_id: str):
        """Delete Microsoft Calendar event"""
        url = f"{self.nango_url}/proxy/microsoft-calendar/v1.0/me/events/{event_id}"

        headers = self._get_nango_headers(connection_id, "microsoft-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()

    async def _list_microsoft_events(
        self,
        connection_id: str,
        time_min: str,
        time_max: str,
        query: Optional[str],
    ) -> List[dict]:
        """List Microsoft Calendar events"""
        url = f"{self.nango_url}/proxy/microsoft-calendar/v1.0/me/calendarView"

        params = {
            "startDateTime": time_min,
            "endDateTime": time_max,
            "$orderby": "start/dateTime",
            "$top": 100,
        }
        if query:
            params["$search"] = f'"{query}"'

        headers = self._get_nango_headers(connection_id, "microsoft-calendar")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

        return result.get("value", [])

    # ========== Helpers ==========

    def _get_nango_headers(self, connection_id: str, provider_config_key: str) -> dict:
        """Get headers for Nango proxy request"""
        return {
            "Authorization": f"Bearer {self.nango_secret}",
            "Connection-Id": connection_id,
            "Provider-Config-Key": provider_config_key,
            "Content-Type": "application/json",
        }

    def _extract_google_meet_link(self, event: dict) -> Optional[str]:
        """Extract Meet link from Google Calendar event"""
        conference_data = event.get("conferenceData", {})
        entry_points = conference_data.get("entryPoints", [])
        for entry in entry_points:
            if entry.get("entryPointType") == "video":
                return entry.get("uri")
        return None
