"""Clerk authentication module."""

from uuid import uuid4

import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.tenant import Tenant
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus


class ClerkAuth:
    """Clerk JWT validation and user management."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._jwks_client: PyJWKClient | None = None

    @property
    def jwks_client(self) -> PyJWKClient:
        """Lazy-loaded JWKS client."""
        if self._jwks_client is None:
            if not self.settings.clerk_jwks_url:
                raise ValueError("CLERK_JWKS_URL is not configured")
            self._jwks_client = PyJWKClient(self.settings.clerk_jwks_url)
        return self._jwks_client

    def verify_token(self, token: str) -> dict:
        """Validate Clerk JWT and return claims.
        
        Args:
            token: JWT token from Authorization header
            
        Returns:
            JWT claims dict with 'sub' (clerk_user_id), 'email', etc.
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk doesn't always set audience
        )
        return claims

    async def get_or_create_user(
        self,
        clerk_user_id: str,
        email: str,
        name: str | None,
        db: AsyncSession,
    ) -> User:
        """Get existing user or create new one with tenant and subscription.
        
        Args:
            clerk_user_id: Clerk's user ID (sub claim)
            email: User's email address
            name: User's display name
            db: Database session
            
        Returns:
            User object (existing or newly created)
        """
        # Try to find existing user
        result = await db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()

        if user is not None:
            # Update email/name if changed
            if user.email != email or user.name != name:
                user.email = email
                user.name = name
                await db.commit()
            return user

        # Create new tenant for the user
        tenant = Tenant(
            id=uuid4(),
            name=f"Workspace de {name or email}",
            max_assistants=3,  # Will be managed by subscription
        )
        db.add(tenant)

        # Create new user
        user = User(
            id=uuid4(),
            clerk_user_id=clerk_user_id,
            email=email,
            name=name,
            tenant_id=tenant.id,
        )
        db.add(user)

        # Create free subscription
        subscription = Subscription(
            id=uuid4(),
            user_id=user.id,
            plan=SubscriptionPlan.FREE.value,
            status=SubscriptionStatus.ACTIVE.value,
        )
        db.add(subscription)

        await db.commit()
        await db.refresh(user)

        return user


# Global instance
clerk_auth = ClerkAuth()
