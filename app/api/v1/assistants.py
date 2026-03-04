"""Assistant endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminMember, CurrentMember, CurrentUser, DbSession, check_assistant_access
from app.integrations.nango.models import NangoConnection
from app.models.assistant import Assistant
from app.models.assistant_permission import AssistantPermission
from app.models.collection import Collection
from app.models.enums import MemberStatus
from app.models.org_member import OrgMember
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.schemas.assistant import (
    AssistantCreate,
    AssistantRead,
    AssistantReadWithCollections,
    AssistantUpdate,
)
from app.schemas.member import PermissionAdd, PermissionBulkSet, PermissionMemberRead
from app.services.quota import quota_service

router = APIRouter()

# Plan limits for assistants
ASSISTANT_LIMITS = {
    SubscriptionPlan.FREE.value: 1,
    SubscriptionPlan.PRO.value: 3,
}

MAX_INTEGRATIONS_PER_ASSISTANT = 2


def _serialize_assistant(assistant: Assistant) -> dict:
    """Serialize an assistant with its collections and integrations."""
    return {
        **AssistantRead.model_validate(assistant).model_dump(),
        "collection_ids": [c.id for c in assistant.collections],
        "integration_ids": [i.id for i in assistant.integrations],
    }


def _assistant_query():
    """Base query for assistants with eager-loaded relations."""
    return (
        select(Assistant)
        .options(
            selectinload(Assistant.collections),
            selectinload(Assistant.integrations),
        )
    )


@router.get("", response_model=list[AssistantReadWithCollections])
async def list_assistants(
    user: CurrentUser,
    member: CurrentMember,
    db: DbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List assistants for tenant with their collections and integrations.

    Admins see all assistants. Members only see those they have permission for.
    """
    query = (
        _assistant_query()
        .where(Assistant.tenant_id == user.tenant_id)
    )

    # Non-admin members: filter by AssistantPermission
    if not member.is_admin:
        query = (
            query
            .join(AssistantPermission, AssistantPermission.assistant_id == Assistant.id)
            .where(AssistantPermission.member_id == member.id)
        )

    result = await db.execute(
        query
        .order_by(Assistant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    assistants = result.scalars().all()
    return [_serialize_assistant(a) for a in assistants]


@router.get("/{assistant_id}", response_model=AssistantReadWithCollections)
async def get_assistant(
    assistant_id: UUID,
    user: CurrentUser,
    member: CurrentMember,
    db: DbSession,
) -> dict:
    """Get a specific assistant with its collections and integrations."""
    result = await db.execute(
        _assistant_query()
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == user.tenant_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    await check_assistant_access(assistant_id, member, db)

    return _serialize_assistant(assistant)


async def _resolve_integrations(
    db: DbSession,
    integration_ids: list[UUID],
    tenant_id: UUID,
) -> list[NangoConnection]:
    """Resolve and validate integration IDs for a tenant."""
    if len(integration_ids) > MAX_INTEGRATIONS_PER_ASSISTANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_INTEGRATIONS_PER_ASSISTANT} intégrations par assistant.",
        )
    result = await db.execute(
        select(NangoConnection)
        .where(NangoConnection.id.in_(integration_ids))
        .where(NangoConnection.tenant_id == tenant_id)
        .where(NangoConnection.status == "connected")
    )
    return list(result.scalars().all())


@router.post("", response_model=AssistantReadWithCollections, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    data: AssistantCreate,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> dict:
    """Create a new assistant."""
    tenant_id = user.tenant_id

    # Get subscription to determine limit
    subscription = await quota_service.get_subscription(db, user.id)
    plan = subscription.plan if subscription else SubscriptionPlan.FREE.value
    max_assistants = ASSISTANT_LIMITS.get(plan, 3)

    # Count existing assistants
    count_result = await db.execute(
        select(func.count(Assistant.id)).where(Assistant.tenant_id == tenant_id)
    )
    current_count = count_result.scalar() or 0

    if current_count >= max_assistants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Limite d'assistants atteinte ({current_count}/{max_assistants}). Passez en Pro pour en créer plus.",
        )

    assistant = Assistant(
        tenant_id=tenant_id,
        name=data.name,
        system_prompt=data.system_prompt,
        model=data.model,
        settings=data.settings,
    )

    # Add collections if specified
    if data.collection_ids:
        result = await db.execute(
            select(Collection)
            .where(Collection.id.in_(data.collection_ids))
            .where(Collection.tenant_id == tenant_id)
        )
        collections = list(result.scalars().all())
        assistant.collections = collections

    # Add integrations if specified (max 2)
    if data.integration_ids:
        assistant.integrations = await _resolve_integrations(
            db, data.integration_ids, tenant_id
        )

    db.add(assistant)
    await db.commit()
    await db.refresh(assistant)

    # Reload with relations
    result = await db.execute(
        _assistant_query().where(Assistant.id == assistant.id)
    )
    assistant = result.scalar_one()

    return _serialize_assistant(assistant)


@router.patch("/{assistant_id}", response_model=AssistantReadWithCollections)
async def update_assistant(
    assistant_id: UUID,
    data: AssistantUpdate,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> dict:
    """Update an assistant."""
    tenant_id = user.tenant_id

    result = await db.execute(
        _assistant_query()
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == tenant_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle collections separately
    collection_ids = update_data.pop("collection_ids", None)
    if collection_ids is not None:
        result = await db.execute(
            select(Collection)
            .where(Collection.id.in_(collection_ids))
            .where(Collection.tenant_id == tenant_id)
        )
        collections = list(result.scalars().all())
        assistant.collections = collections

    # Handle integrations separately (max 2)
    integration_ids = update_data.pop("integration_ids", None)
    if integration_ids is not None:
        assistant.integrations = await _resolve_integrations(
            db, integration_ids, tenant_id
        )

    for key, value in update_data.items():
        setattr(assistant, key, value)

    await db.commit()
    await db.refresh(assistant)

    return _serialize_assistant(assistant)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: UUID,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> None:
    """Delete an assistant."""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.tenant_id == user.tenant_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    await db.delete(assistant)
    await db.commit()


# ---------------------------------------------------------------------------
# Permission management (admin-only)
# ---------------------------------------------------------------------------


async def _get_tenant_assistant(
    assistant_id: UUID, tenant_id: UUID, db: DbSession
) -> Assistant:
    """Fetch assistant ensuring tenant isolation. Raises 404 if not found."""
    result = await db.execute(
        select(Assistant).where(
            Assistant.id == assistant_id,
            Assistant.tenant_id == tenant_id,
        )
    )
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )
    return assistant


def _permission_to_read(
    perm: AssistantPermission, member: OrgMember, user: User
) -> dict:
    """Flatten a permission + member + user into PermissionMemberRead-compatible dict."""
    return {
        "id": perm.id,
        "member_id": member.id,
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "role": member.role,
        "created_at": perm.created_at,
    }


async def _list_permissions(
    assistant_id: UUID, tenant_id: UUID, db: DbSession
) -> list[dict]:
    """Return current permissions for an assistant as dicts."""
    result = await db.execute(
        select(AssistantPermission, OrgMember, User)
        .join(OrgMember, AssistantPermission.member_id == OrgMember.id)
        .join(User, OrgMember.user_id == User.id)
        .where(
            AssistantPermission.assistant_id == assistant_id,
            OrgMember.tenant_id == tenant_id,
        )
        .order_by(AssistantPermission.created_at.desc())
    )
    return [_permission_to_read(p, m, u) for p, m, u in result.all()]


@router.get(
    "/{assistant_id}/permissions",
    response_model=list[PermissionMemberRead],
)
async def list_assistant_permissions(
    assistant_id: UUID,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> list[dict]:
    """List members with access to this assistant."""
    await _get_tenant_assistant(assistant_id, user.tenant_id, db)
    return await _list_permissions(assistant_id, user.tenant_id, db)


@router.put(
    "/{assistant_id}/permissions",
    response_model=list[PermissionMemberRead],
)
async def set_assistant_permissions(
    assistant_id: UUID,
    data: PermissionBulkSet,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> list[dict]:
    """Replace all permissions for an assistant (bulk set)."""
    await _get_tenant_assistant(assistant_id, user.tenant_id, db)

    # Validate all member_ids are active members in the tenant
    if data.member_ids:
        valid_result = await db.execute(
            select(OrgMember.id).where(
                OrgMember.id.in_(data.member_ids),
                OrgMember.tenant_id == user.tenant_id,
                OrgMember.status == MemberStatus.ACTIVE.value,
            )
        )
        valid_ids = set(valid_result.scalars().all())
        invalid = set(data.member_ids) - valid_ids
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Membres invalides ou inactifs: {[str(i) for i in invalid]}",
            )

    # Delete existing permissions
    await db.execute(
        delete(AssistantPermission).where(
            AssistantPermission.assistant_id == assistant_id
        )
    )

    # Insert new permissions
    for mid in data.member_ids:
        db.add(AssistantPermission(assistant_id=assistant_id, member_id=mid))

    await db.commit()
    return await _list_permissions(assistant_id, user.tenant_id, db)


@router.post(
    "/{assistant_id}/permissions",
    response_model=list[PermissionMemberRead],
    status_code=status.HTTP_201_CREATED,
)
async def add_assistant_permissions(
    assistant_id: UUID,
    data: PermissionAdd,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> list[dict]:
    """Grant additional members access to an assistant."""
    await _get_tenant_assistant(assistant_id, user.tenant_id, db)

    if not data.member_ids:
        return await _list_permissions(assistant_id, user.tenant_id, db)

    # Validate member_ids are active members
    valid_result = await db.execute(
        select(OrgMember.id).where(
            OrgMember.id.in_(data.member_ids),
            OrgMember.tenant_id == user.tenant_id,
            OrgMember.status == MemberStatus.ACTIVE.value,
        )
    )
    valid_ids = set(valid_result.scalars().all())
    invalid = set(data.member_ids) - valid_ids
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Membres invalides ou inactifs: {[str(i) for i in invalid]}",
        )

    # Get existing permissions to skip duplicates
    existing_result = await db.execute(
        select(AssistantPermission.member_id).where(
            AssistantPermission.assistant_id == assistant_id,
            AssistantPermission.member_id.in_(data.member_ids),
        )
    )
    existing_ids = set(existing_result.scalars().all())

    for mid in valid_ids - existing_ids:
        db.add(AssistantPermission(assistant_id=assistant_id, member_id=mid))

    await db.commit()
    return await _list_permissions(assistant_id, user.tenant_id, db)


@router.delete(
    "/{assistant_id}/permissions/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_assistant_permission(
    assistant_id: UUID,
    member_id: UUID,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> None:
    """Revoke a member's access to an assistant."""
    await _get_tenant_assistant(assistant_id, user.tenant_id, db)

    result = await db.execute(
        select(AssistantPermission).where(
            AssistantPermission.assistant_id == assistant_id,
            AssistantPermission.member_id == member_id,
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission introuvable.",
        )

    await db.delete(perm)
    await db.commit()
