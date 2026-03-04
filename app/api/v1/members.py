"""Organization member management endpoints.

All endpoints require admin role except invitation acceptance.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminMember, CurrentUser, DbSession
from app.models.assistant_permission import AssistantPermission
from app.models.enums import MemberStatus, OrgRole
from app.models.org_member import OrgMember
from app.models.user import User
from app.schemas.member import MemberInvite, MemberRead, MemberUpdate
from app.services.quota import quota_service

router = APIRouter()
invitation_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _member_to_read(member: OrgMember, user: User) -> dict:
    """Flatten an OrgMember + User join into a MemberRead-compatible dict."""
    return {
        "id": member.id,
        "tenant_id": member.tenant_id,
        "user_id": member.user_id,
        "role": member.role,
        "status": member.status,
        "invited_by": member.invited_by,
        "invited_at": member.invited_at,
        "joined_at": member.joined_at,
        "created_at": member.created_at,
        "updated_at": member.updated_at,
        "email": user.email,
        "name": user.name,
    }


async def _check_last_admin(
    db: DbSession, tenant_id: UUID, target: OrgMember
) -> None:
    """Raise if target is the last active admin in the tenant.

    Must be called inside the same transaction as the mutation.
    """
    if target.role != OrgRole.ADMIN.value:
        return

    result = await db.execute(
        select(func.count(OrgMember.id)).where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.role == OrgRole.ADMIN.value,
            OrgMember.status == MemberStatus.ACTIVE.value,
        )
    )
    if result.scalar_one() <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de retirer le dernier admin actif.",
        )


# ---------------------------------------------------------------------------
# CRUD — all admin-only
# ---------------------------------------------------------------------------


@router.get("", response_model=list[MemberRead])
async def list_members(
    _admin: AdminMember,
    db: DbSession,
) -> list[dict]:
    """List organization members (excludes inactive)."""
    result = await db.execute(
        select(OrgMember, User)
        .join(User, OrgMember.user_id == User.id)
        .where(
            OrgMember.tenant_id == _admin.tenant_id,
            OrgMember.status != MemberStatus.INACTIVE.value,
        )
        .order_by(OrgMember.created_at.desc())
    )
    return [_member_to_read(m, u) for m, u in result.all()]


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def invite_member(
    data: MemberInvite,
    user: CurrentUser,
    _admin: AdminMember,
    db: DbSession,
) -> dict:
    """Invite a member by email. User must already have a Clerk account."""
    tenant_id = _admin.tenant_id

    # --- Quota check (transactional with FOR UPDATE) ---
    subscription = await quota_service.get_subscription_for_tenant(db, tenant_id)
    max_seats = subscription.max_seats if subscription else 1

    # Lock rows to prevent race conditions, then count in Python
    seat_rows = await db.execute(
        select(OrgMember.id)
        .where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.status.in_(
                [MemberStatus.ACTIVE.value, MemberStatus.INVITED.value]
            ),
        )
        .with_for_update()
    )
    current_seats = len(seat_rows.all())

    if current_seats >= max_seats:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Limite de sièges atteinte ({current_seats}/{max_seats}). "
            "Passez en Pro pour ajouter plus de membres.",
        )

    # --- Find target user ---
    target_result = await db.execute(
        select(User).where(User.email == data.email)
    )
    target_user = target_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable. Il doit d'abord créer un compte.",
        )

    # --- Check existing membership ---
    existing_result = await db.execute(
        select(OrgMember).where(
            OrgMember.tenant_id == tenant_id,
            OrgMember.user_id == target_user.id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        if existing.status in (MemberStatus.ACTIVE.value, MemberStatus.INVITED.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce membre fait déjà partie de l'organisation.",
            )
        # Reactivate inactive member
        existing.status = MemberStatus.INVITED.value
        existing.invited_by = user.id
        existing.invited_at = func.now()
        existing.joined_at = None
        await db.commit()
        await db.refresh(existing)
        return _member_to_read(existing, target_user)

    # --- Create new membership ---
    member = OrgMember(
        tenant_id=tenant_id,
        user_id=target_user.id,
        role=OrgRole.MEMBER.value,
        status=MemberStatus.INVITED.value,
        invited_by=user.id,
        invited_at=func.now(),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return _member_to_read(member, target_user)


@router.patch("/{member_id}", response_model=MemberRead)
async def update_member(
    member_id: UUID,
    data: MemberUpdate,
    _admin: AdminMember,
    db: DbSession,
) -> dict:
    """Update a member's role or status."""
    result = await db.execute(
        select(OrgMember)
        .options(selectinload(OrgMember.user))
        .where(
            OrgMember.id == member_id,
            OrgMember.tenant_id == _admin.tenant_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre introuvable.",
        )

    # Validate enum values
    if data.role is not None and data.role not in (
        OrgRole.ADMIN.value,
        OrgRole.MEMBER.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rôle invalide: {data.role}. Valeurs acceptées: admin, member.",
        )
    if data.status is not None and data.status not in (
        MemberStatus.ACTIVE.value,
        MemberStatus.INACTIVE.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Statut invalide: {data.status}. Valeurs acceptées: active, inactive.",
        )

    # Protect last admin (demotion or deactivation)
    is_demotion = data.role == OrgRole.MEMBER.value and member.role == OrgRole.ADMIN.value
    is_deactivation = data.status == MemberStatus.INACTIVE.value and member.status == MemberStatus.ACTIVE.value

    if is_demotion or (is_deactivation and member.role == OrgRole.ADMIN.value):
        await _check_last_admin(db, _admin.tenant_id, member)

    # Apply updates
    if data.role is not None:
        member.role = data.role
    if data.status is not None:
        member.status = data.status

    await db.commit()
    await db.refresh(member)

    return _member_to_read(member, member.user)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: UUID,
    _admin: AdminMember,
    db: DbSession,
) -> None:
    """Remove a member (soft-delete + cascade permissions)."""
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.id == member_id,
            OrgMember.tenant_id == _admin.tenant_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre introuvable.",
        )

    # Cannot remove yourself
    if member.user_id == _admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de vous retirer vous-même.",
        )

    # Protect last admin
    await _check_last_admin(db, _admin.tenant_id, member)

    # Cascade: remove all assistant permissions for this member
    await db.execute(
        delete(AssistantPermission).where(
            AssistantPermission.member_id == member.id
        )
    )

    # Soft-delete
    member.status = MemberStatus.INACTIVE.value
    await db.commit()


# ---------------------------------------------------------------------------
# Invitation acceptance — available to any authenticated user
# ---------------------------------------------------------------------------


@invitation_router.post("/accept", response_model=MemberRead)
async def accept_invitation(
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Accept a pending invitation for the current user."""
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.user_id == user.id,
            OrgMember.status == MemberStatus.INVITED.value,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune invitation en attente.",
        )

    member.status = MemberStatus.ACTIVE.value
    member.joined_at = func.now()
    await db.commit()
    await db.refresh(member)

    return _member_to_read(member, user)
