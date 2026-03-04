"""Tenant endpoints.

All endpoints require authentication. Users can only access their own tenant.
Mutation operations (update, delete) require admin role.
Tenant creation is handled automatically at signup (see auth.py).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import AdminMember, CurrentUser, DbSession
from app.models.assistant import Assistant
from app.models.collection import Collection
from app.models.enums import MemberStatus
from app.models.org_member import OrgMember
from app.models.tenant import Tenant
from app.schemas.tenant import TenantRead, TenantReadWithMeta, TenantStats, TenantUpdate
from app.services.quota import quota_service

router = APIRouter()


async def _enrich_tenant(tenant: Tenant, db: DbSession) -> dict:
    """Build a TenantReadWithMeta-compatible dict from tenant + DB queries."""
    # Member count (non-inactive)
    member_count_result = await db.execute(
        select(func.count(OrgMember.id)).where(
            OrgMember.tenant_id == tenant.id,
            OrgMember.status != MemberStatus.INACTIVE.value,
        )
    )
    member_count = member_count_result.scalar_one()

    # Subscription
    subscription = await quota_service.get_subscription_for_tenant(db, tenant.id)
    plan = subscription.plan if subscription else "free"
    is_pro = subscription.is_pro if subscription else False

    features = (tenant.settings or {}).get("features", {})

    return {
        **TenantRead.model_validate(tenant).model_dump(),
        "member_count": member_count,
        "plan": plan,
        "is_pro": is_pro,
        "features": features,
    }


@router.get("/me", response_model=TenantReadWithMeta)
async def get_my_tenant(
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get the current user's tenant with metadata."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return await _enrich_tenant(tenant, db)


@router.patch("/me", response_model=TenantReadWithMeta)
async def update_my_tenant(
    data: TenantUpdate,
    user: CurrentUser,
    admin: AdminMember,
    db: DbSession,
) -> dict:
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

    # Smart merge for settings.features (don't overwrite the entire dict)
    if "settings" in update_data and update_data["settings"] is not None:
        current_settings = dict(tenant.settings) if tenant.settings else {}
        new_settings = update_data.pop("settings")

        if "features" in new_settings:
            current_features = current_settings.get("features", {})
            current_features.update(new_settings.pop("features"))
            new_settings["features"] = current_features

        current_settings.update(new_settings)
        tenant.settings = current_settings

    for key, value in update_data.items():
        setattr(tenant, key, value)

    await db.commit()
    await db.refresh(tenant)

    return await _enrich_tenant(tenant, db)


@router.get("/me/stats", response_model=TenantStats)
async def get_tenant_stats(
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> TenantStats:
    """Get detailed organization stats. Requires admin role."""
    tenant_id = user.tenant_id

    # Member counts
    members_result = await db.execute(
        select(func.count(OrgMember.id)).where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.status != MemberStatus.INACTIVE.value,
        )
    )
    active_result = await db.execute(
        select(func.count(OrgMember.id)).where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.status == MemberStatus.ACTIVE.value,
        )
    )
    invited_result = await db.execute(
        select(func.count(OrgMember.id)).where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.status == MemberStatus.INVITED.value,
        )
    )

    # Assistants
    assistants_result = await db.execute(
        select(func.count(Assistant.id)).where(
            Assistant.tenant_id == tenant_id,
        )
    )

    # Documents
    documents_count = await quota_service.get_document_count(db, tenant_id)

    # Collections
    collections_result = await db.execute(
        select(func.count(Collection.id)).where(
            Collection.tenant_id == tenant_id,
        )
    )

    # Subscription
    subscription = await quota_service.get_subscription_for_tenant(db, tenant_id)
    plan = subscription.plan if subscription else "free"
    is_pro = subscription.is_pro if subscription else False
    max_seats = subscription.max_seats if subscription else 1
    max_assistants = subscription.max_assistants if subscription else 1

    # Features
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one()
    features = (tenant.settings or {}).get("features", {})

    return TenantStats(
        members_count=members_result.scalar_one(),
        active_members_count=active_result.scalar_one(),
        invited_members_count=invited_result.scalar_one(),
        assistants_count=assistants_result.scalar_one(),
        documents_count=documents_count,
        collections_count=collections_result.scalar_one(),
        plan=plan,
        is_pro=is_pro,
        max_seats=max_seats,
        max_assistants=max_assistants,
        features=features,
    )


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
