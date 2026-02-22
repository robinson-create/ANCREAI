"""Citation registry — deduplicates citations across delegations.

When multiple assistants (parent + delegated children) produce citations,
this registry ensures no duplicate citations and preserves provenance.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CitationEntry:
    """A single citation with provenance tracking."""

    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int | None = None
    excerpt: str = ""
    score: float = 0.0
    url: str | None = None  # For web citations
    source_assistant_id: str | None = None  # Which assistant found this

    @property
    def dedup_key(self) -> str:
        """Key for deduplication: document + page (or chunk_id for unique chunks)."""
        if self.page_number is not None:
            return f"{self.document_id}:p{self.page_number}"
        return f"{self.document_id}:{self.chunk_id}"


class CitationRegistry:
    """Global registry for deduplicating citations across delegations.

    Used per agent run. The parent initializes it, child delegations
    merge their citations into it, and the final list is emitted.
    """

    def __init__(self) -> None:
        self._entries: dict[str, CitationEntry] = {}

    def add(self, entry: CitationEntry) -> bool:
        """Add a citation. Returns True if new, False if duplicate."""
        key = entry.dedup_key
        if key in self._entries:
            # Keep the one with higher score
            if entry.score > self._entries[key].score:
                self._entries[key] = entry
            return False
        self._entries[key] = entry
        return True

    def add_from_dict(self, citation: dict, source_assistant_id: str | None = None) -> bool:
        """Add a citation from a dict (as used in agent_loop citations)."""
        entry = CitationEntry(
            chunk_id=str(citation.get("chunk_id", "")),
            document_id=str(citation.get("document_id", "")),
            document_filename=str(citation.get("document_filename", "")),
            page_number=citation.get("page_number"),
            excerpt=str(citation.get("excerpt", "")),
            score=float(citation.get("score", 0.0)),
            url=citation.get("url"),
            source_assistant_id=source_assistant_id,
        )
        return self.add(entry)

    def merge(self, citations: list[dict], source_assistant_id: str | None = None) -> list[dict]:
        """Merge a list of citation dicts, returning only the new ones."""
        new_citations = []
        for cit in citations:
            if self.add_from_dict(cit, source_assistant_id):
                new_citations.append(cit)
        return new_citations

    def all_dicts(self) -> list[dict]:
        """Return all deduplicated citations as dicts."""
        return [
            {
                "chunk_id": e.chunk_id,
                "document_id": e.document_id,
                "document_filename": e.document_filename,
                "page_number": e.page_number,
                "excerpt": e.excerpt,
                "score": e.score,
                **({"url": e.url} if e.url else {}),
                **({"source_assistant_id": e.source_assistant_id} if e.source_assistant_id else {}),
            }
            for e in self._entries.values()
        ]

    @property
    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()
