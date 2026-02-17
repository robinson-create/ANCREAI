"""Mistral LLM-as-reranker (fallback)."""

import json
import logging

import httpx

from app.config import get_settings
from app.core.retrieval.reranker import BaseReranker, RerankProviderError
from app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()

MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"

RERANK_PROMPT_TEMPLATE = """You are a reranking engine. Rank the given passages by how useful they are to answer the user's query.

User query: {query}

Passages:
{passages}

Output ONLY valid JSON with a 'ranking' array of objects, each with 'chunk_id' (string) and 'score' (float 0.0 to 1.0, higher is more relevant).
Example: {{"ranking": [{{"chunk_id": "abc", "score": 0.95}}, ...]}}
"""


class MistralReranker:
    """Reranker using Mistral chat completion as a ranking LLM."""

    def name(self) -> str:
        return "mistral"

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        topn: int,
    ) -> list[RetrievedChunk]:
        api_key = settings.mistral_api_key
        model = settings.rerank_mistral_model
        timeout = settings.rerank_mistral_timeout_seconds
        max_chars = settings.rerank_max_passage_chars
        temperature = settings.rerank_temperature

        if not api_key:
            raise RerankProviderError("MISTRAL_API_KEY is not configured")

        # Build passages string
        passage_lines = []
        for c in candidates:
            snippet = c.content[:max_chars].replace("\n", " ")
            passage_lines.append(f'[{c.chunk_id}] {snippet}')

        passages_text = "\n\n".join(passage_lines)
        prompt = RERANK_PROMPT_TEMPLATE.format(query=query, passages=passages_text)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    MISTRAL_CHAT_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error("Mistral reranker request failed: %s", e)
            raise RerankProviderError(f"Mistral reranker request failed: {e}") from e

        # Parse response
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            ranking = parsed["ranking"]
            if not isinstance(ranking, list):
                raise ValueError("ranking is not a list")
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.error("Mistral reranker invalid response: %s", e)
            raise RerankProviderError(f"Mistral reranker invalid JSON: {e}") from e

        # Build score map
        score_map: dict[str, float] = {}
        for item in ranking:
            cid = str(item.get("chunk_id", ""))
            score = float(item.get("score", 0.0))
            score_map[cid] = score

        # Sort candidates by rerank score
        for c in candidates:
            c.rerank_score = score_map.get(c.chunk_id, -float("inf"))

        reranked = sorted(candidates, key=lambda c: c.rerank_score or 0, reverse=True)
        logger.info("Mistral reranker scored %d candidates", len(candidates))
        return reranked[:topn]
