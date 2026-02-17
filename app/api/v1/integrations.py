"""Nango integration endpoints.

These endpoints manage OAuth connections via Nango:
- Initiate OAuth connection flow
- List active connections for a tenant
- Handle OAuth callback (if needed)

All endpoints enforce multi-tenant isolation: a user can only
see/manage connections belonging to their tenant.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.integrations.nango.client import nango_client
from app.integrations.nango.models import NangoConnection
from app.integrations.nango.schemas import (
    NangoConnectResponse,
    NangoConnectionListResponse,
    NangoConnectionOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/nango/connect/{provider}", response_model=NangoConnectResponse)
async def initiate_nango_connection(
    provider: str,
    user: CurrentUser,
    db: DbSession,
) -> NangoConnectResponse:
    """Initiate an OAuth connection via Nango.

    Creates a Nango connect session and returns a URL/token that the
    frontend uses to open the OAuth popup or redirect.

    The connection_id is scoped to the tenant: "{tenant_id}:{provider}"
    so each tenant has isolated connections.
    """
    tenant_id = user.tenant_id
    connection_id = f"{tenant_id}:{provider}"

    # Check if connection already exists for this tenant + provider
    result = await db.execute(
        select(NangoConnection).where(
            NangoConnection.tenant_id == tenant_id,
            NangoConnection.provider == provider,
        )
    )
    existing = result.scalar_one_or_none()

    # Store or update connection reference in our DB
    # Allow reconnection even if status is "connected" (user may want to re-auth)
    if existing:
        existing.status = "pending"
    else:
        connection = NangoConnection(
            id=uuid4(),
            tenant_id=tenant_id,
            provider=provider,
            nango_connection_id=connection_id,
            status="pending",
        )
        db.add(connection)

    await db.flush()

    # Build the direct OAuth redirect URL (Nango v0.36)
    connect_url = nango_client.get_oauth_connect_url(
        provider_config_key=provider,
        connection_id=connection_id,
    )

    return NangoConnectResponse(
        connect_url=connect_url,
        connection_id=connection_id,
        provider=provider,
    )


@router.get("/nango/callback")
async def nango_callback(
    providerConfigKey: str = "",
    connectionId: str = "",
    user: CurrentUser = None,  # type: ignore[assignment]
    db: DbSession = None,  # type: ignore[assignment]
) -> dict:
    """Handle Nango OAuth callback.

    Nango typically handles the callback itself and stores the tokens.
    This endpoint is called by our frontend after the Nango popup closes
    to update the connection status in our DB.

    Note: If using Nango's hosted callback, this endpoint may not be needed.
    We include it for completeness and to update our local connection state.
    """
    if not connectionId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connectionId is required",
        )

    tenant_id = user.tenant_id

    # Verify the connection belongs to this tenant
    result = await db.execute(
        select(NangoConnection).where(
            NangoConnection.nango_connection_id == connectionId,
            NangoConnection.tenant_id == tenant_id,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found for this tenant",
        )

    # Update status to connected
    connection.status = "connected"
    await db.flush()

    return {"status": "connected", "provider": connection.provider}


@router.get("/nango/connections", response_model=NangoConnectionListResponse)
async def list_nango_connections(
    user: CurrentUser,
    db: DbSession,
) -> NangoConnectionListResponse:
    """List all Nango connections for the current tenant.

    Returns connections stored in our DB (not querying Nango directly).
    This ensures multi-tenant isolation since we only return connections
    associated with the user's tenant.
    """
    tenant_id = user.tenant_id

    result = await db.execute(
        select(NangoConnection)
        .where(NangoConnection.tenant_id == tenant_id)
        .order_by(NangoConnection.created_at.desc())
    )
    connections = result.scalars().all()

    return NangoConnectionListResponse(
        connections=[
            NangoConnectionOut(
                id=str(c.id),
                provider=c.provider,
                nango_connection_id=c.nango_connection_id,
                tenant_id=str(c.tenant_id),
                status=c.status,
                created_at=c.created_at.isoformat(),
            )
            for c in connections
        ]
    )


@router.delete("/nango/connections/{provider}")
async def delete_nango_connection(
    provider: str,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete a Nango connection for the current tenant.

    Removes the connection from both our DB and Nango.
    """
    tenant_id = user.tenant_id

    result = await db.execute(
        select(NangoConnection).where(
            NangoConnection.tenant_id == tenant_id,
            NangoConnection.provider == provider,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {provider} connection found for this tenant",
        )

    # Try to delete from Nango too
    try:
        await nango_client.delete_connection(
            provider_config_key=provider,
            connection_id=connection.nango_connection_id,
        )
    except Exception as e:
        logger.warning(f"Failed to delete connection from Nango: {e}")

    await db.delete(connection)
    await db.flush()

    return {"status": "deleted", "provider": provider}
