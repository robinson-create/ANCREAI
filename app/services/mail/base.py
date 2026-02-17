"""Abstract mail provider interface and shared data structures."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy


@dataclass
class RawMessage:
    """Raw message returned by a provider, before normalisation."""

    provider_message_id: str
    provider_thread_id: str | None
    internet_message_id: str | None
    raw_payload: dict


@dataclass
class SendPayload:
    """Payload for sending an email."""

    to: list[dict]  # [{"name": "...", "email": "..."}]
    subject: str
    cc: list[dict] | None = None
    bcc: list[dict] | None = None
    body_text: str | None = None
    body_html: str | None = None


@dataclass
class SendResult:
    """Result from a successful send."""

    message_id: str  # provider_message_id
    thread_id: str | None = None  # provider_thread_id (may be None)


@dataclass
class SyncResult:
    """Result from a sync operation."""

    messages: list[RawMessage] = field(default_factory=list)
    cursor: str | None = None  # historyId or deltaLink
    has_more: bool = False


class MailProvider(ABC):
    """Abstract interface for a mail provider (Gmail, Microsoft, SMTP)."""

    def __init__(self, proxy: "NangoProxy | None" = None) -> None:
        self.proxy = proxy

    @abstractmethod
    async def get_profile(self) -> dict:
        """Return account profile with at least ``email_address``."""

    @abstractmethod
    async def initial_sync(self, since_days: int = 30) -> SyncResult:
        """Initial sync: fetch recent messages, return cursor."""

    @abstractmethod
    async def incremental_sync(self, cursor: str) -> SyncResult:
        """Incremental sync from cursor (historyId / deltaLink)."""

    @abstractmethod
    async def fetch_thread(self, provider_thread_id: str) -> list[RawMessage]:
        """Fetch all messages in a thread."""

    @abstractmethod
    async def send_new(self, payload: SendPayload) -> SendResult:
        """Send a new email. Returns provider_message_id + thread_id."""

    @abstractmethod
    async def send_reply(
        self,
        payload: SendPayload,
        thread_id: str,
        in_reply_to: str,
        references: list[str],
    ) -> SendResult:
        """Reply within a thread. Returns provider_message_id."""
