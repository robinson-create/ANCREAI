"""Slack tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "slack_search_messages",
            "description": "Rechercher des messages dans Slack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Requête de recherche Slack",
                    },
                    "count": {
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
            "name": "slack_send_message",
            "description": "Envoyer un message dans un canal Slack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Nom ou ID du canal (ex: #general, C0123456789)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Contenu du message",
                    },
                },
                "required": ["channel", "text"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Slack tool via Nango proxy."""
    if tool_name == "slack_search_messages":
        resp = await proxy.get(
            "/search.messages",
            params={"query": args["query"], "count": args.get("count", 10)},
        )
        data = resp.json()
        matches = data.get("messages", {}).get("matches", [])
        messages = [
            {
                "text": m.get("text", ""),
                "user": m.get("username", ""),
                "channel": m.get("channel", {}).get("name", ""),
                "timestamp": m.get("ts", ""),
            }
            for m in matches
        ]
        return json.dumps({"messages": messages, "total": data.get("messages", {}).get("total", 0)}, ensure_ascii=False)

    elif tool_name == "slack_send_message":
        resp = await proxy.post(
            "/chat.postMessage",
            json={"channel": args["channel"], "text": args["text"]},
        )
        data = resp.json()
        if data.get("ok"):
            return json.dumps({"sent": True, "channel": data.get("channel", ""), "ts": data.get("ts", "")}, ensure_ascii=False)
        return json.dumps({"error": data.get("error", "Unknown error")}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
