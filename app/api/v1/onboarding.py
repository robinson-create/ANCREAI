"""Onboarding endpoints."""

import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.assistant import Assistant
from app.models.collection import Collection
from app.models.web_source import WebSource
from app.integrations.nango.models import NangoConnection
from app.services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool


class OnboardingCompleteRequest(BaseModel):
    first_name: str
    last_name: str
    company_name: str = ""
    memories: str = ""
    website_urls: list[str] = []


class OnboardingCompleteResponse(BaseModel):
    assistant_id: str
    collection_id: str
    checkout_url: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(user: CurrentUser) -> OnboardingStatusResponse:
    """Check if the current user has completed onboarding."""
    return OnboardingStatusResponse(
        onboarding_completed=user.onboarding_completed,
    )


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    data: OnboardingCompleteRequest,
    user: CurrentUser,
    db: DbSession,
) -> OnboardingCompleteResponse:
    """Complete the onboarding process.

    Creates a default collection, assistant (with memories as system context),
    enqueues web crawling jobs, and creates a Stripe trial checkout session.
    """
    tenant_id = user.tenant_id

    # 1. Create default collection
    collection = Collection(
        id=uuid4(),
        tenant_id=tenant_id,
        name=f"Sources de {data.first_name}",
        description="Collection par d\u00e9faut cr\u00e9\u00e9e lors de l'onboarding.",
    )
    db.add(collection)
    await db.flush()

    # 2. Build system prompt with memories
    system_prompt_parts = []
    if data.memories.strip():
        system_prompt_parts.append(
            "Voici des informations de contexte fournies par l'utilisateur "
            "(m\u00e9moires import\u00e9es) :\n\n"
            f"{data.memories.strip()}"
        )
    system_prompt = "\n\n---\n\n".join(system_prompt_parts) if system_prompt_parts else None

    # 3. Resolve connected integrations for this tenant
    result = await db.execute(
        select(NangoConnection)
        .where(NangoConnection.tenant_id == tenant_id)
        .where(NangoConnection.status == "connected")
    )
    connected_integrations = list(result.scalars().all())

    # 4. Create default assistant
    assistant = Assistant(
        id=uuid4(),
        tenant_id=tenant_id,
        name=f"Assistant de {data.first_name}",
        system_prompt=system_prompt,
        model="mistral-medium-latest",
    )
    assistant.collections = [collection]
    # Link up to 2 integrations (assistant limit)
    assistant.integrations = connected_integrations[:2]

    db.add(assistant)
    await db.flush()

    # 5. Create web sources and enqueue crawling jobs
    web_source_ids = []
    for url in data.website_urls:
        url = url.strip()
        if not url:
            continue
        ws = WebSource(
            id=uuid4(),
            tenant_id=tenant_id,
            collection_id=collection.id,
            url=url,
            status="pending",
        )
        db.add(ws)
        web_source_ids.append(str(ws.id))

    # 6. Mark onboarding as completed
    user.onboarding_completed = True

    await db.commit()

    # 7. Enqueue crawl jobs (after commit so IDs are stable)
    try:
        from arq import ArqRedis, create_pool
        from app.workers.settings import redis_settings

        redis: ArqRedis = await create_pool(redis_settings)
        for ws_id in web_source_ids:
            await redis.enqueue_job("crawl_website", ws_id)
        await redis.close()
    except Exception:
        logger.warning("Failed to enqueue crawl jobs — worker may not be running", exc_info=True)

    # 8. Create Stripe trial checkout
    checkout_url: str | None = None
    try:
        checkout_url = await stripe_service.create_trial_checkout_session(
            db=db,
            user=user,
            success_url="http://localhost:3000/app?onboarding=success",
            cancel_url="http://localhost:3000/app/onboarding?step=6",
        )
    except Exception:
        logger.warning("Failed to create Stripe trial checkout", exc_info=True)

    return OnboardingCompleteResponse(
        assistant_id=str(assistant.id),
        collection_id=str(collection.id),
        checkout_url=checkout_url,
    )
