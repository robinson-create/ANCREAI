"""Factory for mail provider instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.mail.base import MailProvider
from app.services.mail.gmail import GmailProvider
from app.services.mail.microsoft import MicrosoftProvider
from app.services.mail.smtp import SMTPProvider

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy


def get_mail_provider(
    provider: str,
    proxy: "NangoProxy | None" = None,
    *,
    smtp_config: dict | None = None,
) -> MailProvider:
    """Create the right MailProvider implementation for a given provider name."""
    if provider == "gmail":
        if not proxy:
            raise ValueError("Gmail provider requires Nango proxy")
        return GmailProvider(proxy)
    if provider == "microsoft":
        if not proxy:
            raise ValueError("Microsoft provider requires Nango proxy")
        return MicrosoftProvider(proxy)
    if provider == "smtp":
        if not smtp_config:
            raise ValueError("SMTP provider requires smtp_config")
        return SMTPProvider(smtp_config, proxy=proxy)
    raise ValueError(f"Unknown mail provider: {provider}")
