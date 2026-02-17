"""Stripe tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "stripe_search_customers",
            "description": "Rechercher des clients Stripe par email ou nom.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Requête de recherche (email ou nom)",
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
            "name": "stripe_get_balance",
            "description": "Obtenir le solde du compte Stripe (disponible et en attente).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stripe_list_invoices",
            "description": "Lister les factures Stripe récentes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["draft", "open", "paid", "void", "uncollectible"],
                        "description": "Filtrer par statut",
                    },
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
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Stripe tool via Nango proxy."""
    if tool_name == "stripe_get_balance":
        resp = await proxy.get("/v1/balance")
        data = resp.json()
        available = [
            {"amount": b.get("amount", 0) / 100, "currency": b.get("currency", "")}
            for b in data.get("available", [])
        ]
        pending = [
            {"amount": b.get("amount", 0) / 100, "currency": b.get("currency", "")}
            for b in data.get("pending", [])
        ]
        return json.dumps({"available": available, "pending": pending}, ensure_ascii=False)

    elif tool_name == "stripe_search_customers":
        resp = await proxy.get(
            "/v1/customers/search",
            params={
                "query": f"name~'{args['query']}' OR email~'{args['query']}'",
                "limit": args.get("limit", 5),
            },
        )
        data = resp.json()
        customers = [
            {
                "id": c["id"],
                "name": c.get("name", ""),
                "email": c.get("email", ""),
                "created": c.get("created", 0),
                "balance": c.get("balance", 0),
                "currency": c.get("currency", ""),
            }
            for c in data.get("data", [])
        ]
        return json.dumps({"customers": customers}, ensure_ascii=False)

    elif tool_name == "stripe_list_invoices":
        params: dict = {"limit": args.get("limit", 10)}
        if args.get("status"):
            params["status"] = args["status"]

        resp = await proxy.get("/v1/invoices", params=params)
        data = resp.json()
        invoices = [
            {
                "id": inv["id"],
                "number": inv.get("number", ""),
                "customer_email": inv.get("customer_email", ""),
                "amount_due": inv.get("amount_due", 0) / 100,
                "currency": inv.get("currency", ""),
                "status": inv.get("status", ""),
                "due_date": inv.get("due_date"),
            }
            for inv in data.get("data", [])
        ]
        return json.dumps({"invoices": invoices}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
