"""Outlook (Microsoft Graph) tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "outlook_search_emails",
            "description": "Rechercher des emails dans Outlook / Office 365.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche (sujet, expéditeur, contenu)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre max de résultats (défaut: 10)",
                        "default": 10,
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
            "name": "outlook_send_email",
            "description": "Envoyer un email via Outlook / Office 365.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Adresse email du destinataire"},
                    "subject": {"type": "string", "description": "Sujet de l'email"},
                    "body": {"type": "string", "description": "Corps de l'email (texte ou HTML)"},
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_list_events",
            "description": "Lister les événements du calendrier Outlook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre max de résultats (défaut: 10)",
                        "default": 10,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute an Outlook tool via Nango proxy (Microsoft Graph API)."""
    if tool_name == "outlook_search_emails":
        query = args["query"]
        max_results = args.get("max_results", 10)
        resp = await proxy.get(
            "/v1.0/me/messages",
            params={
                "$search": f'"{query}"',
                "$top": max_results,
                "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead",
                "$orderby": "receivedDateTime desc",
            },
        )
        data = resp.json()
        emails = [
            {
                "id": msg["id"],
                "subject": msg.get("subject", ""),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "from_name": msg.get("from", {}).get("emailAddress", {}).get("name", ""),
                "date": msg.get("receivedDateTime", ""),
                "preview": msg.get("bodyPreview", ""),
                "is_read": msg.get("isRead", False),
            }
            for msg in data.get("value", [])
        ]
        return json.dumps({"emails": emails, "count": len(emails)}, ensure_ascii=False)

    elif tool_name == "outlook_send_email":
        resp = await proxy.post(
            "/v1.0/me/sendMail",
            json={
                "message": {
                    "subject": args["subject"],
                    "body": {
                        "contentType": "HTML",
                        "content": args["body"],
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": args["to"],
                            }
                        }
                    ],
                },
                "saveToSentItems": True,
            },
        )
        # sendMail returns 202 Accepted with no body
        return json.dumps({"sent": True, "to": args["to"]}, ensure_ascii=False)

    elif tool_name == "outlook_list_events":
        max_results = args.get("max_results", 10)
        resp = await proxy.get(
            "/v1.0/me/events",
            params={
                "$top": max_results,
                "$select": "id,subject,start,end,location,organizer,isAllDay",
                "$orderby": "start/dateTime desc",
            },
        )
        data = resp.json()
        events = [
            {
                "id": evt["id"],
                "subject": evt.get("subject", ""),
                "start": evt.get("start", {}).get("dateTime", ""),
                "end": evt.get("end", {}).get("dateTime", ""),
                "location": evt.get("location", {}).get("displayName", ""),
                "organizer": evt.get("organizer", {}).get("emailAddress", {}).get("name", ""),
                "all_day": evt.get("isAllDay", False),
            }
            for evt in data.get("value", [])
        ]
        return json.dumps({"events": events, "count": len(events)}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
