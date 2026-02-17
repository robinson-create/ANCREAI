"""SMTP mail provider for sending via any SMTP server.

Supports Gmail (smtp.gmail.com), Outlook (smtp.office365.com),
or custom SMTP servers. No OAuth, no inbox sync — send only.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

from app.services.mail.base import (
    MailProvider,
    RawMessage,
    SendPayload,
    SendResult,
    SyncResult,
)

logger = logging.getLogger(__name__)


def verify_smtp_connection(
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool = True,
) -> bool:
    """Test SMTP connection and login. Returns True on success."""
    try:
        smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp_class(host, port, timeout=10) as server:
            if port != 465 and use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
        return True
    except Exception as e:
        logger.warning("SMTP verification failed: %s", e)
        return False


class SMTPProvider(MailProvider):
    """SMTP implementation — send only, no sync."""

    def __init__(self, smtp_config: dict, proxy=None) -> None:
        super().__init__(proxy)
        self.config = smtp_config

    async def get_profile(self) -> dict:
        """Return email from config."""
        return {"email_address": self.config.get("user", "")}

    async def initial_sync(self, since_days: int = 30) -> SyncResult:
        """SMTP has no inbox API."""
        return SyncResult(messages=[], cursor=None, has_more=False)

    async def incremental_sync(self, cursor: str) -> SyncResult:
        """SMTP has no inbox API."""
        return SyncResult(messages=[], cursor=None, has_more=False)

    async def fetch_thread(self, provider_thread_id: str) -> list[RawMessage]:
        """SMTP has no inbox API."""
        return []

    def _build_mime(
        self,
        payload: SendPayload,
        *,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> tuple[MIMEMultipart, str]:
        """Build MIME message. Returns (msg, from_addr)."""
        msg = MIMEMultipart("alternative")
        from_email = self.config.get("user", "")
        msg["From"] = from_email
        msg["To"] = ", ".join(
            formataddr((r.get("name", "") or "", r["email"])) if r.get("name") else r["email"]
            for r in payload.to
        )
        msg["Subject"] = payload.subject

        if payload.cc:
            msg["Cc"] = ", ".join(
                formataddr((r.get("name", "") or "", r["email"])) if r.get("name") else r["email"]
                for r in payload.cc
            )
        if payload.bcc:
            msg["Bcc"] = ", ".join(
                formataddr((r.get("name", "") or "", r["email"])) if r.get("name") else r["email"]
                for r in payload.bcc
            )

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = " ".join(references)

        if payload.body_text:
            msg.attach(MIMEText(payload.body_text, "plain", "utf-8"))
        if payload.body_html:
            msg.attach(MIMEText(payload.body_html, "html", "utf-8"))
        if not payload.body_text and not payload.body_html:
            msg.attach(MIMEText("", "plain", "utf-8"))

        return msg, from_email

    async def send_new(self, payload: SendPayload) -> SendResult:
        """Send via SMTP."""
        msg, from_addr = self._build_mime(payload)
        # Generate Message-ID for tracking
        msg["Message-ID"] = make_msgid(domain="ancre.local")

        host = self.config["host"]
        port = int(self.config.get("port", 587))
        user = self.config["user"]
        password = self._get_password()

        all_recipients = [r["email"] for r in payload.to]
        if payload.cc:
            all_recipients.extend(r["email"] for r in payload.cc)
        if payload.bcc:
            all_recipients.extend(r["email"] for r in payload.bcc)

        def _send() -> str | None:
            use_tls = self.config.get("use_tls", True)
            smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
            with smtp_class(host, port) as server:
                if port != 465 and use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.sendmail(from_addr, all_recipients, msg.as_string())
                # SMTP doesn't return a message ID; use our generated one
                return msg["Message-ID"]

        msg_id = await self._run_sync(_send)
        return SendResult(message_id=msg_id or "", thread_id=None)

    async def send_reply(
        self,
        payload: SendPayload,
        thread_id: str,
        in_reply_to: str,
        references: list[str],
    ) -> SendResult:
        """Reply with In-Reply-To and References headers."""
        msg, from_addr = self._build_mime(
            payload, in_reply_to=in_reply_to, references=references
        )
        msg["Message-ID"] = make_msgid(domain="ancre.local")

        host = self.config["host"]
        port = int(self.config.get("port", 587))
        user = self.config["user"]
        password = self._get_password()

        all_recipients = [r["email"] for r in payload.to]
        if payload.cc:
            all_recipients.extend(r["email"] for r in payload.cc)
        if payload.bcc:
            all_recipients.extend(r["email"] for r in payload.bcc)

        def _send() -> str | None:
            use_tls = self.config.get("use_tls", True)
            smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
            with smtp_class(host, port) as server:
                if port != 465 and use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.sendmail(from_addr, all_recipients, msg.as_string())
                return msg["Message-ID"]

        msg_id = await self._run_sync(_send)
        return SendResult(message_id=msg_id or "", thread_id=None)

    def _get_password(self) -> str:
        """Decrypt and return the SMTP password."""
        from app.core.smtp_crypto import decrypt_smtp_password

        enc = self.config.get("password_encrypted")
        if not enc:
            return ""
        return decrypt_smtp_password(enc) or ""

    async def _run_sync(self, fn):
        """Run blocking SMTP call in executor to avoid blocking event loop."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn)
