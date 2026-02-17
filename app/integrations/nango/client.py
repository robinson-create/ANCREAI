"""HTTP client for Nango API.

Nango manages OAuth tokens and provides a REST API to:
- Create connections (initiate OAuth flows)
- List connections
- Proxy API calls (Nango injects auth headers automatically)

We never store OAuth tokens ourselves. Nango handles token refresh
and storage. We only store a reference (connection_id + provider)
in our DB linked to the tenant.

For calling provider APIs we use the **Nango Proxy**::

    proxy = nango_client.proxy(connection_id, provider_config_key)
    resp = await proxy.get("/crm/v3/objects/deals")

Nango resolves the base URL and injects the correct auth.
"""

from __future__ import annotations

import httpx

from app.config import get_settings


class NangoProxy:
    """Pre-bound proxy for a specific Nango connection.

    All HTTP calls go through ``{NANGO_URL}/proxy/{endpoint}`` with the
    ``Connection-Id`` and ``Provider-Config-Key`` headers.  Nango adds
    the provider base URL and OAuth token automatically.

    Usage in provider modules::

        async def execute(tool_name, args, proxy: NangoProxy) -> str:
            resp = await proxy.get("/crm/v3/objects/deals", params={"limit": 10})
            data = resp.json()
    """

    def __init__(
        self,
        base_url: str,
        secret_key: str,
        connection_id: str,
        provider_config_key: str,
    ) -> None:
        self._base_url = base_url
        self._secret_key = secret_key
        self.connection_id = connection_id
        self.provider_config_key = provider_config_key

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Connection-Id": self.connection_id,
            "Provider-Config-Key": self.provider_config_key,
        }

    async def get(
        self,
        endpoint: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """GET through Nango proxy."""
        h = {**self._headers, **(headers or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/proxy{endpoint}",
                headers=h,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp

    async def post(
        self,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """POST through Nango proxy."""
        h = {**self._headers, "Content-Type": "application/json", **(headers or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/proxy{endpoint}",
                headers=h,
                json=json,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp

    async def put(
        self,
        endpoint: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """PUT through Nango proxy."""
        h = {**self._headers, "Content-Type": "application/json", **(headers or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base_url}/proxy{endpoint}",
                headers=h,
                json=json,
                timeout=30,
            )
            resp.raise_for_status()
            return resp

    async def delete(
        self,
        endpoint: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """DELETE through Nango proxy."""
        h = {**self._headers, **(headers or {})}
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base_url}/proxy{endpoint}",
                headers=h,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp


class NangoClient:
    """Async HTTP client for the Nango REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.nango_url.rstrip("/")
        self.secret_key = settings.nango_secret_key
        self.public_key = settings.nango_public_key

    def proxy(
        self,
        connection_id: str,
        provider_config_key: str,
    ) -> NangoProxy:
        """Return a :class:`NangoProxy` bound to *connection_id*."""
        return NangoProxy(
            base_url=self.base_url,
            secret_key=self.secret_key,
            connection_id=connection_id,
            provider_config_key=provider_config_key,
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def get_oauth_connect_url(
        self,
        provider_config_key: str,
        connection_id: str,
    ) -> str:
        """Build the Nango OAuth redirect URL.

        In Nango v0.36 the flow is a simple redirect:
        ``{NANGO_URL}/oauth/connect/{provider_config_key}?connection_id={connection_id}``

        Nango handles the full OAuth dance and redirects back to its
        own callback URL.
        """
        return (
            f"{self.base_url}/oauth/connect/{provider_config_key}"
            f"?connection_id={connection_id}"
            f"&public_key={self.public_key}"
        )

    async def list_connections(self, connection_id: str | None = None) -> list[dict]:
        """List connections, optionally filtered by connection_id.

        Nango v0.36 endpoint: ``GET /api/v1/connection``
        """
        params: dict[str, str] = {}
        if connection_id:
            params["connectionId"] = connection_id

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/connection",
                headers=self._headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("connections", [])

    async def get_connection(
        self,
        provider_config_key: str,
        connection_id: str,
    ) -> dict:
        """Get details of a specific connection.

        Nango v0.36 endpoint: ``GET /api/v1/connection/{connection_id}``
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/connection/{connection_id}",
                headers=self._headers,
                params={"provider_config_key": provider_config_key},
            )
            response.raise_for_status()
            return response.json()

    async def delete_connection(
        self,
        provider_config_key: str,
        connection_id: str,
    ) -> None:
        """Delete a connection.

        Nango v0.36 endpoint: ``DELETE /api/v1/connection/{connection_id}``
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/connection/{connection_id}",
                headers=self._headers,
                params={"provider_config_key": provider_config_key},
            )
            response.raise_for_status()


# Global instance
nango_client = NangoClient()
