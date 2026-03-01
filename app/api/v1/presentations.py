"""Presentation API endpoints — CRUD, AI generation, export, SSE."""

import asyncio
import json
from uuid import UUID

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.deps import CurrentUser, DbSession
from app.schemas.presentation import (
    ExportRead,
    ExportRequest,
    GenerateOutlineRequest,
    GenerateSlidesRequest,
    OutlineUpdate,
    PresentationCreate,
    PresentationListItem,
    PresentationRead,
    PresentationUpdate,
    RegenerateSlideRequest,
    SlideRead,
    SlideReorderRequest,
    SlideUpdate,
    ThemeCreate,
    ThemeRead,
)
from app.services.presentation import presentation_service

router = APIRouter()


# ── Helpers ──


async def _get_redis() -> ArqRedis:
    """Get Arq Redis connection for enqueuing jobs."""
    from app.workers.settings import redis_settings
    return await create_pool(redis_settings)


def _ensure_found(obj, detail: str = "Ressource introuvable."):
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


async def _to_read(db, user, pres) -> PresentationRead:
    """Re-fetch with slides loaded to avoid lazy-load in async context."""
    loaded = await presentation_service.get(
        db, user.tenant_id, pres.id, with_slides=True
    )
    return PresentationRead.model_validate(loaded)


# ══════════════════════════════════════════════
#  CRUD — Presentations
# ══════════════════════════════════════════════


