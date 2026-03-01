"""Arq tasks for presentation generation and export."""

import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.presentation import (
    Presentation,
    PresentationExport,
    PresentationSlide,
    PresentationStatus,
    PresentationTheme,
)
from app.schemas.presentation import (
    GenerateOutlineRequest,
    GenerateSlidesRequest,
)
from app.services.presentation import presentation_service
from app.services.presentation_events import PresentationEventPublisher
from app.services.presentation_layout import PageSize, resolve_layout

settings = get_settings()
logger = logging.getLogger(__name__)

# Separate engine for worker process
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def _get_db() -> AsyncSession:
    return async_session_maker()


async def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ══════════════════════════════════════════════
#  Outline generation
# ══════════════════════════════════════════════


async def generate_presentation_outline(
    ctx: dict,
    presentation_id: str,
    tenant_id: str,
    request_data: dict,
) -> dict:
    """Arq job: generate outline via LLM.

    Args:
        ctx: Arq context
        presentation_id: UUID string
        tenant_id: UUID string
        request_data: GenerateOutlineRequest dict

    Returns:
        Dict with status and outline
    """
    pres_uuid = UUID(presentation_id)
    tenant_uuid = UUID(tenant_id)
    db = await _get_db()
    redis = await _get_redis()
    publisher = PresentationEventPublisher(redis)

    try:
        request = GenerateOutlineRequest(**request_data)
        outline = await presentation_service.generate_outline(
            db, tenant_uuid, pres_uuid, request
        )
        await db.commit()

        # Publish SSE event
        await publisher.outline_ready(
            pres_uuid,
            [item.model_dump() for item in outline],
        )

        logger.info(f"Outline generated for presentation {presentation_id}: {len(outline)} items")

        # Auto-chain: immediately generate slides (skip user review)
        if request.auto_generate_slides:
            logger.info(f"Auto-chaining slide generation for {presentation_id}")
            slides_request = GenerateSlidesRequest(
                collection_ids=request.collection_ids or [],
            )

            async def slide_callback(slide, index, total):
                await publisher.slide_generated(pres_uuid, slide.id, index, total)

            slides = await presentation_service.generate_slides(
                db, tenant_uuid, pres_uuid, slides_request,
                on_slide_progress=slide_callback,
            )
            await db.commit()
            await publisher.generation_complete(pres_uuid)

            logger.info(f"Slides auto-generated for {presentation_id}: {len(slides)} slides")
            return {"status": "ok", "outline_count": len(outline), "slide_count": len(slides)}

        return {"status": "ok", "outline_count": len(outline)}

    except Exception as e:
        logger.exception(f"Error generating outline for {presentation_id}")
        await db.rollback()

        # Update presentation status
        try:
            result = await db.execute(
                select(Presentation).where(Presentation.id == pres_uuid)
            )
            pres = result.scalar_one_or_none()
            if pres:
                pres.status = PresentationStatus.ERROR.value
                pres.error_message = str(e)[:2000]
                await db.commit()
        except Exception:
            pass

        await publisher.error(pres_uuid, str(e)[:500])
        return {"error": str(e)}

    finally:
        await db.close()
        await redis.close()


# ══════════════════════════════════════════════
#  Slides generation (slide-by-slide)
# ══════════════════════════════════════════════


async def generate_presentation_slides(
    ctx: dict,
    presentation_id: str,
    tenant_id: str,
    request_data: dict,
) -> dict:
    """Arq job: generate slides one by one from outline.

    Publishes SSE events for each slide.

    Args:
        ctx: Arq context
        presentation_id: UUID string
        tenant_id: UUID string
        request_data: GenerateSlidesRequest dict

    Returns:
        Dict with status and slide count
    """
    pres_uuid = UUID(presentation_id)
    tenant_uuid = UUID(tenant_id)
    db = await _get_db()
    redis = await _get_redis()
    publisher = PresentationEventPublisher(redis)

    try:
        request = GenerateSlidesRequest(**request_data)

        async def slide_callback(slide, index, total):
            await publisher.slide_generated(pres_uuid, slide.id, index, total)

        slides = await presentation_service.generate_slides(
            db, tenant_uuid, pres_uuid, request,
            on_slide_progress=slide_callback,
        )
        await db.commit()

        await publisher.generation_complete(pres_uuid)

        logger.info(f"Slides generated for presentation {presentation_id}: {len(slides)} slides")
        return {"status": "ok", "slide_count": len(slides)}

    except Exception as e:
        logger.exception(f"Error generating slides for {presentation_id}")
        await db.rollback()

        try:
            result = await db.execute(
                select(Presentation).where(Presentation.id == pres_uuid)
            )
            pres = result.scalar_one_or_none()
            if pres:
                pres.status = PresentationStatus.ERROR.value
                pres.error_message = str(e)[:2000]
                await db.commit()
        except Exception:
            pass

        await publisher.error(pres_uuid, str(e)[:500])
        return {"error": str(e)}

    finally:
        await db.close()
        await redis.close()


