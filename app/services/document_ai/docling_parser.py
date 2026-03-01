"""Docling-based document parser for structured content extraction.

Docling handles PDF, DOCX, XLSX, PPTX, HTML, images, and more,
producing a unified structured document representation.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from app.core.parsing import ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)

# Lazy import to avoid heavy startup cost
_converter = None


def _get_converter():
    """Lazy-init the Docling DocumentConverter singleton."""
    global _converter
    if _converter is not None:
        return _converter

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        EasyOcrOptions,
    )
    from docling.document_converter import (
        DocumentConverter,
        PdfFormatOption,
        ImageFormatOption,
    )

    # PDF pipeline: enable OCR + table structure
    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = True
    pdf_options.do_table_structure = True
    pdf_options.ocr_options = EasyOcrOptions(force_full_page_ocr=False)

    # Image pipeline: always OCR
    image_options = ImageFormatOption(
        pipeline_cls_name="docling.pipeline.simple_pipeline.SimplePipeline",
    )

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            InputFormat.IMAGE: image_options,
        }
    )
    logger.info("Docling DocumentConverter initialized")
    return _converter


def _parse_with_docling_sync(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> ParsedDocument:
    """Synchronous Docling conversion (runs in thread pool)."""
    converter = _get_converter()

    # Write to temp file (Docling needs a file path)
    suffix = Path(filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        tmp_path = Path(tmp.name)

        result = converter.convert(str(tmp_path), raises_on_error=False)

    status_name = result.status.name if hasattr(result.status, "name") else str(result.status)

    if status_name == "FAILURE":
        error_msgs = [str(e) for e in (result.errors or [])]
        raise RuntimeError(
            f"Docling conversion failed for {filename}: {'; '.join(error_msgs) or 'unknown error'}"
        )

    doc = result.document

    # Extract pages
    pages: list[ParsedPage] = []

    if doc.pages:
        # Page-based extraction
        for page_num in sorted(doc.pages.keys()):
            page_item = doc.pages[page_num]
            # Collect text items that belong to this page
            page_texts = []
            for text_item in doc.texts:
                # Check if text item belongs to this page via provenance
                if hasattr(text_item, "prov") and text_item.prov:
                    for prov in text_item.prov:
                        if hasattr(prov, "page_no") and prov.page_no == page_num:
                            page_texts.append(text_item.text)
                            break

            content = "\n".join(page_texts) if page_texts else ""
            if content.strip():
                pages.append(ParsedPage(
                    page_number=page_num,
                    content=content,
                    metadata={"parser": "docling"},
                ))

    # Fallback: if no page-level content, use full markdown export
    if not pages:
        full_text = doc.export_to_markdown()
        if full_text.strip():
            pages.append(ParsedPage(
                page_number=1,
                content=full_text,
                metadata={"parser": "docling", "export": "markdown"},
            ))

    # Extract metadata
    metadata = {}
    if hasattr(doc, "name") and doc.name:
        metadata["title"] = doc.name

    total_pages = len(doc.pages) if doc.pages else len(pages)

    return ParsedDocument(
        pages=pages,
        total_pages=max(total_pages, len(pages)),
        metadata=metadata,
        parser_used="docling",
    )


async def parse_with_docling(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> ParsedDocument:
    """Async wrapper — runs Docling in a thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _parse_with_docling_sync,
        file_bytes,
        filename,
        content_type,
    )
