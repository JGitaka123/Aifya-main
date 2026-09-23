"""
Section-aware semantic chunker for institutional documents.
Preserves section headings as metadata for citation context.
"""

from dataclasses import dataclass, field

from structlog import get_logger

from app.config import get_settings
from app.parsers.base import ParsedDocument

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TextChunk:
    """
    A chunked text passage with metadata.

    @param text: Chunk text content
    @param chunk_index: Position in the document (0-based)
    @param page_number: Source page number
    @param section_title: Nearest section heading
    @param token_count: Approximate token count
    """

    text: str
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    token_count: int = 0


def _estimate_tokens(text: str) -> int:
    """
    Rough token estimate: ~4 chars per token for English.

    @param text: Input text
    @returns Approximate token count
    """
    return max(1, len(text) // 4)


def chunk_document(
    parsed: ParsedDocument,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Split a parsed document into overlapping text chunks.
    Preserves section headings and page numbers for citation.

    Strategy:
    1. Walk through pages sequentially.
    2. Track the most recent section heading.
    3. Split on sentence boundaries ('. ', '\\n') within chunk_size.
    4. Apply overlap from the previous chunk.

    @param parsed: ParsedDocument from a parser
    @param chunk_size: Max tokens per chunk (default from settings)
    @param chunk_overlap: Token overlap between chunks (default from settings)
    @returns List of TextChunk with metadata
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap
    max_chars = chunk_size * 4
    overlap_chars = chunk_overlap * 4

    chunks: list[TextChunk] = []
    chunk_index = 0
    current_section: str | None = None

    for page in parsed.pages:
        if page.section_titles:
            current_section = page.section_titles[-1]

        text = page.text.strip()
        if not text:
            continue

        sentences = _split_sentences(text)
        buffer: list[str] = []
        buffer_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if buffer_len + sentence_len > max_chars and buffer:
                chunk_text = " ".join(buffer)
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=current_section,
                        token_count=_estimate_tokens(chunk_text),
                    )
                )
                chunk_index += 1

                overlap_text = " ".join(buffer)
                overlap_sentences: list[str] = []
                running = 0
                for s in reversed(buffer):
                    if running + len(s) > overlap_chars:
                        break
                    overlap_sentences.insert(0, s)
                    running += len(s) + 1

                buffer = overlap_sentences
                buffer_len = sum(len(s) for s in buffer)

            buffer.append(sentence)
            buffer_len += sentence_len + 1

        if buffer:
            chunk_text = " ".join(buffer)
            if chunk_text.strip():
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        section_title=current_section,
                        token_count=_estimate_tokens(chunk_text),
                    )
                )
                chunk_index += 1

    logger.info(
        "document_chunked",
        total_chunks=len(chunks),
        total_tokens=sum(c.token_count for c in chunks),
    )
    return chunks


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentence-like segments.
    Handles common abbreviations to avoid false splits.

    @param text: Input text
    @returns List of sentence strings
    """
    import re

    text = re.sub(r"\n{2,}", " [PARA] ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    segments = re.split(r"(?<=[.!?])\s+|\[PARA\]", text)
    return [s.strip() for s in segments if s.strip()]
