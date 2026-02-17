"""S3/MinIO storage service."""

import hashlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator, BinaryIO
from uuid import UUID

import aioboto3
from botocore.config import Config

from app.config import get_settings

settings = get_settings()


class StorageService:
    """Service for file storage operations with S3/MinIO."""

    def __init__(self) -> None:
        self.session = aioboto3.Session()
        self.bucket = settings.s3_bucket
        self.config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator:
        """Get async S3 client."""
        async with self.session.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=self.config,
        ) as client:
            yield client

    def _build_key(self, tenant_id: UUID, collection_id: UUID, filename: str) -> str:
        """Build S3 key with tenant prefix for isolation."""
        return f"{tenant_id}/{collection_id}/{filename}"

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    async def upload_file(
        self,
        tenant_id: UUID,
        collection_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str, int]:
        """
        Upload file to S3.
        
        Returns:
            Tuple of (s3_key, content_hash, file_size)
        """
        s3_key = self._build_key(tenant_id, collection_id, filename)
        content_hash = self.compute_hash(content)
        file_size = len(content)

        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "tenant_id": str(tenant_id),
                    "collection_id": str(collection_id),
                    "content_hash": content_hash,
                },
            )

        return s3_key, content_hash, file_size

    async def download_file(self, s3_key: str) -> bytes:
        """Download file from S3."""
        async with self._get_client() as client:
            response = await client.get_object(Bucket=self.bucket, Key=s3_key)
            content = await response["Body"].read()
            return content

    async def delete_file(self, s3_key: str) -> None:
        """Delete file from S3."""
        async with self._get_client() as client:
            await client.delete_object(Bucket=self.bucket, Key=s3_key)

    async def get_presigned_url(
        self,
        s3_key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate presigned URL for file download."""
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url

    async def file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3."""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self.bucket, Key=s3_key)
                return True
            except Exception:
                return False


# Singleton instance
storage_service = StorageService()
