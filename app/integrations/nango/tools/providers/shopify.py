"""Shopify tools.

Shopify URLs are shop-specific but the Nango proxy resolves them
automatically from the connection metadata — no hardcoded domain.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.nango.client import NangoProxy

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "shopify_search_orders",
            "description": "Rechercher les commandes Shopify récentes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "cancelled", "any"],
                        "description": "Filtrer par statut (défaut: any)",
                        "default": "any",
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
    {
        "type": "function",
        "function": {
            "name": "shopify_get_products",
            "description": "Lister les produits du catalogue Shopify.",
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
            "name": "shopify_search_customers",
            "description": "Rechercher des clients Shopify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Terme de recherche (nom, email)",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


async def execute(tool_name: str, args: dict, proxy: NangoProxy) -> str:
    """Execute a Shopify tool via Nango proxy."""
    if tool_name == "shopify_search_orders":
        resp = await proxy.get(
            "/admin/api/2024-01/orders.json",
            params={
                "status": args.get("status", "any"),
                "limit": args.get("limit", 10),
            },
        )
        data = resp.json()
        orders = [
            {
                "id": o["id"],
                "name": o.get("name", ""),
                "total_price": o.get("total_price", ""),
                "currency": o.get("currency", ""),
                "status": o.get("financial_status", ""),
                "customer": o.get("customer", {}).get("email", ""),
                "created_at": o.get("created_at", ""),
            }
            for o in data.get("orders", [])
        ]
        return json.dumps({"orders": orders}, ensure_ascii=False)

    elif tool_name == "shopify_get_products":
        resp = await proxy.get(
            "/admin/api/2024-01/products.json",
            params={"limit": args.get("limit", 10)},
        )
        data = resp.json()
        products = [
            {
                "id": p["id"],
                "title": p.get("title", ""),
                "status": p.get("status", ""),
                "vendor": p.get("vendor", ""),
                "variants_count": len(p.get("variants", [])),
            }
            for p in data.get("products", [])
        ]
        return json.dumps({"products": products}, ensure_ascii=False)

    elif tool_name == "shopify_search_customers":
        resp = await proxy.get(
            "/admin/api/2024-01/customers/search.json",
            params={"query": args["query"]},
        )
        data = resp.json()
        customers = [
            {
                "id": c["id"],
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "email": c.get("email", ""),
                "orders_count": c.get("orders_count", 0),
                "total_spent": c.get("total_spent", ""),
            }
            for c in data.get("customers", [])
        ]
        return json.dumps({"customers": customers}, ensure_ascii=False)

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
