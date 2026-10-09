"""Check gold files for mistakes before using them.

    uv run python -m chemready.evals.check_gold evals/gold evals/pdfs

Checks the JSON format, code formats, CAS check digits, page numbers and that
every quote really appears on its page. Problems are printed; nothing is changed.
"""

import sys
from pathlib import Path

from pydantic import ValidationError

from chemready.evals.formats import GoldRecord
from chemready.pdf.parse import PdfError, parse_pdf
from chemready.validation.grounding import appears_in
from chemready.validation.rules import (
    cas_check_digit_ok,
    h_code_ok,
    iso_date_ok,
    pictogram_ok,
    signal_word_ok,
)


def check_record(record: GoldRecord, pdf_folder: Path) -> list[str]:
    problems: list[str] = []
    expected = record.expected
    pdf_path = pdf_folder / record.file
    pages: list[str] = []
    if not pdf_path.exists():
        problems.append(f"PDF not found: {pdf_path}")
    else:
        try:
            pages = [page.text for page in parse_pdf(pdf_path).pages]
        except PdfError as error:
            problems.append(f"PDF cannot be read: {error}")

    def check_quote(label: str, page: int | None, quote: str | None) -> None:
        if quote is None or not pages:
            return
        if page is None:
            problems.append(f"{label}: has a quote but no page")
        elif not 1 <= page <= len(pages):
            problems.append(f"{label}: page {page} does not exist (PDF has {len(pages)} pages)")
        elif not record.is_scanned and not appears_in(quote, pages[page - 1]):
            problems.append(f"{label}: quote not found on page {page}: {quote!r}")

    for name in ("product_name", "supplier", "revision_date", "signal_word", "ppe", "storage"):
        field = getattr(expected, name)
        check_quote(name, field.page, field.quote)
    if expected.revision_date.value and not iso_date_ok(expected.revision_date.value):
        problems.append(f"revision_date: {expected.revision_date.value!r} is not YYYY-MM-DD")
    if expected.signal_word.value and not signal_word_ok(expected.signal_word.value):
        problems.append(f"signal_word: {expected.signal_word.value!r} must be Danger or Warning")
    for item in expected.hazard_statements:
        if not h_code_ok(item.code):
            problems.append(f"hazard code {item.code!r} is not H plus 3 digits")
        check_quote(f"hazard {item.code}", item.page, item.quote)
    for picto in expected.pictograms:
        if not pictogram_ok(picto.code):
            problems.append(f"pictogram {picto.code!r} is not GHS01 to GHS09")
    for ingredient in expected.ingredients:
        if ingredient.cas_number and not cas_check_digit_ok(ingredient.cas_number):
            problems.append(
                f"CAS {ingredient.cas_number!r} fails the check digit (if printed so, explain in notes)"
            )
        check_quote(f"ingredient {ingredient.name}", ingredient.page, ingredient.quote)
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage: python -m chemready.evals.check_gold <gold folder> <pdf folder>")
        return 2
    gold_folder, pdf_folder = Path(args[0]), Path(args[1])
    total_problems = 0
    files = sorted(gold_folder.glob("*.json"))
    for path in files:
        try:
            record = GoldRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            print(f"{path.name}: invalid format\n{error}")
            total_problems += 1
            continue
        problems = check_record(record, pdf_folder)
        total_problems += len(problems)
        for problem in problems:
            print(f"{path.name}: {problem}")
    print(f"Checked {len(files)} gold files: {total_problems} problem(s).")
    return 1 if total_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
