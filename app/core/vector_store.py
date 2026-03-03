"""Qdrant vector store client."""

import logging
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
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
            for field in (
                "tenant_id", "collection_id", "document_id",
                "scope", "user_id", "dossier_id", "dossier_document_id",
                "project_id", "project_document_id",
                "source_type", "source_id",
            ):
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                )

    async def ensure_payload_indices(self) -> None:
        """Ensure all required payload indices exist (idempotent).

        Safe to call on an existing collection — Qdrant ignores
        create_payload_index if the index already exists.
        """
        for field in (
            "tenant_id", "collection_id", "document_id",
            "scope", "user_id", "dossier_id", "dossier_document_id",
            "project_id", "project_document_id",
            "source_type", "source_id",
        ):
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                )
            except UnexpectedResponse:
                pass  # Index already exists or collection missing

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

    async def delete_by_document(self, document_id: UUID, tenant_id: UUID) -> None:
        """Delete all chunks for a document, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_document",
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return  # Collection doesn't exist yet — nothing to delete
            raise

    async def delete_by_collection(self, collection_id: UUID, tenant_id: UUID) -> None:
        """Delete all chunks for a collection, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_collection",
            "collection_id": str(collection_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="collection_id",
                            match=MatchValue(value=str(collection_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
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
        dossier_ids: list[UUID] | None = None,
        project_ids: list[UUID] | None = None,
        user_id: UUID | None = None,
        limit: int = 20,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks.

        Supports org, personal, project, and personal-global scopes:
        - collection_ids → org-scope chunks (scope='org', collection_id IN ...)
        - dossier_ids → personal-scope chunks (scope='personal', dossier_id IN ...)
        - project_ids → project-scope chunks (scope='project', project_id IN ...)
        - user_id (alone) → personal-global: ALL user chunks (personal + project)

        Scopes are mutually exclusive: user_id cannot be combined with
        collection_ids, dossier_ids, or project_ids.

        Returns list of dicts with id, score, payload.
        """
        has_specific_scope = (
            (collection_ids is not None and len(collection_ids) > 0)
            or (dossier_ids is not None and len(dossier_ids) > 0)
            or (project_ids is not None and len(project_ids) > 0)
        )

        # Invariant #4: scopes mutually exclusive
        if user_id is not None and has_specific_scope:
            raise ValueError(
                "user_id (personal-global) cannot be combined with "
                "collection_ids, dossier_ids, or project_ids"
            )

        # Always filter by tenant (invariant #8)
        must_conditions: list = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]

        # Personal-global mode: search ALL user content (personal + project)
        if user_id is not None and not has_specific_scope:
            # Invariant #8: tenant_id + user_id always together
            must_conditions.append(
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=str(user_id)),
                )
            )
            # Invariant #5: explicit scope filter — must strict, no should
            must_conditions.append(
                FieldCondition(
                    key="scope",
                    match=MatchAny(any=["personal", "project"]),
                )
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

        # Strict scope enforcement: when only one scope type is passed,
        # add an explicit scope=X filter in must to prevent cross-scope leakage
        only_project = bool(project_ids) and not collection_ids and not dossier_ids
        only_personal = bool(dossier_ids) and not collection_ids and not project_ids

        if only_project:
            must_conditions.append(
                FieldCondition(key="scope", match=MatchValue(value="project"))
            )
        elif only_personal:
            must_conditions.append(
                FieldCondition(key="scope", match=MatchValue(value="personal"))
            )

        # Build scope filter (OR between scope-specific id filters)
        scope_should: list = []

        if collection_ids is not None:
            for cid in collection_ids:
                scope_should.append(
                    FieldCondition(
                        key="collection_id",
                        match=MatchValue(value=str(cid)),
                    )
                )

        if dossier_ids is not None:
            for did in dossier_ids:
                scope_should.append(
                    FieldCondition(
                        key="dossier_id",
                        match=MatchValue(value=str(did)),
                    )
                )

        if project_ids is not None:
            for pid in project_ids:
                scope_should.append(
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=str(pid)),
                    )
                )

        if not scope_should:
            logger.warning("vector_search_no_scope", extra={
                "tenant_id": str(tenant_id),
            })
            return []

        must_conditions.append(Filter(should=scope_should))

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

    async def delete_by_dossier_document(self, dossier_document_id: UUID, tenant_id: UUID) -> None:
        """Delete all personal chunks for a dossier document, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_dossier_document",
            "dossier_document_id": str(dossier_document_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="dossier_document_id",
                            match=MatchValue(value=str(dossier_document_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return
            raise

    async def delete_by_dossier(self, dossier_id: UUID, tenant_id: UUID) -> None:
        """Delete all personal chunks for an entire dossier, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_dossier",
            "dossier_id": str(dossier_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="dossier_id",
                            match=MatchValue(value=str(dossier_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return
            raise

    async def delete_by_project_document(
        self, project_document_id: UUID, tenant_id: UUID
    ) -> None:
        """Delete all project chunks for a project document, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_project_document",
            "project_document_id": str(project_document_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="project_document_id",
                            match=MatchValue(value=str(project_document_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return
            raise

    async def delete_by_project(self, project_id: UUID, tenant_id: UUID) -> None:
        """Delete all project chunks for an entire project, scoped to tenant."""
        logger.info("vector_store_delete", extra={
            "method": "delete_by_project",
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
        })
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="project_id",
                            match=MatchValue(value=str(project_id)),
                        ),
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                    ]
                ),
            )
        except UnexpectedResponse as e:
            if e.status_code == 404:
                return
            raise

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
