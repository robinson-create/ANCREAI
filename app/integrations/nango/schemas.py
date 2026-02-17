"""Pydantic schemas for Nango integration."""

from pydantic import BaseModel


class NangoConnectionOut(BaseModel):
    """A Nango connection reference stored in our DB."""
    id: str
    provider: str
    nango_connection_id: str
    tenant_id: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class NangoConnectRequest(BaseModel):
    """Request to initiate an OAuth connection via Nango."""
    provider: str


class NangoConnectResponse(BaseModel):
    """Response with the Nango Connect URL for the frontend to redirect to."""
    connect_url: str
    connection_id: str
    provider: str


class NangoConnectionListResponse(BaseModel):
    """List of connections for a tenant."""
    connections: list[NangoConnectionOut]


class NangoConnectionStatus(BaseModel):
    """Status returned by Nango API for a connection."""
    id: str
    provider_config_key: str
    connection_id: str
    created_at: str
    credentials_type: str | None = None
