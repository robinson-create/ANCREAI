"""Microsoft Graph mail provider via Nango proxy."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.services.mail.base import MailProvider, RawMessage, SendPayload, SendResult, SyncResult

logger = logging.getLogger(__name__)


class MicrosoftProvider(MailProvider):
    """Microsoft Graph implementation using Nango proxy."""

    async def get_profile(self) -> dict:
        resp = await self.proxy.get("/v1.0/me")
        data = resp.json()
        return {
            "email_address": data.get("mail") or data.get("userPrincipalName", "")
        }

    # ── Sync ──

    async def initial_sync(self, since_days: int = 30) -> SyncResult:
        """Fetch messages from the last ``since_days`` using delta queries."""
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        messages: list[RawMessage] = []
        delta_link: str | None = None

        # Use delta endpoint for initial load so we get a deltaLink
        url = "/v1.0/me/mailFolders/inbox/messages/delta"
        params: dict = {
            "$filter": f"receivedDateTime ge {since}",
            "$top": 100,
            "$select": (
                "id,conversationId,internetMessageId,subject,bodyPreview,"
                "body,from,toRecipients,ccRecipients,bccRecipients,"
                "receivedDateTime,sentDateTime,isRead,isDraft,hasAttachments,"
                "internetMessageHeaders"
            ),
        }

        while True:
            resp = await self.proxy.get(url, params=params)
            data = resp.json()

            for msg in data.get("value", []):
                messages.append(self._to_raw_message(msg))

            # Follow @odata.nextLink for pagination
            next_link = data.get("@odata.nextLink")
            if next_link:
                # Extract the relative path from full URL
                url = self._extract_path(next_link)
                params = {}
                continue

            # No more pages — get deltaLink
            delta_link = data.get("@odata.deltaLink")
            break

        # Also fetch sent items
        sent_messages = await self._fetch_folder_messages(
            "sentitems", since, limit=100
        )
        messages.extend(sent_messages)

        logger.info(
            "Graph initial_sync: %d messages (inbox + sent)", len(messages)
        )

        return SyncResult(
            messages=messages,
            cursor=delta_link,
            has_more=False,
        )

    async def incremental_sync(self, cursor: str) -> SyncResult:
        """Incremental sync using Graph delta link."""
        messages: list[RawMessage] = []
        delta_link: str | None = None

        url = self._extract_path(cursor)
        params: dict = {}

        while True:
            resp = await self.proxy.get(url, params=params)
            data = resp.json()

            for msg in data.get("value", []):
                # Delta can include @removed for deleted messages
                if "@removed" in msg:
                    continue
                messages.append(self._to_raw_message(msg))

            next_link = data.get("@odata.nextLink")
            if next_link:
                url = self._extract_path(next_link)
                params = {}
                continue

            delta_link = data.get("@odata.deltaLink")
            break

        logger.info("Graph incremental_sync: %d changed messages", len(messages))

        return SyncResult(
            messages=messages,
            cursor=delta_link,
            has_more=False,
        )

    async def fetch_thread(self, provider_thread_id: str) -> list[RawMessage]:
        """Fetch all messages with the same conversationId."""
        resp = await self.proxy.get(
            "/v1.0/me/messages",
            params={
                "$filter": f"conversationId eq '{provider_thread_id}'",
                "$orderby": "receivedDateTime asc",
                "$top": 50,
                "$select": (
                    "id,conversationId,internetMessageId,subject,bodyPreview,"
                    "body,from,toRecipients,ccRecipients,bccRecipients,"
                    "receivedDateTime,sentDateTime,isRead,isDraft,hasAttachments,"
                    "internetMessageHeaders"
                ),
            },
        )
        data = resp.json()
        return [self._to_raw_message(msg) for msg in data.get("value", [])]

    # ── Send ──

    async def send_new(self, payload: SendPayload) -> SendResult:
        body = self._build_send_body(payload)
        resp = await self.proxy.post(
            "/v1.0/me/sendMail",
            json={"message": body, "saveToSentItems": True},
        )
        # sendMail returns 202 with no body — we don't get the message ID directly.
        # We return empty and rely on post-send sync to find the message.
        return SendResult(message_id="", thread_id=None)

    async def send_reply(
        self,
        payload: SendPayload,
        thread_id: str,
        in_reply_to: str,
        references: list[str],
    ) -> SendResult:
        """Reply to an existing message.

        We first find the latest message in the thread, then use the
        ``/reply`` endpoint which handles threading automatically.
        """
        # Find the message to reply to (latest in thread)
        thread_messages = await self.fetch_thread(thread_id)
        if not thread_messages:
            # Fallback: send as new
            logger.warning(
                "No messages found for thread %s, sending as new", thread_id
            )
            return await self.send_new(payload)

        reply_to_id = thread_messages[-1].provider_message_id

        # Build the reply body
        body_content = payload.body_html or payload.body_text or ""
        content_type = "HTML" if payload.body_html else "Text"

        reply_payload: dict = {
            "message": {
                "toRecipients": [
                    {"emailAddress": {"name": r.get("name", ""), "address": r["email"]}}
                    for r in payload.to
                ],
            },
            "comment": body_content,
        }

        if payload.cc:
            reply_payload["message"]["ccRecipients"] = [
                {"emailAddress": {"name": r.get("name", ""), "address": r["email"]}}
                for r in payload.cc
            ]

        await self.proxy.post(
            f"/v1.0/me/messages/{reply_to_id}/reply",
            json=reply_payload,
        )

        # Reply endpoint returns 202 with no body
        return SendResult(message_id="", thread_id=thread_id)

    # ── Helpers ──

    async def _fetch_folder_messages(
        self, folder: str, since: str, limit: int = 100
    ) -> list[RawMessage]:
        """Fetch messages from a specific folder."""
        messages: list[RawMessage] = []
        try:
            resp = await self.proxy.get(
                f"/v1.0/me/mailFolders/{folder}/messages",
                params={
                    "$filter": f"receivedDateTime ge {since} or sentDateTime ge {since}",
                    "$top": limit,
                    "$orderby": "receivedDateTime desc",
                    "$select": (
                        "id,conversationId,internetMessageId,subject,bodyPreview,"
                        "body,from,toRecipients,ccRecipients,bccRecipients,"
                        "receivedDateTime,sentDateTime,isRead,isDraft,hasAttachments,"
                        "internetMessageHeaders"
                    ),
                },
            )
            data = resp.json()
            for msg in data.get("value", []):
                messages.append(self._to_raw_message(msg))
        except Exception as e:
            logger.warning("Failed to fetch %s folder: %s", folder, e)
        return messages

    @staticmethod
    def _to_raw_message(msg: dict) -> RawMessage:
        return RawMessage(
            provider_message_id=msg["id"],
            provider_thread_id=msg.get("conversationId"),
            internet_message_id=msg.get("internetMessageId"),
            raw_payload=msg,
        )

    @staticmethod
    def _build_send_body(payload: SendPayload) -> dict:
        """Build Graph API message body."""
        body_content = payload.body_html or payload.body_text or ""
        content_type = "HTML" if payload.body_html else "Text"

        message: dict = {
            "subject": payload.subject,
            "body": {"contentType": content_type, "content": body_content},
            "toRecipients": [
                {"emailAddress": {"name": r.get("name", ""), "address": r["email"]}}
                for r in payload.to
            ],
        }
        if payload.cc:
            message["ccRecipients"] = [
                {"emailAddress": {"name": r.get("name", ""), "address": r["email"]}}
                for r in payload.cc
            ]
        if payload.bcc:
            message["bccRecipients"] = [
                {"emailAddress": {"name": r.get("name", ""), "address": r["email"]}}
                for r in payload.bcc
            ]
        return message

    @staticmethod
    def _extract_path(full_url: str) -> str:
        """Extract relative API path from full Graph URL.

        Nango proxy expects the path part only (e.g. ``/v1.0/me/...``).
        Delta/next links may be full URLs like
        ``https://graph.microsoft.com/v1.0/me/...``.
        """
        if full_url.startswith("http"):
            # Strip scheme + host
            from urllib.parse import urlparse

            parsed = urlparse(full_url)
            path = parsed.path
            if parsed.query:
                path += "?" + parsed.query
            return path
        return full_url
