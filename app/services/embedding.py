"""Embedding service supporting OpenAI and Mistral providers."""

import hashlib
from typing import Sequence

from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()

# Mistral's API is OpenAI-compatible, just different base URL
_PROVIDER_CONFIG = {
    "openai": {
        "base_url": None,  # default OpenAI
        "api_key": settings.openai_api_key,
        "supports_dimensions": True,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "api_key": settings.mistral_api_key,
        "supports_dimensions": False,
    },
}


class EmbeddingService:
    """Service for generating embeddings (OpenAI or Mistral)."""

    def __init__(self) -> None:
        provider = settings.embedding_provider
        config = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG["mistral"])

        self.client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._supports_dimensions = config["supports_dimensions"]
        self._cache: dict[str, list[float]] = {}

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"{self.model}:{text_hash}"

    def _embed_kwargs(self, input_data: str | list[str]) -> dict:
        """Build kwargs for embeddings.create(), conditionally including dimensions."""
        kwargs: dict = {"input": input_data, "model": self.model}
        if self._supports_dimensions and self.dimensions:
            kwargs["dimensions"] = self.dimensions
        return kwargs

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = await self.client.embeddings.create(**self._embed_kwargs(text))

        embedding = response.data[0].embedding
        self._cache[cache_key] = embedding
        return embedding

    async def embed_texts(
        self,
        texts: Sequence[str],
        batch_size: int = 16,
    ) -> tuple[list[list[float]], int]:
        """
        Generate embeddings for multiple texts.

        Returns:
            Tuple of (embeddings, total_tokens_used)
        """
        embeddings: list[list[float]] = []
        total_tokens = 0

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Check cache first
            batch_embeddings = []
            texts_to_embed = []
            indices_to_embed = []

            for j, text in enumerate(batch):
                cache_key = self._cache_key(text)
                if cache_key in self._cache:
                    batch_embeddings.append((j, self._cache[cache_key]))
                else:
                    texts_to_embed.append(text)
                    indices_to_embed.append(j)

            # Embed non-cached texts
            if texts_to_embed:
                response = await self.client.embeddings.create(
                    **self._embed_kwargs(texts_to_embed)
                )

                total_tokens += response.usage.total_tokens

                for idx, data in zip(indices_to_embed, response.data):
                    embedding = data.embedding
                    cache_key = self._cache_key(texts_to_embed[indices_to_embed.index(idx)])
                    self._cache[cache_key] = embedding
                    batch_embeddings.append((idx, embedding))

            # Sort by original index and extract embeddings
            batch_embeddings.sort(key=lambda x: x[0])
            embeddings.extend([emb for _, emb in batch_embeddings])

        return embeddings, total_tokens

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query."""
        response = await self.client.embeddings.create(**self._embed_kwargs(query))
        return response.data[0].embedding


# Singleton instance
embedding_service = EmbeddingService()
