"""Gmail provider using the Gmail API via Nango proxy."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.mail.base import MailProvider, RawMessage, SendPayload, SendResult, SyncResult

logger = logging.getLogger(__name__)

# Gmail API base path (Nango prepends the base URL)
_BASE = "/gmail/v1/users/me"


class GmailProvider(MailProvider):
    """Gmail implementation using Nango proxy."""

    async def get_profile(self) -> dict:
        resp = await self.proxy.get(f"{_BASE}/profile")
        data = resp.json()
        return {"email_address": data.get("emailAddress", "")}

    # ── Sync ──

    async def initial_sync(self, since_days: int = 30) -> SyncResult:
        """Fetch messages from the last ``since_days`` days."""
        query = f"newer_than:{since_days}d"
        messages: list[RawMessage] = []

        # 1. List message IDs
        page_token: str | None = None
        all_ids: list[str] = []
        while True:
            params: dict = {"q": query, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token
            resp = await self.proxy.get(f"{_BASE}/messages", params=params)
            data = resp.json()
            for m in data.get("messages", []):
                all_ids.append(m["id"])
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info("Gmail initial_sync: found %d message IDs", len(all_ids))

        # 2. Fetch full messages (batched by 50)
        for i in range(0, len(all_ids), 50):
            batch = all_ids[i : i + 50]
            for msg_id in batch:
                try:
                    resp = await self.proxy.get(
                        f"{_BASE}/messages/{msg_id}",
                        params={"format": "full"},
                    )
                    msg_data = resp.json()
                    messages.append(
                        RawMessage(
                            provider_message_id=msg_data["id"],
                            provider_thread_id=msg_data.get("threadId"),
                            internet_message_id=None,  # parsed later
                            raw_payload=msg_data,
                        )
                    )
                except Exception as e:
                    logger.warning("Failed to fetch Gmail message %s: %s", msg_id, e)

        # 3. Get current historyId as cursor
        profile_resp = await self.proxy.get(f"{_BASE}/profile")
        history_id = str(profile_resp.json().get("historyId", ""))

        return SyncResult(messages=messages, cursor=history_id, has_more=False)

    async def incremental_sync(self, cursor: str) -> SyncResult:
        """Incremental sync using Gmail History API."""
        messages: list[RawMessage] = []
        added_ids: set[str] = set()
        updated_ids: set[str] = set()

        page_token: str | None = None
        new_history_id = cursor

        while True:
            params: dict = {
                "startHistoryId": cursor,
                "historyTypes": "messageAdded,labelAdded,labelRemoved",
                "maxResults": 100,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = await self.proxy.get(f"{_BASE}/history", params=params)
            data = resp.json()

            new_history_id = str(data.get("historyId", cursor))

            for record in data.get("history", []):
                for added in record.get("messagesAdded", []):
                    msg_id = added.get("message", {}).get("id")
                    if msg_id:
                        added_ids.add(msg_id)
                for label_added in record.get("labelsAdded", []):
                    msg_id = label_added.get("message", {}).get("id")
                    if msg_id:
                        updated_ids.add(msg_id)
                for label_removed in record.get("labelsRemoved", []):
                    msg_id = label_removed.get("message", {}).get("id")
                    if msg_id:
                        updated_ids.add(msg_id)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        # Fetch all messages that were added or had label changes
        all_ids = added_ids | updated_ids
        logger.info(
            "Gmail incremental_sync: %d added, %d label-changed",
            len(added_ids),
            len(updated_ids - added_ids),
        )

        for msg_id in all_ids:
            try:
                resp = await self.proxy.get(
                    f"{_BASE}/messages/{msg_id}",
                    params={"format": "full"},
                )
                msg_data = resp.json()
                messages.append(
                    RawMessage(
                        provider_message_id=msg_data["id"],
                        provider_thread_id=msg_data.get("threadId"),
                        internet_message_id=None,
                        raw_payload=msg_data,
                    )
                )
            except Exception as e:
                logger.warning("Failed to fetch Gmail message %s: %s", msg_id, e)

        return SyncResult(messages=messages, cursor=new_history_id, has_more=False)

    async def fetch_thread(self, provider_thread_id: str) -> list[RawMessage]:
        """Fetch all messages in a Gmail thread."""
        resp = await self.proxy.get(
            f"{_BASE}/threads/{provider_thread_id}",
            params={"format": "full"},
        )
        data = resp.json()
        messages = []
        for msg_data in data.get("messages", []):
            messages.append(
                RawMessage(
                    provider_message_id=msg_data["id"],
                    provider_thread_id=msg_data.get("threadId"),
                    internet_message_id=None,
                    raw_payload=msg_data,
                )
            )
        return messages

    # ── Send ──

    def _build_mime(
        self,
        payload: SendPayload,
        *,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> str:
        """Build a MIME message and return base64url-encoded raw string."""
        msg = MIMEMultipart("alternative")
        msg["To"] = ", ".join(
            f"{r.get('name', '')} <{r['email']}>" if r.get("name") else r["email"]
            for r in payload.to
        )
        msg["Subject"] = payload.subject

        if payload.cc:
            msg["Cc"] = ", ".join(
                f"{r.get('name', '')} <{r['email']}>" if r.get("name") else r["email"]
                for r in payload.cc
            )
        if payload.bcc:
            msg["Bcc"] = ", ".join(
                f"{r.get('name', '')} <{r['email']}>" if r.get("name") else r["email"]
                for r in payload.bcc
            )

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = " ".join(references)

        # Attach text and/or HTML parts
        if payload.body_text:
            msg.attach(MIMEText(payload.body_text, "plain", "utf-8"))
        if payload.body_html:
            msg.attach(MIMEText(payload.body_html, "html", "utf-8"))
        if not payload.body_text and not payload.body_html:
            msg.attach(MIMEText("", "plain", "utf-8"))

        return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    async def send_new(self, payload: SendPayload) -> SendResult:
        raw = self._build_mime(payload)
        resp = await self.proxy.post(
            f"{_BASE}/messages/send",
            json={"raw": raw},
        )
        data = resp.json()
        return SendResult(
            message_id=data.get("id", ""),
            thread_id=data.get("threadId"),
        )

    async def send_reply(
        self,
        payload: SendPayload,
        thread_id: str,
        in_reply_to: str,
        references: list[str],
    ) -> SendResult:
        raw = self._build_mime(
            payload, in_reply_to=in_reply_to, references=references
        )
        resp = await self.proxy.post(
            f"{_BASE}/messages/send",
            json={"raw": raw, "threadId": thread_id},
        )
        data = resp.json()
        return SendResult(
            message_id=data.get("id", ""),
            thread_id=data.get("threadId"),
        )
