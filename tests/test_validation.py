"""Unit tests for every validation rule and the action flags."""

from datetime import date

import pytest

from chemready.demo.synthetic import SyntheticSds, make_sds_pdf
from chemready.pdf.parse import ParsedDocument, parse_pdf_bytes
from chemready.schema import HazardStatement, Ingredient, Pictogram, SdsExtraction, Sourced
from chemready.validation.flags import product_flags
from chemready.validation.validate import FieldCheck, Status, summarise_checks, validate_extraction

SPEC = SyntheticSds(
    product_name="Demowet NF",
    supplier="Example Auxiliaries Ltd",
    revision_date="01.03.2025",
    signal_word="Warning",
    hazards=[("H315", "Causes skin irritation.")],
    pictograms=["GHS07"],
    ingredients=[("Water", "7732-18-5", "75-85%"), ("Alcohol ethoxylate", None, "10-20%")],
    extra_lines={16: ["Product name used in the old version: Totally Safe Cleaner"]},
)


@pytest.fixture(scope="module")
def document() -> ParsedDocument:
    return parse_pdf_bytes(make_sds_pdf(SPEC, lines_per_page=20))


def _page_of(document: ParsedDocument, text: str) -> int:
    return next(page.number for page in document.pages if text in page.text)


def _good(document: ParsedDocument) -> SdsExtraction:
    def at(quote: str) -> int:
        return _page_of(document, quote)

    return SdsExtraction(
        product_name=Sourced(value="Demowet NF", page=1, quote="Product name: Demowet NF"),
        supplier=Sourced(value="Example Auxiliaries Ltd", page=1, quote="Supplier: Example Auxiliaries Ltd"),
        revision_date=Sourced(value="2025-03-01", page=1, quote="Revision date: 01.03.2025"),
        signal_word=Sourced(value="Warning", page=at("Signal word: Warning"), quote="Signal word: Warning"),
        hazard_statements=[
            HazardStatement(code="H315", page=at("H315 Causes"), quote="H315 Causes skin irritation.")
        ],
        pictograms=[Pictogram(code="GHS07", page=at("Pictogram: GHS07"), quote="Pictogram: GHS07")],
        ingredients=[
            Ingredient(
                name="Water", cas_number="7732-18-5", page=at("CAS 7732-18-5"), quote="Water   CAS 7732-18-5"
            ),
            Ingredient(name="Alcohol ethoxylate", cas_number=None, page=at("not disclosed")),
        ],
        storage=Sourced(value=SPEC.storage, page=at("Store in a cool"), quote=SPEC.storage),
        ppe=Sourced(value=SPEC.ppe, page=at("PPE:"), quote=f"PPE: {SPEC.ppe}"),
    )


def _by_name(checks: list[FieldCheck]) -> dict[str, FieldCheck]:
    return {check.field_name: check for check in checks}


def test_a_fully_correct_extraction_passes(document: ParsedDocument) -> None:
    checks = _by_name(validate_extraction(_good(document), document))

    assert checks["product_name"].status is Status.PASSED
    assert checks["product_name"].confidence == 1.0
    assert checks["hazard_statements[0]"].status is Status.PASSED
    assert checks["ingredients[0].cas_number"].status is Status.PASSED
    assert checks["ingredients[1].cas_number"].status is Status.MISSING
    assert "hazard_statements" not in checks


