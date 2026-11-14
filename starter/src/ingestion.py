"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page while preserving its source and page number.

    Pages with no extractable text are returned with empty text and an explicit
    ``no_text`` extraction status. OCR, when needed, is a separate step.
    """
    reader = PdfReader(path)
    pages: list[DocumentPage] = []

    for page_number, pdf_page in enumerate(reader.pages, start=1):
        text = normalize_text(pdf_page.extract_text() or "")
        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_number,
                text=text,
                metadata={
                    "extraction_status": "extracted" if text else "no_text",
                    "char_count": len(text),
                },
            )
        )

    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving line and paragraph breaks."""
    normalized = unicodedata.normalize("NFC", text.replace("\x00", ""))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    lines = [
        re.sub(r"[ \t\f\v]+", " ", line).strip()
        for line in normalized.split("\n")
    ]
    normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return normalized.strip()
