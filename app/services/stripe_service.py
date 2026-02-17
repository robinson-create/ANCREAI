"""Stripe billing service."""

from datetime import datetime, timezone
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User


class StripeService:
    """Service for Stripe billing operations."""

    def __init__(self) -> None:
        self.settings = get_settings()
        stripe.api_key = self.settings.stripe_secret_key

    async def create_customer(self, db: AsyncSession, user: User) -> str:
        """Create a Stripe customer for a user.
        
        Args:
            db: Database session
            user: User to create customer for
            
        Returns:
            Stripe customer ID
        """
        if user.stripe_customer_id:
            return user.stripe_customer_id

        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
            },
        )

        user.stripe_customer_id = customer.id
        await db.commit()

        return customer.id

    async def create_checkout_session(
        self,
        db: AsyncSession,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session for Pro subscription.
        
        Args:
            db: Database session
            user: User to create session for
            success_url: URL to redirect to on success
            cancel_url: URL to redirect to on cancel
            
        Returns:
            Checkout session URL
        """
        # Ensure customer exists
        customer_id = await self.create_customer(db, user)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": self.settings.stripe_pro_price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                }
            },
            allow_promotion_codes=True,
        )

        return session.url

    async def create_trial_checkout_session(
        self,
        db: AsyncSession,
        user: User,
        success_url: str,
        cancel_url: str,
        trial_days: int = 7,
    ) -> str:
        """Create a Stripe Checkout session with a trial period.

        Args:
            db: Database session
            user: User to create session for
            success_url: URL to redirect to on success
            cancel_url: URL to redirect to on cancel
            trial_days: Number of trial days (default 7)

        Returns:
            Checkout session URL
        """
        customer_id = await self.create_customer(db, user)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": self.settings.stripe_pro_price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
            },
            subscription_data={
                "trial_period_days": trial_days,
                "metadata": {
                    "user_id": str(user.id),
                },
            },
            allow_promotion_codes=True,
        )

        return session.url

    async def create_portal_session(
        self,
        db: AsyncSession,
        user: User,
        return_url: str,
    ) -> str:
        """Create a Stripe Customer Portal session.
        
        Args:
            db: Database session
            user: User to create session for
            return_url: URL to return to after portal
            
        Returns:
            Portal session URL
        """
        # Ensure customer exists
        customer_id = await self.create_customer(db, user)

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return session.url

    async def handle_checkout_completed(
        self,
        db: AsyncSession,
        session: stripe.checkout.Session,
    ) -> None:
        """Handle checkout.session.completed webhook event.
        
        Args:
            db: Database session
            session: Stripe checkout session object
        """
        user_id = session.metadata.get("user_id")
        if not user_id:
            return

        # Get subscription from session
        stripe_subscription = stripe.Subscription.retrieve(session.subscription)

        # Update or create subscription in our DB
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == UUID(user_id))
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.plan = SubscriptionPlan.PRO.value
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.stripe_price_id = stripe_subscription["items"]["data"][0]["price"]["id"]
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            )
            subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end

        await db.commit()

    async def handle_subscription_updated(
        self,
        db: AsyncSession,
        stripe_subscription: stripe.Subscription,
    ) -> None:
        """Handle customer.subscription.updated webhook event.
        
        Args:
            db: Database session
            stripe_subscription: Stripe subscription object
        """
        # Find subscription by Stripe ID
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription.id
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Map Stripe status to our status
        status_map = {
            "active": SubscriptionStatus.ACTIVE.value,
            "past_due": SubscriptionStatus.PAST_DUE.value,
            "canceled": SubscriptionStatus.CANCELED.value,
            "trialing": SubscriptionStatus.TRIALING.value,
            "incomplete": SubscriptionStatus.INCOMPLETE.value,
        }

        subscription.status = status_map.get(
            stripe_subscription.status, SubscriptionStatus.ACTIVE.value
        )
        subscription.current_period_start = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=timezone.utc
        )
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=timezone.utc
        )
        subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end

        await db.commit()

    async def handle_subscription_deleted(
        self,
        db: AsyncSession,
        stripe_subscription: stripe.Subscription,
    ) -> None:
        """Handle customer.subscription.deleted webhook event.
        
        Args:
            db: Database session
            stripe_subscription: Stripe subscription object
        """
        # Find subscription by Stripe ID
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription.id
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Downgrade to free plan
        subscription.plan = SubscriptionPlan.FREE.value
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.stripe_subscription_id = None
        subscription.stripe_price_id = None
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.cancel_at_period_end = False

        await db.commit()

    async def handle_payment_failed(
        self,
        db: AsyncSession,
        invoice: stripe.Invoice,
    ) -> None:
        """Handle invoice.payment_failed webhook event.
        
        Args:
            db: Database session
            invoice: Stripe invoice object
        """
        if not invoice.subscription:
            return

        # Find subscription by Stripe ID
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == invoice.subscription
            )
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.status = SubscriptionStatus.PAST_DUE.value
            await db.commit()


# Global instance
stripe_service = StripeService()