def test_quote_not_in_pdf_removes_the_value(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.revision_date = Sourced(value="2025-04-12", page=1, quote="Revision date: 12.04.2025")

    check = _by_name(validate_extraction(extraction, document))["revision_date"]

    assert check.status is Status.NEEDS_REVIEW
    assert check.value is None
    assert check.reasons == ["Quote not found in the PDF. The value was removed."]


def test_value_without_quote_is_removed(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.supplier = Sourced(value="Example Auxiliaries Ltd", page=1, quote=None)

    check = _by_name(validate_extraction(extraction, document))["supplier"]

    assert check.value is None and "No quote" in check.reasons[0]


def test_wrong_page_goes_to_review_and_says_where(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.product_name.page = 2

    check = _by_name(validate_extraction(extraction, document))["product_name"]

    assert check.status is Status.NEEDS_REVIEW
    assert "It is on page 1" in check.reasons[0]
    assert check.value == "Demowet NF"  # kept: the quote is real, only the page is wrong


def test_quote_from_the_wrong_section_is_caught(document: ParsedDocument) -> None:
    """A prompt injection or a confused model taking a name from section 16."""
    extraction = _good(document)
    quote = "Product name used in the old version: Totally Safe Cleaner"
    extraction.product_name = Sourced(
        value="Totally Safe Cleaner", page=_page_of(document, quote), quote=quote
    )

    check = _by_name(validate_extraction(extraction, document))["product_name"]

    assert check.status is Status.NEEDS_REVIEW
    assert "not in section 1" in " ".join(check.reasons)


def test_value_that_does_not_match_its_quote(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.signal_word.value = "Danger"

    check = _by_name(validate_extraction(extraction, document))["signal_word"]

    assert "The value does not match its quote." in check.reasons


def test_wrong_cas_check_digit_is_flagged(document: ParsedDocument) -> None:
    pdf = parse_pdf_bytes(
        make_sds_pdf(SyntheticSds(**{**SPEC.__dict__, "ingredients": [("Water", "7732-18-6", "")]}))
    )
    extraction = SdsExtraction(
        ingredients=[
            Ingredient(cas_number="7732-18-6", page=_page_of(pdf, "7732-18-6"), quote="CAS 7732-18-6")
        ]
    )

    check = _by_name(validate_extraction(extraction, pdf))["ingredients[0].cas_number"]

    assert check.status is Status.NEEDS_REVIEW
    assert "CAS check digit is wrong" in " ".join(check.reasons)


def test_malformed_h_code_is_flagged() -> None:
    pdf = parse_pdf_bytes(
        make_sds_pdf(SyntheticSds(**{**SPEC.__dict__, "hazards": [("H3l9", "Eye irritation.")]}))
    )
    extraction = SdsExtraction(
        hazard_statements=[
            HazardStatement(code="H3l9", page=_page_of(pdf, "H3l9"), quote="H3l9 Eye irritation.")
        ]
    )

    check = _by_name(validate_extraction(extraction, pdf))["hazard_statements[0]"]

    assert check.status is Status.NEEDS_REVIEW
    assert "H plus 3 digits" in " ".join(check.reasons)


def test_impossible_date_and_bad_signal_word_are_flagged(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.revision_date = Sourced(value="2025-02-30", page=1, quote="Revision date: 01.03.2025")
    extraction.signal_word = Sourced(value="Signal", page=2, quote="Signal word: Warning")

    checks = _by_name(validate_extraction(extraction, document))

    assert checks["revision_date"].checks["format"] is False
    assert checks["signal_word"].checks["format"] is False


def test_empty_hazard_section_always_goes_to_review(document: ParsedDocument) -> None:
    extraction = _good(document)
    extraction.hazard_statements = []

    check = _by_name(validate_extraction(extraction, document))["hazard_statements"]

    assert check.status is Status.NEEDS_REVIEW
    assert "check section 2" in check.reasons[0]


def test_review_summary_counts_and_rate(document: ParsedDocument) -> None:
    summary = summarise_checks(validate_extraction(_good(document), document))

    assert summary.missing == 1 and summary.needs_review == 0
    assert summary.review_rate == 0.0


def test_flags_old_sds_missing_cas_and_sections() -> None:
    flags = product_flags(
        revision_date="2021-01-02",
        cas_numbers=["1310-73-2", None],
        missing_sections=[8, 9],
        max_age_years=3,
        today=date(2026, 10, 9),
    )

    assert [flag.kind for flag in flags] == ["old_sds", "missing_cas", "missing_sections"]
    assert "5.8 years old" in flags[0].detail


def test_recent_complete_sds_has_no_flags() -> None:
    flags = product_flags(
        revision_date="2025-03-01",
        cas_numbers=["7732-18-5"],
        missing_sections=[],
        max_age_years=3,
        today=date(2026, 10, 9),
    )

    assert flags == []


def test_missing_revision_date_is_flagged() -> None:
    flags = product_flags(
        revision_date=None, cas_numbers=[], missing_sections=[], max_age_years=3, today=date.today()
    )

    assert flags[0].detail.startswith("No revision date")
