"""FastAPI dependencies."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.subscription import Subscription
from app.models.org_member import OrgMember
from app.models.assistant_permission import AssistantPermission
from app.models.enums import OrgRole, MemberStatus
from app.core.auth import clerk_auth
from app.config import get_settings

logger = logging.getLogger(__name__)


async def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> UUID:
    """Extract tenant ID from header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    try:
        return UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )


async def get_current_tenant(
    tenant_id: Annotated[UUID, Depends(get_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """Get current tenant from database."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    
    return tenant


async def get_or_create_dev_user(db: AsyncSession) -> User:
    """Get or create a dev user for local development."""
    dev_email = "dev@mecano-man.local"

    # Check if dev user exists
    result = await db.execute(
        select(User)
        .where(User.email == dev_email)
        .options(selectinload(User.subscription))
    )
    user = result.scalar_one_or_none()

    if user:
        return user

    # Create dev tenant
    from app.models.tenant import Tenant
    tenant = Tenant(name="Dev Tenant")
    db.add(tenant)
    await db.flush()

    # Create dev user
    user = User(
        email=dev_email,
        name="Dev User",
        clerk_user_id="dev_user_123",
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.flush()

    # Create org membership (admin of own org)
    org_member = OrgMember(
        tenant_id=tenant.id,
        user_id=user.id,
        role=OrgRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add(org_member)

    # Create free subscription (dual-write: user_id + tenant_id)
    subscription = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan="free",
        status="active",
        max_seats=1,
        max_assistants=1,
        max_org_documents=10,
    )
    db.add(subscription)
    await db.commit()

    # Reload with subscription
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.subscription))
    )
    return result.scalar_one()


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate Clerk JWT, return authenticated user.
    
    This dependency:
    1. Validates the JWT token from Authorization header
    2. Gets or creates the user (with tenant and subscription)
    3. Returns the user with subscription loaded
    
    In dev mode (DEV_AUTH_BYPASS=true), returns a mock dev user.
    """
    import logging
    
    settings = get_settings()
    
    # Dev mode: bypass auth and return dev user
    if settings.dev_auth_bypass:
        logging.info("DEV MODE: Bypassing Clerk auth, using dev user")
        return await get_or_create_dev_user(db)
    
    logging.info(f"Authorization header present: {authorization is not None}")
    if authorization:
        logging.info(f"Authorization header (first 30 chars): {authorization[:30]}...")
    
    if not authorization:
        logging.error("No Authorization header in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate JWT with Clerk
    try:
        claims = clerk_auth.verify_token(token)
    except Exception as e:
        logging.error(f"Token validation failed: {e}")
        logging.error(f"Token (first 50 chars): {token[:50]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info from claims
    clerk_user_id = claims.get("sub")
    email = claims.get("email") or claims.get("primary_email_address")
    name = claims.get("name") or claims.get("first_name")

    if not clerk_user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    # Get or create user
    user = await clerk_auth.get_or_create_user(
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
        db=db,
    )

    # Reload with subscription
    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.subscription))
    )
    user = result.scalar_one()

    return user


# ---------------------------------------------------------------------------
# OrgMember resolution
# ---------------------------------------------------------------------------

async def get_current_member(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMember:
    """Resolve the OrgMember for the authenticated user in their current tenant.

    During the transition period we use user.tenant_id (the legacy 1:1 link)
    to find the membership. Once multi-org is supported, this will switch to
    reading the tenant from a header or session.
    """
    result = await db.execute(
        select(OrgMember).where(
            OrgMember.tenant_id == user.tenant_id,
            OrgMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        # Fallback: auto-create for legacy users that predate the migration.
        # This handles the edge case where the backfill missed a row.
        logger.warning(
            "OrgMember missing for user %s / tenant %s — creating admin fallback",
            user.id, user.tenant_id,
        )
        member = OrgMember(
            tenant_id=user.tenant_id,
            user_id=user.id,
            role=OrgRole.ADMIN.value,
            status=MemberStatus.ACTIVE.value,
        )
        db.add(member)
        await db.flush()

    if member.status == MemberStatus.INACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your seat has been deactivated. Contact your organization admin.",
        )

    if member.status == MemberStatus.INVITED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your invitation is pending. Please complete the onboarding first.",
        )

    return member


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

async def require_admin(
    member: OrgMember = Depends(get_current_member),
) -> OrgMember:
    """Dependency that ensures the current member is an admin."""
    if not member.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return member


async def check_assistant_access(
    assistant_id: UUID,
    member: OrgMember,
    db: AsyncSession,
) -> None:
    """Verify the member has access to the given assistant.

    Admins always have access. Members need an explicit AssistantPermission row.
    Raises HTTP 403 if access is denied.
    """
    if member.is_admin:
        return

    result = await db.execute(
        select(AssistantPermission.id).where(
            AssistantPermission.assistant_id == assistant_id,
            AssistantPermission.member_id == member.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this assistant.",
        )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

TenantId = Annotated[UUID, Depends(get_tenant_id)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentMember = Annotated[OrgMember, Depends(get_current_member)]
AdminMember = Annotated[OrgMember, Depends(require_admin)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
