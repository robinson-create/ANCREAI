"""Web crawler service — fetch and parse web pages for RAG indexing."""

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "AncreBot/1.0 (RAG indexer)",
    "Accept": "text/html,application/xhtml+xml",
}
_TIMEOUT = 30.0
_MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB


@dataclass
class CrawlResult:
    url: str
    title: str
    text: str


async def crawl_url(url: str) -> CrawlResult:
    """Fetch a URL and extract its text content.

    Args:
        url: The URL to crawl.

    Returns:
        CrawlResult with extracted title and text.

    Raises:
        httpx.HTTPError: On network/HTTP errors.
        ValueError: If content is too large or not HTML.
    """
    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError(f"Not an HTML page: {content_type}")

        if len(resp.content) > _MAX_CONTENT_LENGTH:
            raise ValueError(f"Page too large: {len(resp.content)} bytes")

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Extract body text
    body = soup.find("body") or soup
    text = body.get_text(separator=" ", strip=True)

    # Collapse whitespace
    text = " ".join(text.split())

    if not text:
        raise ValueError(f"No text content extracted from {url}")

    return CrawlResult(url=url, title=title, text=text)
