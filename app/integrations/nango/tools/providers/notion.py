"""Notion tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "notion_search",
            "description": "Rechercher des pages et bases de données dans Notion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Notion tool via Nango proxy."""
    if tool_name == "notion_search":
        resp = await proxy.post(
            "/v1/search",
            json={"query": args["query"], "page_size": 10},
            headers={"Notion-Version": "2022-06-28"},
        )
        data = resp.json()
        results = []
        for r in data.get("results", []):
            title = ""
            if r["object"] == "page":
                props = r.get("properties", {})
                for prop in props.values():
                    if prop.get("type") == "title":
                        title_items = prop.get("title", [])
                        title = "".join(t.get("plain_text", "") for t in title_items)
                        break
            elif r["object"] == "database":
                title_items = r.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_items)

            results.append({
                "id": r["id"],
                "type": r["object"],
                "title": title,
                "url": r.get("url", ""),
            })
        return json.dumps({"results": results}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
