"""Hugging Face Inference Endpoint reranker (primary).

Uses the TEI (Text Embeddings Inference) /rerank API format:
  POST <base_url>/rerank
  {"query": "...", "texts": ["passage1", ...], "truncate": true}
  → [{"index": 0, "score": 0.98}, {"index": 1, "score": 0.12}, ...]
"""

import logging

import httpx

from app.config import get_settings
from app.core.retrieval.reranker import BaseReranker, RerankProviderError
from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()


class HFEndpointReranker:
    """Reranker using a HF Inference Endpoint running a cross-encoder (TEI)."""

    def name(self) -> str:
        return "hf_endpoint"

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        topn: int,
    ) -> list[RetrievedChunk]:
        base_url = settings.hf_rerank_url.rstrip("/")
        token = settings.hf_rerank_token
        timeout = settings.rerank_timeout_seconds
        max_chars = settings.rerank_max_passage_chars
        max_retries = settings.rerank_retry_max

        if not base_url:
            raise RerankProviderError("HF_RERANK_URL is not configured")

        url = f"{base_url}/rerank"

        # Build texts list (truncated)
        texts = [c.content[:max_chars] for c in candidates]

        payload = {"query": query, "texts": texts, "truncate": True}
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        last_error: Exception | None = None
        for attempt in range(1 + max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()

                data = response.json()

                # TEI returns a list of {"index": int, "score": float}
                if not isinstance(data, list):
                    raise RerankProviderError(
                        f"Invalid HF rerank response: expected list, got {type(data).__name__}"
                    )

                # Map index → score
                for item in data:
                    idx = item.get("index")
                    score = float(item.get("score", 0.0))
                    if idx is not None and 0 <= idx < len(candidates):
                        candidates[idx].rerank_score = score

                # Sort candidates by rerank score
                reranked = sorted(candidates, key=lambda c: c.rerank_score or 0, reverse=True)
                logger.info(
                    "HF reranker scored %d candidates (attempt %d)",
                    len(candidates),
                    attempt + 1,
                )
                return reranked[:topn]

            except (httpx.HTTPError, httpx.TimeoutException, KeyError, ValueError) as e:
                last_error = e
                logger.warning("HF reranker attempt %d failed: %s", attempt + 1, e)

        raise RerankProviderError(f"HF reranker failed after {1 + max_retries} attempts: {last_error}")
