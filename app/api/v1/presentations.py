"""Presentation API endpoints — CRUD, AI generation, export, SSE."""

import asyncio
import json
from uuid import UUID, uuid4

from arq import ArqRedis, create_pool
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models.presentation import AssetKind, AssetStatus, PresentationAsset
from app.schemas.presentation import (
    AssetReadWithUrl,
    AssetUrlResponse,
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
from app.services.storage import storage_service

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
    read = PresentationRead.model_validate(loaded)
    await _resolve_slide_asset_urls(db, user.tenant_id, read)
    return read


async def _resolve_slide_asset_urls(
    db,
    tenant_id: UUID,
    pres_read: PresentationRead,
) -> None:
    """Resolve presigned URLs for asset_ids in root_image and content_json."""
    if not pres_read.slides:
        return

    # Collect all asset IDs from root_image fields AND content_json __asset_id__ fields
    asset_ids: list[UUID] = []
    for slide in pres_read.slides:
        if slide.root_image and slide.root_image.get("asset_id"):
            try:
                asset_ids.append(UUID(slide.root_image["asset_id"]))
            except (ValueError, TypeError):
                pass

        # Also collect __asset_id__ from content_json image fields
        if slide.content_json and isinstance(slide.content_json, dict):
            for _key, value in slide.content_json.items():
                if isinstance(value, dict) and value.get("__asset_id__"):
                    try:
                        asset_ids.append(UUID(value["__asset_id__"]))
                    except (ValueError, TypeError):
                        pass
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            for _sk, sv in item.items():
                                if isinstance(sv, dict) and sv.get("__asset_id__"):
                                    try:
                                        asset_ids.append(UUID(sv["__asset_id__"]))
                                    except (ValueError, TypeError):
                                        pass

    if not asset_ids:
        return

    # Fetch all assets in one query
    result = await db.execute(
        select(PresentationAsset)
        .where(PresentationAsset.id.in_(asset_ids))
        .where(PresentationAsset.tenant_id == tenant_id)
    )
    assets_by_id = {str(a.id): a for a in result.scalars().all()}

    # Resolve presigned URLs
    for slide in pres_read.slides:
        # root_image (legacy)
        if slide.root_image and slide.root_image.get("asset_id"):
            asset = assets_by_id.get(slide.root_image["asset_id"])
            if asset and asset.s3_key:
                url = await storage_service.get_presigned_url(asset.s3_key, expires_in=3600)
                slide.root_image["url"] = url

        # content_json image fields (new JSON template pipeline)
        if slide.content_json and isinstance(slide.content_json, dict):
            for _key, value in slide.content_json.items():
                if isinstance(value, dict) and value.get("__asset_id__"):
                    asset = assets_by_id.get(value["__asset_id__"])
                    if asset and asset.s3_key:
                        value["__image_url__"] = await storage_service.get_presigned_url(
                            asset.s3_key, expires_in=3600,
                        )
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            for _sk, sv in item.items():
                                if isinstance(sv, dict) and sv.get("__asset_id__"):
                                    asset = assets_by_id.get(sv["__asset_id__"])
                                    if asset and asset.s3_key:
                                        sv["__image_url__"] = await storage_service.get_presigned_url(
                                            asset.s3_key, expires_in=3600,
                                        )


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
    read = PresentationRead.model_validate(pres)
    await _resolve_slide_asset_urls(db, user.tenant_id, read)
    return read


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
    """Enqueue direct generation job (split + slides in one pass).

    NOTE: endpoint name kept as /outline/generate for frontend compatibility.
    Internally, this now enqueues the direct generation job which splits
    the prompt and generates slides without a separate outline step.
    """
    pres = _ensure_found(await presentation_service.get(db, user.tenant_id, pres_id))
    pres.status = "generating_slides"
    await db.commit()
    redis = await _get_redis()
    job = await redis.enqueue_job(
        "generate_presentation_slides_direct",
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


@router.get("/{pres_id}/exports/{export_id}/download")
async def download_export(
    pres_id: UUID,
    export_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a presigned URL to download a completed export."""
    export = _ensure_found(
        await presentation_service.get_export(db, user.tenant_id, pres_id, export_id)
    )
    if export.status != "done" or not export.s3_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export non disponible.",
        )
    url = await storage_service.get_presigned_url(export.s3_key, expires_in=3600)
    return {"url": url, "format": export.format, "file_size": export.file_size}


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


# ══════════════════════════════════════════════
#  Assets — Image upload / management
# ══════════════════════════════════════════════

_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/{presentation_id}/assets/upload",
    response_model=AssetReadWithUrl,
    status_code=status.HTTP_201_CREATED,
)
async def upload_asset(
    presentation_id: UUID,
    user: CurrentUser,
    db: DbSession,
    file: UploadFile,
) -> AssetReadWithUrl:
    """Upload an image to a presentation."""
    pres = await presentation_service.get(db, user.tenant_id, presentation_id)
    _ensure_found(pres, "Présentation introuvable.")

    # Validate MIME type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier non supporté : {content_type}. "
                   f"Formats acceptés : JPEG, PNG, WebP, GIF.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier vide.",
        )

    if len(content) > _MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fichier trop volumineux ({len(content) // (1024*1024)} MB). Maximum : 10 MB.",
        )

    # Build a unique filename
    asset_id = uuid4()
    original_name = file.filename or "image"
    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "jpg"
    filename = f"{asset_id}.{ext}"

    # Upload to S3
    s3_key, content_hash, file_size = await storage_service.upload_file(
        tenant_id=user.tenant_id,
        collection_id=presentation_id,
        filename=filename,
        content=content,
        content_type=content_type,
    )

    # Create DB record
    asset = PresentationAsset(
        id=asset_id,
        tenant_id=user.tenant_id,
        presentation_id=presentation_id,
        kind=AssetKind.IMAGE.value,
        status=AssetStatus.READY.value,
        s3_key=s3_key,
        mime=content_type,
        byte_size=file_size,
        checksum=content_hash,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    # Generate presigned URL
    url = await storage_service.get_presigned_url(s3_key, expires_in=3600)

    result = AssetReadWithUrl.model_validate(asset)
    result.url = url
    return result


@router.get(
    "/{presentation_id}/assets",
    response_model=list[AssetReadWithUrl],
)
async def list_assets(
    presentation_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[AssetReadWithUrl]:
    """List all assets for a presentation."""
    pres = await presentation_service.get(db, user.tenant_id, presentation_id)
    _ensure_found(pres, "Présentation introuvable.")

    result = await db.execute(
        select(PresentationAsset)
        .where(PresentationAsset.presentation_id == presentation_id)
        .where(PresentationAsset.tenant_id == user.tenant_id)
        .order_by(PresentationAsset.created_at.desc())
    )
    assets = result.scalars().all()

    items: list[AssetReadWithUrl] = []
    for asset in assets:
        url = None
        if asset.s3_key:
            url = await storage_service.get_presigned_url(asset.s3_key, expires_in=3600)
        item = AssetReadWithUrl.model_validate(asset)
        item.url = url
        items.append(item)

    return items


@router.get(
    "/{presentation_id}/assets/{asset_id}/url",
    response_model=AssetUrlResponse,
)
async def get_asset_url(
    presentation_id: UUID,
    asset_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> AssetUrlResponse:
    """Get a fresh presigned URL for an asset (used for expired URL refresh)."""
    result = await db.execute(
        select(PresentationAsset)
        .where(PresentationAsset.id == asset_id)
        .where(PresentationAsset.presentation_id == presentation_id)
        .where(PresentationAsset.tenant_id == user.tenant_id)
    )
    asset = result.scalar_one_or_none()
    _ensure_found(asset, "Asset introuvable.")

    if not asset.s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset sans fichier associé.",
        )

    url = await storage_service.get_presigned_url(asset.s3_key, expires_in=3600)
    return AssetUrlResponse(url=url)


@router.delete(
    "/{presentation_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_asset(
    presentation_id: UUID,
    asset_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an asset (S3 file + DB record)."""
    result = await db.execute(
        select(PresentationAsset)
        .where(PresentationAsset.id == asset_id)
        .where(PresentationAsset.presentation_id == presentation_id)
        .where(PresentationAsset.tenant_id == user.tenant_id)
    )
    asset = result.scalar_one_or_none()
    _ensure_found(asset, "Asset introuvable.")

    # Delete from S3
    if asset.s3_key:
        try:
            await storage_service.delete_file(asset.s3_key)
        except Exception:
            pass  # S3 delete failure is non-blocking

    # Delete DB record
    await db.delete(asset)
    await db.commit()
