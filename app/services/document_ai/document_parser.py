"""Central document parsing service.

Routes documents to the appropriate parser based on MIME type:
- Primary: Docling (PDF, DOCX, XLSX, PPTX, HTML, images)
- Fallback OCR: Mistral OCR (scanned PDFs, complex images)
- Legacy: native parsers for simple text/markdown
"""

import logging
from pathlib import Path
from typing import Literal

from app.core.parsing import ParsedDocument, ParsedPage, parse_document

logger = logging.getLogger(__name__)

# MIME types that Docling handles well
DOCLING_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/html",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/bmp",
}

# Extension fallback for MIME type detection
EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".html": "text/html",
    ".htm": "text/html",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

# Image MIME types (always need OCR)
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/bmp",
}


def _resolve_mime(content_type: str, filename: str) -> str:
    """Resolve MIME type from content_type header or file extension."""
    if content_type and content_type != "application/octet-stream":
        return content_type
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_MIME.get(ext, content_type or "application/octet-stream")


async def extract_document_content(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> ParsedDocument:
    """Extract structured content from any document.

    Strategy:
    1. Resolve MIME type
    2. If Docling-compatible → try Docling
    3. If Docling fails or quality is poor → try Mistral OCR as fallback
    4. If neither works → fall back to native parsers
    5. For plain text/markdown → use native parsers directly

    Returns a ParsedDocument with metadata including parser_used and ocr_used.
    """
    from app.config import get_settings

    settings = get_settings()
    mime = _resolve_mime(content_type, filename)
    is_image = mime in IMAGE_MIME_TYPES
    is_pdf = mime == "application/pdf"
    use_docling = mime in DOCLING_MIME_TYPES

    # Simple text formats → native parser (no need for heavy tooling)
    if mime in ("text/plain", "text/markdown"):
        result = parse_document(file_bytes, filename, mime)
        result.metadata["ocr_used"] = False
        return result

    # Try Docling first for supported formats
    if use_docling:
        try:
            from app.services.document_ai.docling_parser import parse_with_docling

            result = await parse_with_docling(file_bytes, filename, mime)
            text_len = len(result.full_text.strip())

            # For images and scanned PDFs: if Docling extracted too little text,
            # try Mistral OCR as fallback
            if (is_image or is_pdf) and text_len < settings.ocr_heuristic_min_text_chars:
                logger.info(
                    "Docling extracted only %d chars for %s (threshold %d), trying Mistral OCR fallback",
                    text_len,
                    filename,
                    settings.ocr_heuristic_min_text_chars,
                )
                mistral_result = await _try_mistral_ocr(file_bytes, filename, mime)
                if mistral_result and len(mistral_result.full_text.strip()) > text_len:
                    logger.info(
                        "Mistral OCR produced better result (%d chars) for %s",
                        len(mistral_result.full_text.strip()),
                        filename,
                    )
                    return mistral_result

            result.metadata["ocr_used"] = is_image or result.parser_used == "docling"
            return result

        except Exception as e:
            logger.warning("Docling failed for %s: %s, trying fallback", filename, e)

    # Fallback: Mistral OCR for images and PDFs
    if (is_image or is_pdf) and settings.use_mistral_ocr and settings.mistral_api_key:
        mistral_result = await _try_mistral_ocr(file_bytes, filename, mime)
        if mistral_result:
            return mistral_result

    # Ultimate fallback: native parsers
    logger.info("Using native parser for %s (mime=%s)", filename, mime)
    result = parse_document(file_bytes, filename, mime)
    result.metadata["ocr_used"] = False
    return result


async def _try_mistral_ocr(
    file_bytes: bytes,
    filename: str,
    mime: str,
) -> ParsedDocument | None:
    """Try Mistral OCR, return None on failure."""
    from app.services.document_ai.mistral_ocr import OCRProviderError, ocr_document

    try:
        ocr_pages = await ocr_document(file_bytes, filename, mime)
        if not ocr_pages:
            return None

        pages = [
            ParsedPage(
                page_number=p["page"],
                content=p["text"],
                metadata={**(p.get("meta") or {}), "parser": "mistral_ocr"},
            )
            for p in ocr_pages
            if p["text"].strip()
        ]

        if not pages:
            return None

        return ParsedDocument(
            pages=pages,
            total_pages=len(ocr_pages),
            metadata={"ocr_used": True},
            parser_used="mistral_ocr",
        )
    except OCRProviderError as e:
        logger.warning("Mistral OCR failed for %s: %s", filename, e)
        return None
