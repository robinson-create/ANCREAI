"""Execute integration tools via the Nango Proxy.

Instead of fetching tokens and making direct HTTP calls, we use
Nango's proxy API which handles auth injection automatically.
"""

from __future__ import annotations

import json
import logging

from app.integrations.nango.client import nango_client
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

logger = logging.getLogger(__name__)

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


async def execute_integration_tool(
    tool_name: str,
    arguments: dict,
    provider: str,
    nango_connection_id: str,
) -> str:
    """Execute an integration tool via the Nango Proxy.

    1. Create a NangoProxy bound to the connection
    2. Call the provider-specific execute function
    3. Return the result as a string for the LLM
    """
    module = _PROVIDER_MODULES.get(provider)
    if module is None:
        return json.dumps({"error": f"Provider '{provider}' not supported"})

    try:
        proxy = nango_client.proxy(
            connection_id=nango_connection_id,
            provider_config_key=provider,
        )
        result = await module.execute(tool_name, arguments, proxy)
        return result

    except Exception as e:
        logger.error("Tool execution failed: %s/%s: %s", provider, tool_name, e)
        return json.dumps({"error": f"Tool execution failed: {e}"})
