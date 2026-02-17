"""Reranker base protocol and error."""

from typing import Protocol, runtime_checkable

from app.services.retrieval import RetrievedChunk


class RerankProviderError(Exception):
    """Raised when a rerank provider fails."""


@runtime_checkable
class BaseReranker(Protocol):
    """Protocol for reranker implementations."""

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        topn: int,
    ) -> list[RetrievedChunk]: ...

    def name(self) -> str: ...
