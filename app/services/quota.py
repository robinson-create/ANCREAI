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
        """Get user's subscription."""
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
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

    async def check_chat_allowed(
        self, db: AsyncSession, user: User
    ) -> tuple[bool, str | None]:
        """Check if user can send a chat message.
        
        Returns:
            tuple of (allowed, error_message)
        """
        subscription = await self.get_subscription(db, user.id)

        if subscription is None:
            return False, "Aucun abonnement trouvé"

        # Pro users have unlimited access
        if subscription.plan == SubscriptionPlan.PRO.value and subscription.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value,
        ):
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
        subscription = await self.get_subscription(db, user.id)

        if subscription is None:
            return False, "Aucun abonnement trouvé"

        # Pro users have unlimited access
        if subscription.plan == SubscriptionPlan.PRO.value and subscription.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value,
        ):
            return True, None

        # Free tier: check file limit
        doc_count = await self.get_document_count(db, user.tenant_id)
        
        if doc_count >= self.settings.free_max_files:
            return (
                False,
                f"Limite de fichiers atteinte ({doc_count}/{self.settings.free_max_files}). "
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
        subscription = await self.get_subscription(db, user.id)
        daily_usage = await self.get_daily_usage(db, user.id)
        doc_count = await self.get_document_count(db, user.tenant_id)

        is_pro = subscription and subscription.plan == SubscriptionPlan.PRO.value

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
            "file_limit": None if is_pro else self.settings.free_max_files,
            "files_remaining": (
                None if is_pro else max(0, self.settings.free_max_files - doc_count)
            ),
        }


# Global instance
quota_service = QuotaService()
