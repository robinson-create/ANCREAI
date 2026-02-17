"""Central parsing module for normalising Gmail and Graph messages.

Providers return raw JSON; this module extracts bodies, recipients,
headers and flags into a uniform ``ParsedMessage`` dataclass.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """Normalised email message, provider-agnostic."""

    provider_message_id: str
    provider_thread_id: str | None
    internet_message_id: str | None
    sender: dict  # {"name": "...", "email": "..."}
    to_recipients: list[dict]
    cc_recipients: list[dict] | None
    bcc_recipients: list[dict] | None
    subject: str | None
    date: datetime
    snippet: str | None
    body_text: str | None
    body_html: str | None
    is_read: bool
    is_sent: bool
    is_draft: bool
    has_attachments: bool
    raw_headers: dict | None  # References, In-Reply-To


# ── Gmail helpers ──


def _gmail_get_header(headers: list[dict], name: str) -> str | None:
    """Get a header value from Gmail headers list (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value")
    return None


def _gmail_parse_address(raw: str | None) -> dict:
    """Parse 'Name <email>' into {"name": ..., "email": ...}."""
    if not raw:
        return {"name": "", "email": ""}
    raw = raw.strip()
    if "<" in raw and ">" in raw:
        name = raw[: raw.index("<")].strip().strip('"')
        email = raw[raw.index("<") + 1 : raw.index(">")].strip()
        return {"name": name, "email": email}
    return {"name": "", "email": raw}


def _gmail_parse_address_list(raw: str | None) -> list[dict]:
    """Parse comma-separated address list."""
    if not raw:
        return []
    return [_gmail_parse_address(addr) for addr in raw.split(",")]


def _gmail_extract_body(payload: dict) -> tuple[str | None, str | None]:
    """Recursively extract text/plain and text/html from Gmail payload."""
    text = None
    html = None

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if body_data:
        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        if mime_type == "text/plain":
            text = decoded
        elif mime_type == "text/html":
            html = decoded

    for part in payload.get("parts", []):
        part_text, part_html = _gmail_extract_body(part)
        if part_text and not text:
            text = part_text
        if part_html and not html:
            html = part_html

    return text, html


def _gmail_has_attachments(payload: dict) -> bool:
    """Check if the message has real attachments (not inline)."""
    for part in payload.get("parts", []):
        filename = part.get("filename")
        if filename:
            return True
        if _gmail_has_attachments(part):
            return True
    return False


def parse_gmail_message(raw: dict) -> ParsedMessage:
    """Parse a full Gmail API message object into ParsedMessage."""
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])
    label_ids = set(raw.get("labelIds", []))

    # Headers
    sender_raw = _gmail_get_header(headers, "From")
    to_raw = _gmail_get_header(headers, "To")
    cc_raw = _gmail_get_header(headers, "Cc")
    bcc_raw = _gmail_get_header(headers, "Bcc")
    subject = _gmail_get_header(headers, "Subject")
    message_id = _gmail_get_header(headers, "Message-ID") or _gmail_get_header(
        headers, "Message-Id"
    )
    in_reply_to = _gmail_get_header(headers, "In-Reply-To")
    references = _gmail_get_header(headers, "References")
    date_raw = _gmail_get_header(headers, "Date")

    # Date
    try:
        date = parsedate_to_datetime(date_raw) if date_raw else datetime.now(timezone.utc)
    except Exception:
        # Fallback to internalDate (epoch ms)
        internal_date_ms = raw.get("internalDate")
        if internal_date_ms:
            date = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
        else:
            date = datetime.now(timezone.utc)

    # Body
    body_text, body_html = _gmail_extract_body(payload)

    # Flags from labels
    is_read = "UNREAD" not in label_ids
    is_sent = "SENT" in label_ids
    is_draft = "DRAFT" in label_ids

    # Threading headers
    raw_headers_dict: dict | None = None
    if in_reply_to or references:
        raw_headers_dict = {}
        if in_reply_to:
            raw_headers_dict["In-Reply-To"] = in_reply_to
        if references:
            raw_headers_dict["References"] = references

    return ParsedMessage(
        provider_message_id=raw["id"],
        provider_thread_id=raw.get("threadId"),
        internet_message_id=message_id,
        sender=_gmail_parse_address(sender_raw),
        to_recipients=_gmail_parse_address_list(to_raw),
        cc_recipients=_gmail_parse_address_list(cc_raw) or None,
        bcc_recipients=_gmail_parse_address_list(bcc_raw) or None,
        subject=subject,
        date=date,
        snippet=raw.get("snippet"),
        body_text=body_text,
        body_html=body_html,
        is_read=is_read,
        is_sent=is_sent,
        is_draft=is_draft,
        has_attachments=_gmail_has_attachments(payload),
        raw_headers=raw_headers_dict,
    )


# ── Microsoft Graph helpers ──


def _graph_parse_address(raw: dict | None) -> dict:
    """Parse Graph emailAddress object."""
    if not raw:
        return {"name": "", "email": ""}
    ea = raw.get("emailAddress", raw)
    return {"name": ea.get("name", ""), "email": ea.get("address", "")}


def _graph_parse_address_list(raw: list[dict] | None) -> list[dict]:
    """Parse Graph recipients list."""
    if not raw:
        return []
    return [_graph_parse_address(r) for r in raw]


def parse_graph_message(raw: dict) -> ParsedMessage:
    """Parse a Microsoft Graph message object into ParsedMessage."""
    body = raw.get("body", {})
    body_content = body.get("content")
    body_type = body.get("contentType", "text").lower()

    body_text = body_content if body_type == "text" else None
    body_html = body_content if body_type == "html" else None

    # Date
    date_raw = raw.get("receivedDateTime") or raw.get("sentDateTime")
    try:
        date = datetime.fromisoformat(date_raw.replace("Z", "+00:00")) if date_raw else datetime.now(timezone.utc)
    except Exception:
        date = datetime.now(timezone.utc)

    # Threading headers
    internet_message_id = raw.get("internetMessageId")
    raw_headers_dict: dict | None = None
    internet_headers = raw.get("internetMessageHeaders", [])
    if internet_headers:
        in_reply_to = None
        references = None
        for h in internet_headers:
            name_lower = h.get("name", "").lower()
            if name_lower == "in-reply-to":
                in_reply_to = h.get("value")
            elif name_lower == "references":
                references = h.get("value")
        if in_reply_to or references:
            raw_headers_dict = {}
            if in_reply_to:
                raw_headers_dict["In-Reply-To"] = in_reply_to
            if references:
                raw_headers_dict["References"] = references

    return ParsedMessage(
        provider_message_id=raw["id"],
        provider_thread_id=raw.get("conversationId"),
        internet_message_id=internet_message_id,
        sender=_graph_parse_address(raw.get("from")),
        to_recipients=_graph_parse_address_list(raw.get("toRecipients")),
        cc_recipients=_graph_parse_address_list(raw.get("ccRecipients")) or None,
        bcc_recipients=_graph_parse_address_list(raw.get("bccRecipients")) or None,
        subject=raw.get("subject"),
        date=date,
        snippet=raw.get("bodyPreview"),
        body_text=body_text,
        body_html=body_html,
        is_read=raw.get("isRead", False),
        is_sent=raw.get("isDraft") is False
        and raw.get("from", {}).get("emailAddress", {}).get("address", "") != "",
        is_draft=raw.get("isDraft", False),
        has_attachments=raw.get("hasAttachments", False),
        raw_headers=raw_headers_dict,
    )
