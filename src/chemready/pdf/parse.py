"""Read a PDF into plain text, one entry per page, with PyMuPDF.

This is plain code, not AI. Page numbers start at 1, the way a person counts them,
so every extracted value can point back to the page an auditor would open.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf

# A real text page has hundreds of characters. Fewer than this, with an image on
# the page, means the page is most likely a scan (a photo of text).
MIN_TEXT_CHARS_PER_PAGE = 40


class PdfError(Exception):
    """The file cannot be read as a PDF. The message is safe to show to the user."""


@dataclass(frozen=True)
class PageText:
    """The text of one PDF page."""

    number: int
    text: str
    is_scanned: bool


@dataclass(frozen=True)
class ParsedDocument:
    """A whole PDF as text, plus facts the pipeline needs."""

    file_name: str
    file_hash: str
    pages: list[PageText]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def scanned_pages(self) -> list[int]:
        return [page.number for page in self.pages if page.is_scanned]

    @property
    def is_scanned(self) -> bool:
        """True when most pages have no real text. These files need OCR."""
        return self.page_count > 0 and len(self.scanned_pages) * 2 > self.page_count

    def page(self, number: int) -> PageText:
        """Return a page by its 1-based number."""
        if not 1 <= number <= self.page_count:
            raise IndexError(f"page {number} does not exist (document has {self.page_count} pages)")
        return self.pages[number - 1]

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)


def file_hash(data: bytes) -> str:
    """SHA-256 of the file bytes. The same file always gives the same hash, so duplicates are found."""
    return hashlib.sha256(data).hexdigest()


def parse_pdf_bytes(data: bytes, file_name: str = "document.pdf") -> ParsedDocument:
    """Read PDF bytes into text per page."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
        raise PdfError("This file is not a readable PDF.") from error

    with document:
        if document.needs_pass:
            raise PdfError("This PDF is password protected. Ask the supplier for an unlocked copy.")
        if document.page_count == 0:
            raise PdfError("This PDF has no pages.")

        pages = []
        for index, page in enumerate(document):
            text = page.get_text("text", sort=True).strip()
            has_images = bool(page.get_images(full=False))
            is_scanned = len(text) < MIN_TEXT_CHARS_PER_PAGE and has_images
            pages.append(PageText(number=index + 1, text=text, is_scanned=is_scanned))

    return ParsedDocument(file_name=file_name, file_hash=file_hash(data), pages=pages)


def parse_pdf(path: Path) -> ParsedDocument:
    """Read a PDF file from disk."""
    return parse_pdf_bytes(path.read_bytes(), file_name=path.name)
