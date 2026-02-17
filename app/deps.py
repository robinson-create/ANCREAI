"""FastAPI dependencies."""

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
from app.core.auth import clerk_auth
from app.config import get_settings


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
    
    # Create free subscription
    subscription = Subscription(
        user_id=user.id,
        plan="free",
        status="active",
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


# Type aliases for dependency injection
TenantId = Annotated[UUID, Depends(get_tenant_id)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