@router.get("", response_model=list[PresentationListItem])
async def list_presentations(
    user: CurrentUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[PresentationListItem]:
    """List presentations for the current tenant."""
    items = await presentation_service.list(
        db, user.tenant_id, status=status_filter, limit=limit, offset=offset
    )
    return [PresentationListItem.model_validate(p) for p in items]


@router.post("", response_model=PresentationRead, status_code=status.HTTP_201_CREATED)
async def create_presentation(
    data: PresentationCreate,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Create a new presentation."""
    pres = await presentation_service.create(db, user.tenant_id, data)
    return await _to_read(db, user, pres)


@router.get("/{pres_id}", response_model=PresentationRead)
async def get_presentation(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Get a presentation with slides."""
    pres = _ensure_found(
        await presentation_service.get(db, user.tenant_id, pres_id, with_slides=True)
    )
    return PresentationRead.model_validate(pres)


@router.patch("/{pres_id}", response_model=PresentationRead)
async def update_presentation(
    pres_id: UUID,
    data: PresentationUpdate,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Update presentation metadata."""
    pres = _ensure_found(
        await presentation_service.update(db, user.tenant_id, pres_id, data)
    )
    return await _to_read(db, user, pres)


@router.delete("/{pres_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_presentation(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a presentation and all its slides, assets, exports."""
    deleted = await presentation_service.delete(db, user.tenant_id, pres_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Présentation introuvable.")


@router.post("/{pres_id}/duplicate", response_model=PresentationRead, status_code=status.HTTP_201_CREATED)
async def duplicate_presentation(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Duplicate a presentation."""
    pres = _ensure_found(
        await presentation_service.duplicate(db, user.tenant_id, pres_id)
    )
    return await _to_read(db, user, pres)


# ══════════════════════════════════════════════
#  Outline
# ══════════════════════════════════════════════


@router.post("/{pres_id}/outline/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_outline(
    pres_id: UUID,
    request: GenerateOutlineRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Enqueue outline generation job."""
    pres = _ensure_found(await presentation_service.get(db, user.tenant_id, pres_id))
    pres.status = "generating_outline"
    await db.commit()
    redis = await _get_redis()
    job = await redis.enqueue_job(
        "generate_presentation_outline",
        str(pres_id),
        str(user.tenant_id),
        request.model_dump(),
    )
    await redis.close()
    return {"job_id": job.job_id, "status": "queued"}


@router.patch("/{pres_id}/outline", response_model=PresentationRead)
async def update_outline(
    pres_id: UUID,
    data: OutlineUpdate,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Manually update the outline."""
    pres = _ensure_found(
        await presentation_service.update_outline(
            db, user.tenant_id, pres_id, data.outline
        )
    )
    return await _to_read(db, user, pres)


# ══════════════════════════════════════════════
#  Slides
# ══════════════════════════════════════════════


@router.post("/{pres_id}/slides/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_slides(
    pres_id: UUID,
    request: GenerateSlidesRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Enqueue slide generation job."""
    pres = _ensure_found(await presentation_service.get(db, user.tenant_id, pres_id))
    pres.status = "generating_slides"
    await db.commit()
    redis = await _get_redis()
    job = await redis.enqueue_job(
        "generate_presentation_slides",
        str(pres_id),
        str(user.tenant_id),
        request.model_dump(),
    )
    await redis.close()
    return {"job_id": job.job_id, "status": "queued"}


@router.post("/{pres_id}/slides/{slide_id}/regenerate", response_model=SlideRead)
async def regenerate_slide(
    pres_id: UUID,
    slide_id: UUID,
    request: RegenerateSlideRequest,
    user: CurrentUser,
    db: DbSession,
) -> SlideRead:
    """Regenerate a single slide (synchronous, fast)."""
    slide = _ensure_found(
        await presentation_service.regenerate_slide(
            db, user.tenant_id, pres_id, slide_id, request
        )
    )
    return SlideRead.model_validate(slide)


@router.patch("/{pres_id}/slides/{slide_id}", response_model=SlideRead)
async def update_slide(
    pres_id: UUID,
    slide_id: UUID,
    data: SlideUpdate,
    user: CurrentUser,
    db: DbSession,
) -> SlideRead:
    """Update a single slide (autosave)."""
    slide = _ensure_found(
        await presentation_service.update_slide(
            db, user.tenant_id, pres_id, slide_id, data
        )
    )
    return SlideRead.model_validate(slide)


@router.post("/{pres_id}/slides", response_model=SlideRead, status_code=status.HTTP_201_CREATED)
async def add_slide(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> SlideRead:
    """Add a blank slide."""
    slide = _ensure_found(
        await presentation_service.add_slide(db, user.tenant_id, pres_id)
    )
    return SlideRead.model_validate(slide)


@router.delete("/{pres_id}/slides/{slide_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slide(
    pres_id: UUID,
    slide_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a slide."""
    deleted = await presentation_service.delete_slide(
        db, user.tenant_id, pres_id, slide_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slide introuvable.")


@router.post("/{pres_id}/slides/reorder", response_model=PresentationRead)
async def reorder_slides(
    pres_id: UUID,
    data: SlideReorderRequest,
    user: CurrentUser,
    db: DbSession,
) -> PresentationRead:
    """Reorder slides."""
    pres = _ensure_found(
        await presentation_service.reorder_slides(
            db, user.tenant_id, pres_id, data.slide_ids
        )
    )
    return await _to_read(db, user, pres)


# ══════════════════════════════════════════════
#  Export
# ══════════════════════════════════════════════


@router.post("/{pres_id}/export", status_code=status.HTTP_202_ACCEPTED)
async def export_presentation(
    pres_id: UUID,
    request: ExportRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create an export job (PPTX or PDF)."""
    export = _ensure_found(
        await presentation_service.create_export(
            db, user.tenant_id, pres_id, request
        )
    )
    redis = await _get_redis()
    job = await redis.enqueue_job(
        "export_presentation",
        str(export.id),
        str(user.tenant_id),
    )
    await redis.close()
    return {"export_id": str(export.id), "job_id": job.job_id, "status": "queued"}


@router.get("/{pres_id}/exports", response_model=list[ExportRead])
async def list_exports(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[ExportRead]:
    """List exports for a presentation."""
    exports = await presentation_service.list_exports(db, user.tenant_id, pres_id)
    return [ExportRead.model_validate(e) for e in exports]


# ══════════════════════════════════════════════
#  Themes
# ══════════════════════════════════════════════


@router.get("/themes", response_model=list[ThemeRead])
async def list_themes(
    user: CurrentUser,
    db: DbSession,
) -> list[ThemeRead]:
    """List built-in + custom themes."""
    themes = await presentation_service.list_themes(db, user.tenant_id)
    return [ThemeRead.model_validate(t) for t in themes]


@router.post("/themes", response_model=ThemeRead, status_code=status.HTTP_201_CREATED)
async def create_theme(
    data: ThemeCreate,
    user: CurrentUser,
    db: DbSession,
) -> ThemeRead:
    """Create a custom theme."""
    theme = await presentation_service.create_theme(db, user.tenant_id, data)
    return ThemeRead.model_validate(theme)


# ══════════════════════════════════════════════
#  SSE — Generation progress
# ══════════════════════════════════════════════


@router.get("/{pres_id}/events")
async def presentation_events(
    pres_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """SSE stream for generation progress. Supports reconnection via Last-Event-ID."""
    _ensure_found(await presentation_service.get(db, user.tenant_id, pres_id))

    async def event_stream():
        import redis.asyncio as aioredis

        from app.config import get_settings

        settings = get_settings()
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        channel = f"pres:{pres_id}:events"
        await pubsub.subscribe(channel)

        heartbeat_interval = 15  # seconds

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=heartbeat_interval,
                    )
                except asyncio.TimeoutError:
                    msg = None

                if msg is None:
                    yield ": heartbeat\n\n"
                    continue

                if msg["type"] != "message":
                    continue

                event = json.loads(msg["data"])
                event_type = event.get("type", "update")
                payload = event.get("payload", {})
                seq = event.get("seq", "")

                yield (
                    f"id: {seq}\n"
                    f"event: {event_type}\n"
                    f"data: {json.dumps(payload)}\n\n"
                )

                if event_type in ("generation_complete", "export_ready", "error"):
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await redis.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
