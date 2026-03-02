"""Image generation service for presentation slides.

Generates images from text prompts using OpenAI DALL-E, downloads the result,
and stores it in MinIO for persistence.
"""

import hashlib
import logging
from uuid import UUID

import httpx
from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class ImageService:
    """Generate images from text prompts and store them in MinIO."""

    def __init__(self) -> None:
        self.enabled = bool(settings.image_provider and settings.openai_api_key)
        if self.enabled:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = settings.image_model
            self.size = settings.image_size
            self.quality = settings.image_quality
            logger.info(
                "ImageService: enabled, model=%s size=%s quality=%s",
                self.model, self.size, self.quality,
            )
        else:
            self.client = None
            logger.info("ImageService: disabled (image_provider=%r)", settings.image_provider)

    async def generate_and_store(
        self,
        prompt: str,
        presentation_id: UUID,
        slide_position: int,
        field_name: str = "image",
    ) -> str | None:
        """Generate an image, download it, upload to MinIO, return the S3 key.

        Returns None if image generation is disabled or fails.
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Enhance prompt for presentation-quality images
            enhanced_prompt = (
                f"Professional presentation slide image: {prompt}. "
                "Clean, modern, minimalist style. High quality photography or illustration. "
                "No text or watermarks."
            )

            logger.info(
                "ImageService: generating image for slide %d field=%s prompt=%r",
                slide_position, field_name, prompt[:80],
            )

            response = await self.client.images.generate(
                model=self.model,
                prompt=enhanced_prompt,
                n=1,
                size=self.size,
                quality=self.quality,
                response_format="url",
            )

            image_url = response.data[0].url
            if not image_url:
                logger.warning("ImageService: empty URL from API")
                return None

            # Download the image
            async with httpx.AsyncClient(timeout=30) as http:
                img_response = await http.get(image_url)
                img_response.raise_for_status()
                image_bytes = img_response.content

            content_type = img_response.headers.get("content-type", "image/png")
            ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"

            # Build S3 key
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]
            s3_key = (
                f"generated-images/{presentation_id}/"
                f"slide_{slide_position}_{field_name}_{prompt_hash}.{ext}"
            )

            # Upload to MinIO
            from app.services.storage import storage_service

            async with storage_service._get_client() as s3:
                await s3.put_object(
                    Bucket=storage_service.bucket,
                    Key=s3_key,
                    Body=image_bytes,
                    ContentType=content_type,
                )

            logger.info(
                "ImageService: stored %d bytes as %s",
                len(image_bytes), s3_key,
            )
            return s3_key

        except Exception as e:
            logger.warning(
                "ImageService: failed for slide %d field=%s: %s",
                slide_position, field_name, e,
            )
            return None

    async def get_presigned_url(self, s3_key: str, expires_in: int = 86400) -> str:
        """Get a presigned URL for a stored image (default 24h TTL)."""
        from app.services.storage import storage_service
        return await storage_service.get_presigned_url(s3_key, expires_in=expires_in)


# Singleton
image_service = ImageService()
