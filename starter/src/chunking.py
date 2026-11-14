"""Chunk source pages while keeping source and metadata traceability."""
import re

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split a page into character windows with a fixed overlap."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be non-negative and smaller than size")
    if not page.text.strip():
        return []

    step = size - overlap
    texts: list[str] = []
    start = 0
    while start < len(page.text):
        end = min(start + size, len(page.text))
        texts.append(page.text[start:end].strip())
        if end == len(page.text):
            break
        start += step
    return _make_chunks(page, [text for text in texts if text], "fixed_size")


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group paragraphs up to a limit, splitting oversized blocks at boundaries."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    if not page.text.strip():
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", page.text.strip())
        if paragraph.strip()
    ]
    parts: list[tuple[int, str]] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        if len(paragraph) <= max_size:
            parts.append((paragraph_index, paragraph))
            continue

        segments = [
            segment.strip()
            for segment in re.split(r"(?<=[.!?])\s+|\n+", paragraph)
            if segment.strip()
        ]
        for segment in segments:
            if len(segment) <= max_size:
                parts.append((paragraph_index, segment))
            else:
                parts.extend(
                    (paragraph_index, piece)
                    for piece in _split_at_words(segment, max_size)
                )

    chunk_texts: list[str] = []
    current = ""
    current_paragraph: int | None = None
    for paragraph_index, part in parts:
        separator = "\n\n" if current and paragraph_index != current_paragraph else " "
        candidate = f"{current}{separator}{part}" if current else part
        if len(candidate) > max_size:
            chunk_texts.append(current)
            current = part
        else:
            current = candidate
        current_paragraph = paragraph_index

    if current:
        chunk_texts.append(current)

    return _make_chunks(page, chunk_texts, "by_paragraph")


def _split_at_words(text: str, max_size: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in text.split():
        if len(word) > max_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                word[start:start + max_size]
                for start in range(0, len(word), max_size)
            )
            continue

        candidate = f"{current} {word}" if current else word
        if len(candidate) > max_size:
            pieces.append(current)
            current = word
        else:
            current = candidate

    if current:
        pieces.append(current)
    return pieces


def _make_chunks(page: DocumentPage, texts: list[str], strategy: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    for index, text in enumerate(texts):
        metadata = dict(page.metadata)
        metadata.update(
            {
                "chunk_strategy": strategy,
                "chunk_index": index,
                "chunk_char_count": len(text),
            }
        )
        chunks.append(
            Chunk(
                chunk_id=f"{page.document_id}:p{page.page}:{strategy}:{index:04d}",
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=text,
                metadata=metadata,
            )
        )
    return chunks
