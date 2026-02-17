"""HubSpot CRM tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "hubspot_search_contacts",
            "description": "Rechercher des contacts dans HubSpot par nom, email ou entreprise.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche (nom, email, entreprise)",
                    },
                    "limit": {
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
            "name": "hubspot_get_deals",
            "description": "Lister les deals/opportunités HubSpot récents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
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
    {
        "type": "function",
        "function": {
            "name": "hubspot_create_contact",
            "description": "Créer un nouveau contact dans HubSpot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email du contact"},
                    "firstname": {"type": "string", "description": "Prénom"},
                    "lastname": {"type": "string", "description": "Nom"},
                    "company": {"type": "string", "description": "Entreprise"},
                    "phone": {"type": "string", "description": "Téléphone"},
                },
                "required": ["email"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a HubSpot tool via Nango proxy."""
    if tool_name == "hubspot_search_contacts":
        resp = await proxy.post(
            "/crm/v3/objects/contacts/search",
            json={
                "query": args["query"],
                "limit": args.get("limit", 5),
                "properties": ["firstname", "lastname", "email", "company", "phone"],
            },
        )
        data = resp.json()
        contacts = [
            {
                "id": r["id"],
                **{k: v for k, v in r.get("properties", {}).items()
                   if k in ("firstname", "lastname", "email", "company", "phone")},
            }
            for r in data.get("results", [])
        ]
        return json.dumps({"contacts": contacts, "total": data.get("total", 0)}, ensure_ascii=False)

    elif tool_name == "hubspot_get_deals":
        resp = await proxy.get(
            "/crm/v3/objects/deals",
            params={
                "limit": args.get("limit", 10),
                "properties": "dealname,amount,dealstage,closedate",
            },
        )
        data = resp.json()
        deals = [
            {"id": r["id"], **r.get("properties", {})}
            for r in data.get("results", [])
        ]
        return json.dumps({"deals": deals}, ensure_ascii=False)

    elif tool_name == "hubspot_create_contact":
        properties = {k: v for k, v in args.items() if v}
        resp = await proxy.post(
            "/crm/v3/objects/contacts",
            json={"properties": properties},
        )
        data = resp.json()
        return json.dumps({"created": True, "id": data["id"]}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
