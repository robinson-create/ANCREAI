"""Billing API endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.services.quota import quota_service
from app.services.stripe_service import stripe_service

router = APIRouter()
settings = get_settings()


class CheckoutRequest(BaseModel):
    """Request body for checkout session creation."""

    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    """Request body for portal session creation."""

    return_url: str


class CheckoutResponse(BaseModel):
    """Response for checkout session creation."""

    url: str


class PortalResponse(BaseModel):
    """Response for portal session creation."""

    url: str


class SubscriptionResponse(BaseModel):
    """Response for current subscription."""

    plan: str
    status: str
    is_pro: bool
    current_period_end: str | None
    cancel_at_period_end: bool


class UsageResponse(BaseModel):
    """Response for usage information."""

    plan: str
    status: str
    is_pro: bool
    daily_chat_requests: int
    daily_chat_limit: int | None
    daily_chat_remaining: int | None
    total_files: int
    file_limit: int | None
    files_remaining: int | None


class PlansResponse(BaseModel):
    """Available subscription plans."""

    plans: list[dict]


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(user: CurrentUser, db: DbSession) -> SubscriptionResponse:
    """Get current user's subscription information."""
    subscription = await quota_service.get_subscription(db, user.id)

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    return SubscriptionResponse(
        plan=subscription.plan,
        status=subscription.status,
        is_pro=subscription.is_pro,
        current_period_end=(
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: CurrentUser,
    db: DbSession,
) -> CheckoutResponse:
    """Create a Stripe Checkout session for Pro subscription.
    
    The user will be redirected to Stripe's hosted checkout page.
    """
    if not settings.stripe_pro_price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    url = await stripe_service.create_checkout_session(
        db=db,
        user=user,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )

    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalRequest,
    user: CurrentUser,
    db: DbSession,
) -> PortalResponse:
    """Create a Stripe Customer Portal session.
    
    The user can manage their subscription, update payment method, etc.
    """
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please subscribe first.",
        )

    url = await stripe_service.create_portal_session(
        db=db,
        user=user,
        return_url=body.return_url,
    )

    return PortalResponse(url=url)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user: CurrentUser, db: DbSession) -> UsageResponse:
    """Get current usage information and remaining quotas."""
    usage_info = await quota_service.get_usage_info(db, user)
    return UsageResponse(**usage_info)


@router.get("/plans", response_model=PlansResponse)
async def get_plans() -> PlansResponse:
    """Get available subscription plans."""
    plans = [
        {
            "id": "free",
            "name": "Free",
            "price": 0,
            "currency": "EUR",
            "interval": "month",
            "features": [
                f"{settings.free_daily_chat_limit} requêtes chat/jour",
                f"{settings.free_max_files} fichiers maximum",
                "3 assistants",
                "Support email",
            ],
        },
        {
            "id": "pro",
            "name": "Pro",
            "price": 15,
            "currency": "EUR",
            "interval": "month",
            "stripe_price_id": settings.stripe_pro_price_id,
            "features": [
                "Requêtes chat illimitées",
                "Fichiers illimités",
                "10 assistants",
                "Support prioritaire",
                "API access",
            ],
            "popular": True,
        },
    ]
    return PlansResponse(plans=plans)
