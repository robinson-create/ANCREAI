"""Registry mapping provider keys to their OpenAI tool definitions.

Each provider module exposes:
- TOOLS: list of OpenAI function-calling tool dicts
- execute(tool_name, args, access_token) -> str
"""

from __future__ import annotations

from app.integrations.nango.tools.providers import (
    hubspot,
    pipedrive,
    gmail,
    shopify,
    stripe_provider,
    notion,
    slack,
    google_drive,
    outlook,
)

# Map provider key → module
_PROVIDER_MODULES = {
    "hubspot": hubspot,
    "pipedrive": pipedrive,
    "gmail": gmail,
    "shopify": shopify,
    "stripe": stripe_provider,
    "notion": notion,
    "slack": slack,
    "google-drive": google_drive,
    "outlook": outlook,
}


def get_tools_for_provider(provider: str) -> list[dict]:
    """Return OpenAI tool definitions for a provider."""
    module = _PROVIDER_MODULES.get(provider)
    if module is None:
        return []
    return module.TOOLS


def get_all_tool_names_for_provider(provider: str) -> list[str]:
    """Return all tool function names for a provider."""
    return [
        t["function"]["name"]
        for t in get_tools_for_provider(provider)
    ]


def find_provider_for_tool(tool_name: str) -> str | None:
    """Find which provider owns a given tool name."""
    for provider, module in _PROVIDER_MODULES.items():
        for tool in module.TOOLS:
            if tool["function"]["name"] == tool_name:
                return provider
    return None
