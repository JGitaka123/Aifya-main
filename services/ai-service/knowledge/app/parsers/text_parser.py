"""
Plain text / Markdown parser.
Splits on natural section boundaries.
"""

import re
from pathlib import Path

from structlog import get_logger

from app.parsers.base import ParsedDocument, ParsedPage

logger = get_logger(__name__)

_SECTION_PATTERN = re.compile(
    r"^(?:#{1,4}\s+.+|[A-Z][A-Za-z\s:,\-&/()]{3,80}|"
    r"\d+\.[\d.]*\s+[A-Z].+)$",
    re.MULTILINE,
)
_CHARS_PER_PAGE = 3000


def parse_text(file_path: str | Path) -> ParsedDocument:
    """
    Parse a plain text or Markdown file.

    @param file_path: Path to the text file
    @returns ParsedDocument with pseudo-pages
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")

    pages: list[ParsedPage] = []
    page_num = 1
    start = 0

    while start < len(content):
        end = min(start + _CHARS_PER_PAGE, len(content))

        if end < len(content):
            newline_pos = content.rfind("\n\n", start, end)
            if newline_pos > start:
                end = newline_pos + 2

        chunk = content[start:end].strip()
        if chunk:
            sections = _SECTION_PATTERN.findall(chunk)
            pages.append(
                ParsedPage(
                    page_number=page_num,
                    text=chunk,
                    section_titles=[s.strip().lstrip("#").strip() for s in sections],
                )
            )
            page_num += 1

        start = end

    logger.info("text_parsed", file=str(file_path), pages=len(pages))
    return ParsedDocument(pages=pages, total_pages=len(pages), metadata={})