# ══════════════════════════════════════════════
#  Export (PPTX via Node microservice, PDF later)
# ══════════════════════════════════════════════


async def export_presentation(
    ctx: dict,
    export_id: str,
    tenant_id: str,
) -> dict:
    """Arq job: export presentation to PPTX/PDF.

    1. Load presentation + slides + theme
    2. Resolve layouts to bounding boxes
    3. POST to pptx-exporter Node service
    4. Update export record with S3 key

    Args:
        ctx: Arq context
        export_id: UUID string
        tenant_id: UUID string

    Returns:
        Dict with status and s3_key
    """
    import time

    import httpx

    export_uuid = UUID(export_id)
    tenant_uuid = UUID(tenant_id)
    db = await _get_db()
    redis = await _get_redis()
    publisher = PresentationEventPublisher(redis)

    try:
        # Load export record
        result = await db.execute(
            select(PresentationExport).where(PresentationExport.id == export_uuid)
        )
        export = result.scalar_one_or_none()
        if not export:
            return {"error": "Export record not found"}

        export.status = "processing"
        await db.flush()

        # Load presentation + slides
        result = await db.execute(
            select(Presentation).where(Presentation.id == export.presentation_id)
        )
        pres = result.scalar_one_or_none()
        if not pres:
            export.status = "error"
            export.error_message = "Presentation not found"
            await db.commit()
            return {"error": "Presentation not found"}

        result = await db.execute(
            select(PresentationSlide)
            .where(PresentationSlide.presentation_id == pres.id)
            .order_by(PresentationSlide.position)
        )
        slides = list(result.scalars().all())

        # Get theme
        theme_data = export.theme_snapshot or {}
        if not theme_data and pres.theme_id:
            theme = await db.get(PresentationTheme, pres.theme_id)
            if theme:
                theme_data = theme.theme_data

        await publisher.export_progress(pres.id, 10)

        # Resolve layouts
        page = PageSize()
        resolved_slides = []
        for slide in slides:
            boxes = resolve_layout(
                theme_data,
                {
                    "content_json": slide.content_json if isinstance(slide.content_json, list) else [],
                    "layout_type": slide.layout_type,
                    "root_image": slide.root_image,
                    "bg_color": slide.bg_color,
                },
                page,
            )
            resolved_slides.append({
                "id": str(slide.id),
                "position": slide.position,
                "layout_type": slide.layout_type,
                "bg_color": slide.bg_color,
                "boxes": [
                    {
                        "x": box.x,
                        "y": box.y,
                        "w": box.w,
                        "h": box.h,
                        "node_type": box.node_type,
                        "content": box.content,
                        "font_size_pt": box.font_size_pt,
                        "truncated": box.truncated,
                    }
                    for box in boxes
                ],
            })

        await publisher.export_progress(pres.id, 30)

        # POST to pptx-exporter Node service
        exporter_url = getattr(settings, "pptx_exporter_url", "http://localhost:4100")
        t0 = time.monotonic()

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{exporter_url}/export",
                json={
                    "schema_version": 1,
                    "presentation_id": str(pres.id),
                    "tenant_id": str(tenant_uuid),
                    "export_id": str(export_uuid),
                    "theme": theme_data,
                    "page_size": {
                        "width": page.width,
                        "height": page.height,
                        "margin": page.margin,
                    },
                    "slides": resolved_slides,
                    "assets": [],  # TODO: resolve asset presigned URLs
                },
            )

        duration_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            export.status = "error"
            export.error_message = f"Exporter returned {resp.status_code}: {resp.text[:500]}"
            export.duration_ms = duration_ms
            await db.commit()
            await publisher.error(pres.id, export.error_message)
            return {"error": export.error_message}

        result_data = resp.json()

        await publisher.export_progress(pres.id, 90)

        export.s3_key = result_data.get("s3_key")
        export.file_size = result_data.get("file_size")
        export.status = "done"
        export.duration_ms = duration_ms
        await db.commit()

        await publisher.export_ready(pres.id, export_uuid, export.format)

        logger.info(
            f"Export {export_id} completed: {export.s3_key} "
            f"({export.file_size} bytes, {duration_ms}ms)"
        )
        return {
            "status": "ok",
            "s3_key": export.s3_key,
            "file_size": export.file_size,
        }

    except Exception as e:
        logger.exception(f"Error exporting {export_id}")
        await db.rollback()

        try:
            result = await db.execute(
                select(PresentationExport).where(PresentationExport.id == export_uuid)
            )
            export = result.scalar_one_or_none()
            if export:
                export.status = "error"
                export.error_message = str(e)[:2000]
                await db.commit()
        except Exception:
            pass

        return {"error": str(e)}

    finally:
        await db.close()
        await redis.close()
