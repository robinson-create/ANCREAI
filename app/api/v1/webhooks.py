"""Stripe webhooks endpoint."""

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.deps import DbSession
from app.services.stripe_service import stripe_service

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events.
    
    This endpoint receives events from Stripe about:
    - Checkout session completions
    - Subscription updates
    - Subscription cancellations
    - Payment failures
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    logger.info(f"Received Stripe webhook: {event.type}")

    try:
        match event.type:
            case "checkout.session.completed":
                await stripe_service.handle_checkout_completed(db, event.data.object)
                logger.info("Checkout session completed processed")

            case "customer.subscription.updated":
                await stripe_service.handle_subscription_updated(db, event.data.object)
                logger.info("Subscription updated processed")

            case "customer.subscription.deleted":
                await stripe_service.handle_subscription_deleted(db, event.data.object)
                logger.info("Subscription deleted processed")

            case "invoice.payment_failed":
                await stripe_service.handle_payment_failed(db, event.data.object)
                logger.info("Payment failed processed")

            case _:
                logger.debug(f"Unhandled event type: {event.type}")

    except Exception as e:
        logger.error(f"Error processing webhook {event.type}: {e}")
        # Don't fail the webhook - Stripe will retry
        # Just log the error for investigation

    return {"status": "ok"}
