"""Pipedrive CRM tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "pipedrive_search_persons",
            "description": "Rechercher des personnes/contacts dans Pipedrive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Terme de recherche (nom, email, téléphone)",
                    },
                },
                "required": ["term"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipedrive_get_deals",
            "description": "Lister les deals Pipedrive avec leur statut.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "won", "lost", "all_not_deleted"],
                        "description": "Filtrer par statut (défaut: open)",
                        "default": "open",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Nombre max de résultats",
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
    """Execute a Pipedrive tool via Nango proxy."""
    if tool_name == "pipedrive_search_persons":
        resp = await proxy.get(
            "/persons/search",
            params={"term": args["term"], "limit": 10},
        )
        data = resp.json()
        items = data.get("data", {}).get("items", [])
        persons = [
            {
                "id": item["item"]["id"],
                "name": item["item"].get("name", ""),
                "email": item["item"].get("primary_email", ""),
                "organization": item["item"].get("organization", {}).get("name", ""),
            }
            for item in items
        ]
        return json.dumps({"persons": persons}, ensure_ascii=False)

    elif tool_name == "pipedrive_get_deals":
        resp = await proxy.get(
            "/deals",
            params={
                "status": args.get("status", "open"),
                "limit": args.get("limit", 10),
            },
        )
        data = resp.json()
        deals = [
            {
                "id": d["id"],
                "title": d.get("title", ""),
                "value": d.get("value", 0),
                "currency": d.get("currency", ""),
                "status": d.get("status", ""),
                "stage": d.get("stage_id", ""),
                "person": d.get("person_name", ""),
            }
            for d in (data.get("data") or [])
        ]
        return json.dumps({"deals": deals}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
