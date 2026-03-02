"""Quota service for managing free/pro limits."""

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.daily_usage import DailyUsage
from app.models.document import Document
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User


class QuotaService:
    """Service for checking and tracking usage quotas."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def get_subscription(self, db: AsyncSession, user_id: UUID) -> Subscription | None:
        """Get subscription by user_id (legacy — prefer get_subscription_for_tenant)."""
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_subscription_for_tenant(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Subscription | None:
        """Get subscription by tenant_id (preferred).

        Falls back to user_id-based lookup via the users table if tenant_id
        column hasn't been backfilled yet.
        """
        # Primary: lookup by tenant_id directly
        result = await db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            return sub

        # Fallback: find via user.tenant_id → subscription.user_id
        from app.models.user import User
        result = await db.execute(
            select(Subscription)
            .join(User, Subscription.user_id == User.id)
            .where(User.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_daily_usage(self, db: AsyncSession, user_id: UUID) -> DailyUsage:
        """Get or create today's usage record."""
        today = date.today()

        result = await db.execute(
            select(DailyUsage).where(
                DailyUsage.user_id == user_id,
                DailyUsage.date == today,
            )
        )
        usage = result.scalar_one_or_none()

        if usage is None:
            usage = DailyUsage(
                id=uuid4(),
                user_id=user_id,
                date=today,
                chat_requests=0,
            )
            db.add(usage)
            await db.commit()
            await db.refresh(usage)

        return usage

    async def get_document_count(self, db: AsyncSession, tenant_id: UUID) -> int:
        """Get total number of documents for a tenant."""
        from app.models.collection import Collection

        result = await db.execute(
            select(func.count(Document.id))
            .join(Collection, Document.collection_id == Collection.id)
            .where(Collection.tenant_id == tenant_id)
        )
        return result.scalar_one() or 0

    async def _resolve_subscription(
        self, db: AsyncSession, user: User
    ) -> Subscription | None:
        """Resolve subscription: try tenant-based first, then user-based."""
        return (
            await self.get_subscription_for_tenant(db, user.tenant_id)
            or await self.get_subscription(db, user.id)
        )

    async def check_chat_allowed(
        self, db: AsyncSession, user: User
    ) -> tuple[bool, str | None]:
        """Check if user can send a chat message.

        Returns:
            tuple of (allowed, error_message)
        """
        subscription = await self._resolve_subscription(db, user)

        if subscription is None:
            return False, "Aucun abonnement trouvé"

        # Pro orgs have unlimited access
        if subscription.is_pro:
            return True, None

        # Free tier: check daily limit
        daily_usage = await self.get_daily_usage(db, user.id)

        if daily_usage.chat_requests >= self.settings.free_daily_chat_limit:
            return (
                False,
                f"Limite quotidienne atteinte ({daily_usage.chat_requests}/{self.settings.free_daily_chat_limit}). "
                "Passez en Pro pour un accès illimité.",
            )

        return True, None

    async def check_upload_allowed(
        self, db: AsyncSession, user: User
    ) -> tuple[bool, str | None]:
        """Check if user can upload a file.

        Returns:
            tuple of (allowed, error_message)
        """
        subscription = await self._resolve_subscription(db, user)

        if subscription is None:
            return False, "Aucun abonnement trouvé"

        # Pro orgs have unlimited access
        if subscription.is_pro:
            return True, None

        # Free tier: check file limit (use subscription.max_org_documents if set)
        max_files = subscription.max_org_documents or self.settings.free_max_files
        doc_count = await self.get_document_count(db, user.tenant_id)

        if doc_count >= max_files:
            return (
                False,
                f"Limite de fichiers atteinte ({doc_count}/{max_files}). "
                "Passez en Pro pour un accès illimité.",
            )

        return True, None

    async def record_chat_request(self, db: AsyncSession, user_id: UUID) -> None:
        """Increment today's chat request counter."""
        daily_usage = await self.get_daily_usage(db, user_id)
        daily_usage.chat_requests += 1
        await db.commit()

    async def get_usage_info(
        self, db: AsyncSession, user: User
    ) -> dict:
        """Get current usage information for display.

        Returns:
            dict with usage stats and limits
        """
        subscription = await self._resolve_subscription(db, user)
        daily_usage = await self.get_daily_usage(db, user.id)
        doc_count = await self.get_document_count(db, user.tenant_id)

        is_pro = subscription.is_pro if subscription else False
        max_files = (
            None if is_pro
            else (subscription.max_org_documents if subscription else self.settings.free_max_files)
        )

        return {
            "plan": subscription.plan if subscription else SubscriptionPlan.FREE.value,
            "status": subscription.status if subscription else SubscriptionStatus.ACTIVE.value,
            "is_pro": is_pro,
            "daily_chat_requests": daily_usage.chat_requests,
            "daily_chat_limit": None if is_pro else self.settings.free_daily_chat_limit,
            "daily_chat_remaining": (
                None
                if is_pro
                else max(0, self.settings.free_daily_chat_limit - daily_usage.chat_requests)
            ),
            "total_files": doc_count,
            "file_limit": max_files,
            "files_remaining": (
                None if is_pro else max(0, (max_files or 0) - doc_count)
            ),
        }


# Global instance
quota_service = QuotaService()
