"""Factory for mail provider instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.mail.base import MailProvider
from app.services.mail.gmail import GmailProvider
from app.services.mail.microsoft import MicrosoftProvider

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy


def get_mail_provider(provider: str, proxy: NangoProxy) -> MailProvider:
    """Create the right MailProvider implementation for a given provider name."""
    if provider == "gmail":
        return GmailProvider(proxy)
    if provider == "microsoft":
        return MicrosoftProvider(proxy)
    raise ValueError(f"Unknown mail provider: {provider}")
