"""Redis Streams client for agent run events.

Provides publish/consume primitives for the agent:{run_id} streams.
Events are batched (not token-by-token) and carry sequential IDs
for client-side idempotence.
"""

from __future__ import annotations

import json
import time
from uuid import UUID

import redis.asyncio as aioredis

from app.config import get_settings

# ── Event types ──────────────────────────────────────────────────────

EVENT_STATUS = "status"          # searching / analyzing / writing
EVENT_DELTA = "delta"            # text chunk (batched, not per-token)
EVENT_TOOL = "tool"              # tool_called / tool_result
EVENT_BLOCK = "block"            # generative UI block
EVENT_CITATIONS = "citations"    # source citations
EVENT_DONE = "done"              # run completed
EVENT_ERROR = "error"            # run failed


def _stream_key(run_id: UUID | str) -> str:
    return f"agent:{run_id}"


class AgentStreamPublisher:
    """Publishes events to a Redis Stream for a single agent run.

    Usage::

        pub = AgentStreamPublisher(redis, run_id)
        await pub.setup(ttl=600)
        await pub.emit_status("searching")
        await pub.emit_delta("Voici le contrat...")
        await pub.emit_done(tokens_input=400, tokens_output=800)
    """

    def __init__(self, redis: aioredis.Redis, run_id: UUID | str) -> None:
        self._redis = redis
        self._key = _stream_key(run_id)
        self._seq = 0

    async def setup(self, ttl: int = 600, maxlen: int = 2000) -> None:
        """Set TTL on the stream key and configure trim policy."""
        self._ttl = ttl
        self._maxlen = maxlen
        # Pre-create stream with initial TTL
        await self._redis.expire(self._key, ttl)

    async def _emit(self, event_type: str, payload: dict) -> str:
        """Publish an event to the stream. Returns the Redis stream message ID."""
        self._seq += 1
        fields = {
            "seq": str(self._seq),
            "type": event_type,
            "ts": str(time.time()),
            "data": json.dumps(payload, default=str),
        }
        msg_id = await self._redis.xadd(
            self._key,
            fields,
            maxlen=self._maxlen,
            approximate=True,
        )
        # Refresh TTL on each major event
        if self._seq % 10 == 0 or event_type in (EVENT_DONE, EVENT_ERROR):
            await self._redis.expire(self._key, self._ttl)
        return msg_id

    # ── Typed emitters ───────────────────────────────────────────

    async def emit_status(self, status: str) -> str:
        return await self._emit(EVENT_STATUS, {"status": status})

    async def emit_delta(self, text: str) -> str:
        return await self._emit(EVENT_DELTA, {"text": text})

    async def emit_tool(self, tool_name: str, phase: str, detail: dict | None = None) -> str:
        """phase: 'called' or 'result'"""
        return await self._emit(EVENT_TOOL, {
            "tool": tool_name, "phase": phase, **(detail or {}),
        })

    async def emit_block(self, block: dict) -> str:
        return await self._emit(EVENT_BLOCK, block)

    async def emit_citations(self, citations: list[dict]) -> str:
        return await self._emit(EVENT_CITATIONS, {"citations": citations})

    async def emit_done(
        self,
        *,
        tokens_input: int = 0,
        tokens_output: int = 0,
        tool_rounds: int = 0,
    ) -> str:
        return await self._emit(EVENT_DONE, {
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tool_rounds": tool_rounds,
        })

    async def emit_error(self, code: str, message: str | None = None) -> str:
        return await self._emit(EVENT_ERROR, {"code": code, "message": message})


class AgentStreamConsumer:
    """Async generator that reads events from an agent stream.

    Usage::

        async for event in AgentStreamConsumer(redis, run_id):
            # event = {"seq": "1", "type": "delta", "ts": "...", "data": {...}}
            if event["type"] == "done":
                break
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        run_id: UUID | str,
        *,
        last_id: str = "0-0",
        block_ms: int = 500,
        heartbeat_interval: float = 15.0,
        hard_timeout: float = 180.0,
    ) -> None:
        self._redis = redis
        self._key = _stream_key(run_id)
        self._last_id = last_id
        self._block_ms = block_ms
        self._heartbeat_interval = heartbeat_interval
        self._hard_timeout = hard_timeout

    def __aiter__(self):
        return self._consume()

    async def _consume(self):
        start_time = time.time()
        last_event_time = start_time

        while True:
            elapsed = time.time() - start_time
            if elapsed > self._hard_timeout:
                yield {
                    "seq": "-1",
                    "type": EVENT_ERROR,
                    "ts": str(time.time()),
                    "data": json.dumps({"code": "hard_timeout", "message": "Stream timeout"}),
                }
                return

            result = await self._redis.xread(
                {self._key: self._last_id},
                block=self._block_ms,
                count=50,
            )

            if not result:
                # No events — check heartbeat
                since_last = time.time() - last_event_time
                if since_last >= self._heartbeat_interval:
                    yield {
                        "seq": "-1",
                        "type": EVENT_STATUS,
                        "ts": str(time.time()),
                        "data": json.dumps({"status": "heartbeat"}),
                    }
                    last_event_time = time.time()
                continue

            for _stream_name, messages in result:
                for msg_id, fields in messages:
                    self._last_id = msg_id
                    last_event_time = time.time()

                    # Decode bytes → str
                    decoded = {}
                    for k, v in fields.items():
                        key = k.decode() if isinstance(k, bytes) else k
                        val = v.decode() if isinstance(v, bytes) else v
                        decoded[key] = val

                    yield decoded

                    # Stop if terminal event
                    if decoded.get("type") in (EVENT_DONE, EVENT_ERROR):
                        return


# ── Redis connection pool (singleton) ────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the shared async Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,  # We handle decoding in consumer
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool (call on shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
