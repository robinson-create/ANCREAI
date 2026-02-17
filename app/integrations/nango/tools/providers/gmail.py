"""Gmail tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "gmail_search_emails",
            "description": "Rechercher des emails dans Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Requête de recherche Gmail (ex: 'from:john subject:meeting')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre max de résultats (défaut: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_send_email",
            "description": "Envoyer un email via Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Adresse email du destinataire"},
                    "subject": {"type": "string", "description": "Sujet de l'email"},
                    "body": {"type": "string", "description": "Corps de l'email (texte brut)"},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Gmail tool via Nango proxy."""
    if tool_name == "gmail_search_emails":
        # Search for message IDs
        resp = await proxy.get(
            "/gmail/v1/users/me/messages",
            params={"q": args["query"], "maxResults": args.get("max_results", 5)},
        )
        data = resp.json()
        messages_meta = data.get("messages", [])

        # Fetch details for each message
        emails = []
        for msg_meta in messages_meta[:5]:
            msg_resp = await proxy.get(
                f"/gmail/v1/users/me/messages/{msg_meta['id']}",
                params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
            )
            msg_data = msg_resp.json()
            headers_list = msg_data.get("payload", {}).get("headers", [])
            email_info = {"id": msg_data["id"], "snippet": msg_data.get("snippet", "")}
            for h in headers_list:
                email_info[h["name"].lower()] = h["value"]
            emails.append(email_info)

        return json.dumps({"emails": emails, "total": data.get("resultSizeEstimate", 0)}, ensure_ascii=False)

    elif tool_name == "gmail_send_email":
        import base64

        raw_message = f"To: {args['to']}\r\nSubject: {args['subject']}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{args['body']}"
        encoded = base64.urlsafe_b64encode(raw_message.encode()).decode()

        resp = await proxy.post(
            "/gmail/v1/users/me/messages/send",
            json={"raw": encoded},
        )
        data = resp.json()
        return json.dumps({"sent": True, "message_id": data.get("id", "")}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
