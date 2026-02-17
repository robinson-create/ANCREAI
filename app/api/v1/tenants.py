"""Tenant endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DbSession
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate

router = APIRouter()


@router.get("", response_model=list[TenantRead])
async def list_tenants(
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[Tenant]:
    """List all tenants."""
    result = await db.execute(
        select(Tenant)
        .order_by(Tenant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: UUID,
    db: DbSession,
) -> Tenant:
    """Get a specific tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    return tenant


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    db: DbSession,
) -> Tenant:
    """Create a new tenant."""
    tenant = Tenant(
        name=data.name,
        settings=data.settings,
        max_assistants=data.max_assistants,
        max_ingestion_tokens=data.max_ingestion_tokens,
        max_chat_tokens=data.max_chat_tokens,
        max_storage_bytes=data.max_storage_bytes,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    db: DbSession,
) -> Tenant:
    """Update a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)
    
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: DbSession,
) -> None:
    """Delete a tenant and all associated data."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    # Note: This cascades to assistants, collections, documents, etc.
    await db.delete(tenant)
    await db.commit()
