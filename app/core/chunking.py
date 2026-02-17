"""Text chunking with fixed size and overlap."""

import hashlib
from dataclasses import dataclass

import tiktoken

from app.config import get_settings
from app.core.parsing import ParsedDocument, ParsedPage

settings = get_settings()


@dataclass
class TextChunk:
    """A chunk of text with metadata."""

    content: str
    content_hash: str
    token_count: int
    chunk_index: int
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    section_title: str | None = None


class Chunker:
    """Fixed-size chunker with overlap."""

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
        encoding_name: str = "cl100k_base",  # GPT-4 / text-embedding-3 encoding
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def _compute_hash(self, text: str) -> str:
        """Compute hash of chunk content."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences for better chunk boundaries."""
        import re
        
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        section_title: str | None = None,
    ) -> list[TextChunk]:
        """Chunk a single text block."""
        if not text or not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        chunks = []
        current_chunk: list[str] = []
        current_tokens = 0
        chunk_index = 0
        text_offset = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If single sentence exceeds chunk size, split by tokens
            if sentence_tokens > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(TextChunk(
                        content=chunk_text,
                        content_hash=self._compute_hash(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index,
                        page_number=page_number,
                        start_offset=text_offset - len(chunk_text),
                        end_offset=text_offset,
                        section_title=section_title,
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Split long sentence by tokens
                tokens = self.encoding.encode(sentence)
                for i in range(0, len(tokens), self.chunk_size - self.chunk_overlap):
                    chunk_tokens = tokens[i:i + self.chunk_size]
                    chunk_text = self.encoding.decode(chunk_tokens)
                    chunks.append(TextChunk(
                        content=chunk_text,
                        content_hash=self._compute_hash(chunk_text),
                        token_count=len(chunk_tokens),
                        chunk_index=chunk_index,
                        page_number=page_number,
                        start_offset=text_offset,
                        end_offset=text_offset + len(chunk_text),
                        section_title=section_title,
                    ))
                    chunk_index += 1
                    text_offset += len(chunk_text)
                continue

            # Check if adding sentence exceeds chunk size
            if current_tokens + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    start = text_offset - len(chunk_text)
                    chunks.append(TextChunk(
                        content=chunk_text,
                        content_hash=self._compute_hash(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index,
                        page_number=page_number,
                        start_offset=start,
                        end_offset=text_offset,
                        section_title=section_title,
                    ))
                    chunk_index += 1

                    # Keep overlap sentences
                    overlap_tokens = 0
                    overlap_sentences = []
                    for s in reversed(current_chunk):
                        s_tokens = self.count_tokens(s)
                        if overlap_tokens + s_tokens <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_tokens += s_tokens
                        else:
                            break
                    
                    current_chunk = overlap_sentences
                    current_tokens = overlap_tokens

            current_chunk.append(sentence)
            current_tokens += sentence_tokens
            text_offset += len(sentence) + 1  # +1 for space

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(TextChunk(
                content=chunk_text,
                content_hash=self._compute_hash(chunk_text),
                token_count=current_tokens,
                chunk_index=chunk_index,
                page_number=page_number,
                start_offset=text_offset - len(chunk_text),
                end_offset=text_offset,
                section_title=section_title,
            ))

        return chunks

    def chunk_document(self, doc: ParsedDocument) -> list[TextChunk]:
        """Chunk a parsed document."""
        all_chunks: list[TextChunk] = []
        global_index = 0

        for page in doc.pages:
            section_title = page.metadata.get("section_title")
            page_chunks = self.chunk_text(
                page.content,
                page_number=page.page_number,
                section_title=section_title,
            )
            
            # Update global indices
            for chunk in page_chunks:
                chunk.chunk_index = global_index
                global_index += 1
                all_chunks.append(chunk)

        return all_chunks


# Singleton chunker
chunker = Chunker()


def chunk_document(doc: ParsedDocument) -> list[TextChunk]:
    """Chunk a parsed document using default chunker."""
    return chunker.chunk_document(doc)
