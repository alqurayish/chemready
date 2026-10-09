"""Make fictional SDS PDFs for tests, demos and pipeline checks.

These files are NOT real safety data sheets. Product and supplier names are made
up, and hazard data is illustrative only. They exist so the software can be
tested without any private factory files. Accuracy claims must come from real,
hand-labelled SDS files (see docs/data/collecting-sds.md), never from these.
"""

from dataclasses import dataclass, field
from typing import Literal

import pymupdf

SECTION_TITLES: dict[int, str] = {
    1: "Identification",
    2: "Hazard(s) identification",
    3: "Composition/information on ingredients",
    4: "First-aid measures",
    5: "Fire-fighting measures",
    6: "Accidental release measures",
    7: "Handling and storage",
    8: "Exposure controls/personal protection",
    9: "Physical and chemical properties",
    10: "Stability and reactivity",
    11: "Toxicological information",
    12: "Ecological information",
    13: "Disposal considerations",
    14: "Transport information",
    15: "Regulatory information",
    16: "Other information",
}

HeadingStyle = Literal["section_word", "numbered_caps"]


@dataclass
class SyntheticSds:
    """Everything needed to draw one fictional SDS."""

    product_name: str
    supplier: str
    revision_date: str  # as printed, for example "01.03.2025"
    signal_word: str | None
    hazards: list[tuple[str, str]] = field(default_factory=list)  # (H code, statement)
    pictograms: list[str] = field(default_factory=list)  # e.g. "GHS07"
    ingredients: list[tuple[str, str | None, str]] = field(default_factory=list)  # (name, CAS, percent)
    storage: str = "Store in a cool, dry place. Keep container tightly closed."
    ppe: str = "Protective gloves, safety goggles"
    heading_style: HeadingStyle = "section_word"
    omit_sections: tuple[int, ...] = ()
    extra_lines: dict[int, list[str]] = field(default_factory=dict)  # more text per section


def _section_lines(spec: SyntheticSds, number: int) -> list[str]:
    if number == 1:
        lines = [
            f"Product name: {spec.product_name}",
            f"Supplier: {spec.supplier}",
            f"Revision date: {spec.revision_date}",
            "Recommended use: textile processing auxiliary",
        ]
    elif number == 2:
        if spec.signal_word is None and not spec.hazards:
            lines = ["Not classified as hazardous according to GHS."]
        else:
            lines = [f"Signal word: {spec.signal_word}", "Hazard statements:"]
            lines += [f"{code} {text}" for code, text in spec.hazards]
            lines += [f"Pictogram: {code}" for code in spec.pictograms]
    elif number == 3:
        lines = []
        for name, cas, percent in spec.ingredients:
            cas_text = f"CAS {cas}" if cas else "CAS: not disclosed (trade secret)"
            lines.append(f"{name}   {cas_text}   {percent}")
    elif number == 7:
        lines = [spec.storage]
    elif number == 8:
        lines = [f"PPE: {spec.ppe}"]
    else:
        lines = ["No specific information."]
    return lines + spec.extra_lines.get(number, [])


def _heading(spec: SyntheticSds, number: int) -> str:
    title = SECTION_TITLES[number]
    if spec.heading_style == "numbered_caps":
        return f"{number}. {title.upper()}"
    return f"SECTION {number}: {title}"


def make_sds_pdf(spec: SyntheticSds, lines_per_page: int = 34) -> bytes:
    """Draw the SDS as a simple text PDF and return its bytes."""
    lines = ["SAFETY DATA SHEET", "Prepared according to GHS. FICTIONAL TEST DOCUMENT.", ""]
    for number in range(1, 17):
        if number in spec.omit_sections:
            continue
        lines.append(_heading(spec, number))
        lines += _section_lines(spec, number)
        lines.append("")

    document = pymupdf.open()
    for start in range(0, len(lines), lines_per_page):
        page = document.new_page(width=595, height=842)  # A4 in points
        y = 60.0
        for line in lines[start : start + lines_per_page]:
            page.insert_text((50, y), line, fontsize=10, fontname="helv")
            y += 21
    data: bytes = document.tobytes()
    document.close()
    return data


def make_scanned_pdf(pages: int = 2) -> bytes:
    """A PDF whose pages are images only, like a scanned paper SDS."""
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 280), False)
    pixmap.clear_with(200)
    for _ in range(pages):
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, pixmap=pixmap)
    data: bytes = document.tobytes()
    document.close()
    return data
