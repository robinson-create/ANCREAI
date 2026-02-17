"""
Calendar services package.

Services:
- nango_client: Interface with Nango proxy for Google/Microsoft APIs
- intent_service: Parse user text into structured commands (LLM-powered)
- executor_service: Execute calendar commands (CRUD operations)
- provider_service: List/find/search events across providers
"""

from app.services.calendar.nango_client import NangoCalendarClient
from app.services.calendar.intent_service import CalendarIntentService
from app.services.calendar.executor_service import CalendarExecutorService
from app.services.calendar.provider_service import CalendarProviderService

__all__ = [
    "NangoCalendarClient",
    "CalendarIntentService",
    "CalendarExecutorService",
    "CalendarProviderService",
]
