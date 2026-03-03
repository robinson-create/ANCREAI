"""Tenant endpoints.

All endpoints require authentication. Users can only access their own tenant.
Mutation operations (update, delete) require admin role.
Tenant creation is handled automatically at signup (see auth.py).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import AdminMember, CurrentUser, DbSession
from app.models.tenant import Tenant
from app.schemas.tenant import TenantRead, TenantUpdate

router = APIRouter()


@router.get("/me", response_model=TenantRead)
async def get_my_tenant(
    user: CurrentUser,
    db: DbSession,
) -> Tenant:
    """Get the current user's tenant."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant


@router.patch("/me", response_model=TenantRead)
async def update_my_tenant(
    data: TenantUpdate,
    admin: AdminMember,
    db: DbSession,
) -> Tenant:
    """Update the current user's tenant. Requires admin role."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == admin.tenant_id)
    )
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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_tenant(
    admin: AdminMember,
    db: DbSession,
) -> None:
    """Delete the current user's tenant and all associated data. Requires admin role."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == admin.tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Cascades to assistants, collections, documents, chunks, etc.
    await db.delete(tenant)
    await db.commit()
