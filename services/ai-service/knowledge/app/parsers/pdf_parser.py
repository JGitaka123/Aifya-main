"""
PDF document parser using PyMuPDF (fitz).
Extracts text with page numbers and detects section headings.
"""

import re
from pathlib import Path

from structlog import get_logger

from app.parsers.base import ParsedDocument, ParsedPage

logger = get_logger(__name__)

_HEADING_PATTERN = re.compile(
    r"^(?:\d+\.[\d.]*\s+)?[A-Z][A-Za-z\s:,\-&/()]{3,80}$", re.MULTILINE
)


def _load_fitz():
    """
    Import PyMuPDF on first use.

    Kept out of the module import so the service starts, and every non-PDF
    endpoint keeps working, on an installation without PyMuPDF.

    @returns The fitz module
    @raises RuntimeError: If PyMuPDF is not installed
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PDF support needs PyMuPDF. Install it with "
            "'python -m pip install PyMuPDF' and restart the service."
        ) from exc
    return fitz


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """
    Parse a PDF file and extract text with page structure.

    @param file_path: Path to the PDF file
    @returns ParsedDocument with pages, headings, and metadata
    """
    fitz = _load_fitz()
    doc = fitz.open(str(file_path))
    pages: list[ParsedPage] = []

    metadata: dict[str, str] = {}
    pdf_meta = doc.metadata
    if pdf_meta:
        for key in ("title", "author", "subject", "creator"):
            val = pdf_meta.get(key, "")
            if val:
                metadata[key] = val

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        if not text.strip():
            continue

        section_titles: list[str] = []
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = "".join(
                    span["text"] for span in line.get("spans", [])
                ).strip()
                if not line_text or len(line_text) < 4:
                    continue

                spans = line.get("spans", [])
                if spans:
                    avg_size = sum(s["size"] for s in spans) / len(spans)
                    is_bold = any("bold" in s.get("font", "").lower() for s in spans)

                    if (avg_size >= 12.0 and is_bold) or avg_size >= 14.0:
                        section_titles.append(line_text)
                    elif _HEADING_PATTERN.match(line_text) and is_bold:
                        section_titles.append(line_text)

        pages.append(
            ParsedPage(
                page_number=page_num + 1,
                text=text.strip(),
                section_titles=section_titles,
            )
        )

    doc.close()
    logger.info(
        "pdf_parsed",
        file=str(file_path),
        pages=len(pages),
        total_pages=len(doc),
    )

    return ParsedDocument(
        pages=pages,
        total_pages=len(doc) if not doc.is_closed else len(pages),
        metadata=metadata,
    )
