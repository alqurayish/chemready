"""Tests for PDF parsing, scan detection and GHS section splitting."""

from pathlib import Path

import pymupdf
import pytest

from chemready.demo.synthetic import SyntheticSds, make_scanned_pdf, make_sds_pdf
from chemready.pdf.parse import PdfError, file_hash, parse_pdf, parse_pdf_bytes
from chemready.pdf.sections import ALL_SECTIONS, missing_sections, split_sections


def _spec(**changes: object) -> SyntheticSds:
    spec = SyntheticSds(
        product_name="Demowet NF",
        supplier="Example Auxiliaries Ltd",
        revision_date="01.03.2025",
        signal_word="Warning",
        hazards=[("H315", "Causes skin irritation."), ("H319", "Causes serious eye irritation.")],
        pictograms=["GHS07"],
        ingredients=[("Water", "7732-18-5", "75-85%"), ("Alcohol ethoxylate", None, "10-20%")],
    )
    for name, value in changes.items():
        setattr(spec, name, value)
    return spec


def test_text_is_read_per_page_with_numbers_starting_at_1() -> None:
    parsed = parse_pdf_bytes(make_sds_pdf(_spec()), file_name="demo.pdf")

    assert parsed.file_name == "demo.pdf"
    assert parsed.page_count >= 2
    assert [page.number for page in parsed.pages] == list(range(1, parsed.page_count + 1))
    assert "Product name: Demowet NF" in parsed.page(1).text
    assert not parsed.is_scanned


def test_same_bytes_give_the_same_hash_for_duplicate_detection() -> None:
    data = make_sds_pdf(_spec())

    assert parse_pdf_bytes(data).file_hash == file_hash(data)
    assert file_hash(data) != file_hash(make_sds_pdf(_spec(product_name="Other")))


def test_parse_pdf_reads_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "sds.pdf"
    path.write_bytes(make_sds_pdf(_spec()))

    assert parse_pdf(path).file_name == "sds.pdf"


def test_page_outside_range_raises() -> None:
    parsed = parse_pdf_bytes(make_sds_pdf(_spec()))

    with pytest.raises(IndexError):
        parsed.page(0)


def test_image_only_pdf_is_detected_as_scanned() -> None:
    parsed = parse_pdf_bytes(make_scanned_pdf(pages=3))

    assert parsed.is_scanned
    assert parsed.scanned_pages == [1, 2, 3]


def test_not_a_pdf_gives_a_clear_error() -> None:
    with pytest.raises(PdfError, match="not a readable PDF"):
        parse_pdf_bytes(b"this is a spreadsheet, not a pdf")


def test_password_protected_pdf_gives_a_clear_error() -> None:
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")

    with pytest.raises(PdfError, match="password protected"):
        parse_pdf_bytes(data)


@pytest.mark.parametrize("style", ["section_word", "numbered_caps"])
def test_all_16_sections_are_found_in_both_heading_styles(style: str) -> None:
    parsed = parse_pdf_bytes(make_sds_pdf(_spec(heading_style=style)))

    sections = split_sections(parsed)

    assert sorted(sections) == list(ALL_SECTIONS)
    assert missing_sections(sections) == []
    assert "Signal word: Warning" in sections[2].text
    assert "CAS 7732-18-5" in sections[3].text
    assert "Signal word" not in sections[3].text


def test_section_remembers_its_pages() -> None:
    parsed = parse_pdf_bytes(make_sds_pdf(_spec(), lines_per_page=12))

    sections = split_sections(parsed)

    assert sections[1].start_page == 1
    assert sections[16].end_page == parsed.page_count
    for section in sections.values():
        for part in section.parts:
            assert part.text.splitlines()[0] in parsed.page(part.page).text


def test_missing_sections_are_reported() -> None:
    parsed = parse_pdf_bytes(make_sds_pdf(_spec(omit_sections=(8, 9))))

    assert missing_sections(split_sections(parsed)) == [8, 9]


def test_numbered_lists_inside_a_section_are_not_mistaken_for_headings() -> None:
    spec = _spec(extra_lines={4: ["1. Move the person to fresh air.", "2. Rinse skin with water."]})

    sections = split_sections(parse_pdf_bytes(make_sds_pdf(spec)))

    assert "Rinse skin with water" in sections[4].text
    assert sections[2].title.lower().startswith("hazard")
