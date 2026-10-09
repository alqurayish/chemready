"""Find the 16 GHS sections in SDS text, whatever the layout.

GHS fixes the order and topic of the 16 sections, but suppliers write the headings
in many ways: "SECTION 2: Hazards identification", "2. HAZARD IDENTIFICATION",
"Section 2 - Hazard(s) identification". We accept a heading when:

* it starts with the word "Section" and a number, or
* it starts with a number and its title contains a keyword for that section,

and the section numbers appear in increasing order.
"""

import re
from dataclasses import dataclass

from chemready.pdf.parse import ParsedDocument

SECTION_KEYWORDS: dict[int, tuple[str, ...]] = {
    1: ("identification", "identity", "product and company"),
    2: ("hazard",),
    3: ("composition", "ingredient"),
    4: ("first aid", "first-aid"),
    5: ("fire", "firefighting", "fire-fighting"),
    6: ("accidental release", "spill"),
    7: ("handling", "storage"),
    8: ("exposure", "personal protection"),
    9: ("physical", "chemical properties"),
    10: ("stability", "reactivity"),
    11: ("toxicolog",),
    12: ("ecolog", "environmental"),
    13: ("disposal",),
    14: ("transport",),
    15: ("regulatory",),
    16: ("other information", "other"),
}

ALL_SECTIONS = tuple(range(1, 17))

_SECTION_WORD = re.compile(r"^\s*section\s*(\d{1,2})\b\s*[:.\-)]*\s*(.*)$", re.IGNORECASE)
_NUMBERED = re.compile(r"^\s*(\d{1,2})\s*[.:)]\s*(?!\d)(.{3,120})$")


@dataclass(frozen=True)
class SectionPage:
    """The part of one page that belongs to a section."""

    page: int
    text: str


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    parts: list[SectionPage]

    @property
    def text(self) -> str:
        return "\n".join(part.text for part in self.parts)

    @property
    def start_page(self) -> int:
        return self.parts[0].page

    @property
    def end_page(self) -> int:
        return self.parts[-1].page


@dataclass(frozen=True)
class _Heading:
    number: int
    title: str
    line_index: int


def _heading_in_line(line: str) -> tuple[int, str] | None:
    match = _SECTION_WORD.match(line)
    if match:
        number = int(match.group(1))
        return (number, match.group(2).strip()) if number in SECTION_KEYWORDS else None
    match = _NUMBERED.match(line)
    if match:
        number, title = int(match.group(1)), match.group(2).strip()
        keywords = SECTION_KEYWORDS.get(number, ())
        if any(keyword in title.lower() for keyword in keywords):
            return number, title
    return None


def split_sections(document: ParsedDocument) -> dict[int, Section]:
    """Return the sections found, keyed by section number (1 to 16)."""
    lines: list[tuple[int, str]] = [
        (page.number, line) for page in document.pages for line in page.text.splitlines()
    ]

    headings: list[_Heading] = []
    last_number = 0
    for index, (_, line) in enumerate(lines):
        found = _heading_in_line(line)
        if found and found[0] > last_number:
            headings.append(_Heading(number=found[0], title=found[1], line_index=index))
            last_number = found[0]

    sections: dict[int, Section] = {}
    for position, heading in enumerate(headings):
        end = headings[position + 1].line_index if position + 1 < len(headings) else len(lines)
        parts: list[SectionPage] = []
        for page_number, line in lines[heading.line_index : end]:
            if parts and parts[-1].page == page_number:
                parts[-1] = SectionPage(page=page_number, text=f"{parts[-1].text}\n{line}")
            else:
                parts.append(SectionPage(page=page_number, text=line))
        sections[heading.number] = Section(number=heading.number, title=heading.title, parts=parts)
    return sections


def missing_sections(sections: dict[int, Section]) -> list[int]:
    """Section numbers that were not found. Used for the "Missing sections" action flag."""
    return [number for number in ALL_SECTIONS if number not in sections]
