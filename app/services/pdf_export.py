"""PDF export service — DocModel -> HTML (Jinja2) -> PDF (Playwright) -> S3."""

import logging
import re
from datetime import date
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader

from app.config import get_settings
from app.schemas.workspace_document import DocModel
from app.services.storage import storage_service

settings = get_settings()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "pdf"


def _prosemirror_to_html(node: dict) -> str:
    """Convert a ProseMirror JSON node to HTML (simplified)."""
    if not node or not isinstance(node, dict):
        return ""

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")
    marks = node.get("marks", [])
    attrs = node.get("attrs", {})

    # Text nodes
    if node_type == "text":
        result = text
        for mark in marks:
            mark_type = mark.get("type", "")
            if mark_type == "bold":
                result = f"<strong>{result}</strong>"
            elif mark_type == "italic":
                result = f"<em>{result}</em>"
            elif mark_type == "link":
                href = mark.get("attrs", {}).get("href", "#")
                result = f'<a href="{href}">{result}</a>'
            elif mark_type == "code":
                result = f"<code>{result}</code>"
        return result

    # Recursively render children
    children_html = "".join(_prosemirror_to_html(child) for child in content)

    # Block nodes
    tag_map = {
        "doc": ("", ""),
        "paragraph": ("<p>", "</p>"),
        "heading": (f"<h{attrs.get('level', 1)}>", f"</h{attrs.get('level', 1)}>"),
        "bulletList": ("<ul>", "</ul>"),
        "orderedList": ("<ol>", "</ol>"),
        "listItem": ("<li>", "</li>"),
        "blockquote": ("<blockquote>", "</blockquote>"),
        "codeBlock": ("<pre><code>", "</code></pre>"),
        "hardBreak": ("<br>", ""),
        "horizontalRule": ("<hr>", ""),
    }

    if node_type in tag_map:
        open_tag, close_tag = tag_map[node_type]
        return f"{open_tag}{children_html}{close_tag}"

    # Fallback: just render children
    return children_html


class PdfExportService:
    """DocModel -> HTML (Jinja2) -> PDF (Playwright) -> S3."""

    def __init__(self) -> None:
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    def render_html(
        self,
        title: str,
        doc_model: DocModel,
        template_name: str = "default.html",
    ) -> str:
        """Render DocModel to HTML using a Jinja2 template."""
        template = self.jinja_env.get_template(template_name)

        # Pre-process blocks: convert ProseMirror JSON to HTML for rich text blocks
        blocks_data = []
        for block in doc_model.blocks:
            block_dict = block.model_dump()
            if block.type in ("rich_text", "clause", "terms"):
                content = getattr(block, "content", {})
                block_dict["html_content"] = _prosemirror_to_html(content)
            blocks_data.append(block_dict)

        return template.render(
            title=title,
            meta=doc_model.meta.model_dump(),
            blocks=blocks_data,
            variables=doc_model.variables,
            sources=[s.model_dump() for s in doc_model.sources],
        )

    async def html_to_pdf(self, html: str, title: str = "") -> bytes:
        """Convert HTML to PDF using Playwright."""
        from playwright.async_api import async_playwright

        footer_html = (
            '<div style="width:100%;font-size:8px;color:#94a3b8;'
            'text-align:center;border-top:1px solid #e2e8f0;padding-top:4px;">'
            f'{title}'
            ' — page <span class="pageNumber"></span>/<span class="totalPages"></span>'
            '</div>'
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template='<span></span>',
                footer_template=footer_html,
                margin={"top": "20mm", "right": "15mm", "bottom": "20mm", "left": "15mm"},
            )
            await browser.close()

        return pdf_bytes

    async def export(
        self,
        doc_id: UUID,
        title: str,
        doc_model: DocModel,
        tenant_id: UUID,
    ) -> str:
        """Full pipeline: render HTML -> PDF -> upload to S3 -> return presigned URL."""
        # 1. Render HTML
        html = self.render_html(title, doc_model)

        # 2. Convert to PDF
        pdf_bytes = await self.html_to_pdf(html, title=title)

        # 3. Upload to S3 using a fixed collection_id for workspace exports
        exports_collection_id = UUID("00000000-0000-0000-0000-000000000000")
        # Filename: slugified title + date (e.g. "contrat-nda-2026-02-14.pdf")
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:80]
        today = date.today().isoformat()
        filename = f"{slug}-{today}.pdf" if slug else f"{doc_id}.pdf"
        s3_key, _, _ = await storage_service.upload_file(
            tenant_id=tenant_id,
            collection_id=exports_collection_id,
            filename=filename,
            content=pdf_bytes,
            content_type="application/pdf",
        )

        # 4. Return presigned URL
        url = await storage_service.get_presigned_url(s3_key)
        return url


# Singleton
pdf_export_service = PdfExportService()
