"""Reranker factory: select provider based on config."""

from app.config import get_settings
from app.core.retrieval.reranker import BaseReranker
from app.core.retrieval.reranker_hf import HFEndpointReranker
from app.core.retrieval.reranker_mistral import MistralReranker

settings = get_settings()

_PROVIDERS = {
    "hf_endpoint": HFEndpointReranker,
    "mistral": MistralReranker,
}


def get_reranker() -> BaseReranker | None:
    """Get the primary reranker, or None if disabled."""
    if not settings.rerank_enabled:
        return None
    cls = _PROVIDERS.get(settings.rerank_provider)
    return cls() if cls else None


def get_fallback_reranker() -> BaseReranker | None:
    """Get the fallback reranker, or None."""
    provider = settings.rerank_fallback_provider
    if not provider or provider == "none":
        return None
    cls = _PROVIDERS.get(provider)
    return cls() if cls else None
