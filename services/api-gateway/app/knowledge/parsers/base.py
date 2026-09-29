"""
Document parsing module.
Extracts raw text and page structure from uploaded files.
"""

from dataclasses import dataclass, field


@dataclass
class ParsedPage:
    """
    A single page of extracted content.

    @param page_number: 1-based page number
    @param text: Extracted text content
    @param section_titles: Detected section headings on this page
    """

    page_number: int
    text: str
    section_titles: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """
    Full parsed output from a document.

    @param pages: List of parsed pages
    @param total_pages: Total page count
    @param metadata: Additional metadata from parsing (author, title, etc.)
    """

    pages: list[ParsedPage]
    total_pages: int
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Concatenated text from all pages."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())
