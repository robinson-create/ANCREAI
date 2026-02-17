"""Qdrant vector store client."""

from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings

settings = get_settings()


class VectorStore:
    """Async Qdrant vector store client."""

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = settings.qdrant_collection
        self.vector_size = settings.embedding_dimensions

    async def ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if self.collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            
            # Create payload indices for filtering
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="tenant_id",
                field_schema="keyword",
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="collection_id",
                field_schema="keyword",
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema="keyword",
            )

    async def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        batch_size: int = 200,
    ) -> None:
        """
        Upsert chunks into the vector store in batches.

        Each chunk should have:
        - id: str (UUID)
        - vector: list[float]
        - payload: dict with tenant_id, collection_id, document_id, content, page_number, etc.
        """
        if not chunks:
            return

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            points = [
                PointStruct(
                    id=chunk["id"],
                    vector=chunk["vector"],
                    payload=chunk["payload"],
                )
                for chunk in batch
            ]

            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

    async def delete_by_document(self, document_id: UUID) -> None:
        """Delete all chunks for a document."""
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        )
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return  # Collection doesn't exist yet — nothing to delete
            raise

    async def delete_by_collection(self, collection_id: UUID) -> None:
        """Delete all chunks for a collection."""
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="collection_id",
                            match=MatchValue(value=str(collection_id)),
                        )
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return  # Collection doesn't exist yet — nothing to delete
            raise

    async def search(
        self,
        query_vector: list[float],
        tenant_id: UUID,
        collection_ids: list[UUID] | None = None,
        limit: int = 20,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Search for similar chunks.
        
        Returns list of dicts with:
        - id: str
        - score: float
        - payload: dict
        """
        # Build filter
        must_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]
        
        if collection_ids is not None:
            # Filter by specific collections (empty list = match nothing)
            should_conditions = [
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(value=str(cid)),
                )
                for cid in collection_ids
            ]
            must_conditions.append(
                Filter(should=should_conditions)
            )

        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "id": str(point.id),
                "score": point.score,
                "payload": point.payload,
            }
            for point in results.points
        ]

    async def get_collection_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        info = await self.client.get_collection(self.collection_name)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }


# Singleton instance
vector_store = VectorStore()
