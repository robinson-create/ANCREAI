"""Mistral OCR client for PDF text extraction."""

import base64
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"


class OCRProviderError(Exception):
    """Raised when the OCR provider fails."""


async def ocr_pdf(
    file_bytes: bytes,
    filename: str,
    model: str | None = None,
) -> list[dict]:
    """
    Extract text from a PDF using Mistral OCR.

    Returns:
        List of pages: [{"page": 1, "text": "...", "meta": {...}}, ...]
    """
    model = model or settings.mistral_ocr_model
    api_key = settings.mistral_api_key

    if not api_key:
        raise OCRProviderError("MISTRAL_API_KEY is not configured")

    # Encode file as base64 data URI
    b64 = base64.b64encode(file_bytes).decode("ascii")
    document_url = f"data:application/pdf;base64,{b64}"

    payload = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": document_url,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                MISTRAL_OCR_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Mistral OCR HTTP error %s: %s", e.response.status_code, e.response.text[:500])
        raise OCRProviderError(f"Mistral OCR returned {e.response.status_code}") from e
    except httpx.RequestError as e:
        logger.error("Mistral OCR request error: %s", e)
        raise OCRProviderError(f"Mistral OCR request failed: {e}") from e

    data = response.json()

    # Parse response: Mistral OCR returns {"pages": [{"index": 0, "markdown": "..."}]}
    pages = []
    for page_data in data.get("pages", []):
        page_index = page_data.get("index", 0)
        markdown_text = page_data.get("markdown", "")

        pages.append({
            "page": page_index + 1,  # 1-based
            "text": markdown_text,
            "meta": {
                k: v
                for k, v in page_data.items()
                if k not in ("index", "markdown")
            } or None,
        })

    if not pages:
        logger.warning("Mistral OCR returned no pages for %s", filename)

    logger.info("Mistral OCR extracted %d pages from %s", len(pages), filename)
    return pages
