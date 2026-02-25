"""SSE event publisher for presentation generation progress."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class PresentationEventPublisher:
    """Publishes idempotent SSE events to Redis pub/sub."""

    def __init__(self, redis) -> None:
        self.redis = redis

    async def publish(
        self,
        pres_id: UUID,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        slide_id: UUID | None = None,
        slide_index: int | None = None,
        run_id: UUID | None = None,
    ) -> None:
        """Publish a single SSE event with idempotent ID."""
        channel = f"pres:{pres_id}:events"
        seq = await self.redis.incr(f"pres:{pres_id}:seq")

        event = {
            "event_id": f"{pres_id}:{event_type}:{seq}",
            "seq": seq,
            "type": event_type,
            "payload": {
                **(payload or {}),
                **({"slide_id": str(slide_id)} if slide_id else {}),
                **({"slide_index": slide_index} if slide_index is not None else {}),
                **({"run_id": str(run_id)} if run_id else {}),
            },
        }

        await self.redis.publish(channel, json.dumps(event))

    # ── Convenience methods ──

    async def outline_ready(self, pres_id: UUID, outline: list[dict]) -> None:
        await self.publish(pres_id, event_type="outline_ready", payload={"outline": outline})

    async def slide_generated(
        self, pres_id: UUID, slide_id: UUID, slide_index: int, total: int
    ) -> None:
        await self.publish(
            pres_id,
            event_type="slide_generated",
            payload={"total": total},
            slide_id=slide_id,
            slide_index=slide_index,
        )

    async def slide_error(
        self, pres_id: UUID, slide_index: int, used_fallback: bool, run_id: UUID | None = None
    ) -> None:
        await self.publish(
            pres_id,
            event_type="slide_error",
            payload={"used_fallback": used_fallback},
            slide_index=slide_index,
            run_id=run_id,
        )

    async def asset_ready(
        self, pres_id: UUID, slide_id: UUID, slide_index: int, asset_id: UUID
    ) -> None:
        await self.publish(
            pres_id,
            event_type="asset_ready",
            payload={"asset_id": str(asset_id)},
            slide_id=slide_id,
            slide_index=slide_index,
        )

    async def generation_complete(self, pres_id: UUID) -> None:
        await self.publish(pres_id, event_type="generation_complete")

    async def export_progress(self, pres_id: UUID, percent: int) -> None:
        await self.publish(pres_id, event_type="export_progress", payload={"percent": percent})

    async def export_ready(self, pres_id: UUID, export_id: UUID, format: str) -> None:
        await self.publish(
            pres_id,
            event_type="export_ready",
            payload={"export_id": str(export_id), "format": format},
        )

    async def error(self, pres_id: UUID, message: str) -> None:
        await self.publish(pres_id, event_type="error", payload={"message": message})
