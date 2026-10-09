"""Check every extracted value with plain code and decide what a person must review.

For each value we run the checks that apply:

* grounded      the quote is really in the PDF text (otherwise the value is removed)
* right_page    the quote is on the page the model named
* right_section the quote is in the SDS section where this field belongs
* matches_quote the value can be seen inside its own quote
* format        CAS check digit, H code, pictogram, signal word, ISO date

A value passes only if every check passes. Anything else goes to human review.
Confidence is the share of checks that passed, so it comes from evidence, not
from the model's own opinion of itself.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from chemready.pdf.parse import ParsedDocument
from chemready.pdf.sections import Section, split_sections
from chemready.schema import SdsExtraction
from chemready.validation.grounding import appears_in, value_in_text
from chemready.validation.rules import (
    cas_check_digit_ok,
    h_code_ok,
    iso_date_ok,
    pictogram_ok,
    signal_word_ok,
)


class Status(StrEnum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"


# Which SDS sections each field may come from.
FIELD_SECTIONS: dict[str, tuple[int, ...]] = {
    "product_name": (1,),
    "supplier": (1,),
    "revision_date": (1, 16),
    "signal_word": (2,),
    "hazard_statement": (2,),
    "pictogram": (2,),
    "ingredient_cas": (3,),
    "storage": (7,),
    "ppe": (8,),
}

LABELS = {
    "product_name": "Product name",
    "supplier": "Supplier",
    "revision_date": "Revision date",
    "signal_word": "Signal word",
    "storage": "Storage",
    "ppe": "PPE",
}


@dataclass
class FieldCheck:
    """One value after validation. This is what the field_value table stores."""

    field_name: str
    label: str
    value: str | None
    page: int | None
    quote: str | None
    status: Status
    confidence: float
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Checker:
    document: ParsedDocument
    sections: dict[int, Section]

    def check(
        self,
        *,
        field_name: str,
        kind: str,
        label: str,
        value: str | None,
        page: int | None,
        quote: str | None,
        format_ok: bool | None = None,
        format_reason: str = "",
        is_date: bool = False,
        missing_reason: str = "Not found in this SDS.",
    ) -> FieldCheck:
        if value is None:
            return FieldCheck(
                field_name, label, None, page, quote, Status.MISSING, 0.0, reasons=[missing_reason]
            )

        checks: dict[str, bool] = {"grounded": appears_in(quote, self.document.full_text)}
        if not checks["grounded"]:
            reason = "Quote not found in the PDF. The value was removed."
            if quote is None:
                reason = "No quote was given. The value was removed."
            return FieldCheck(
                field_name, label, None, page, quote, Status.NEEDS_REVIEW, 0.0, checks, [reason]
            )

        reasons: list[str] = []
        on_page = page is not None and 1 <= page <= self.document.page_count
        checks["right_page"] = (
            on_page and page is not None and appears_in(quote, self.document.page(page).text)
        )
        if not checks["right_page"]:
            found_on = [p.number for p in self.document.pages if appears_in(quote, p.text)]
            where = f" It is on page {found_on[0]}." if found_on else ""
            reasons.append(f"The quote is not on page {page}.{where}")

        allowed = FIELD_SECTIONS[kind]
        known = [self.sections[n] for n in allowed if n in self.sections]
        if known:
            checks["right_section"] = any(appears_in(quote, section.text) for section in known)
            if not checks["right_section"]:
                names = " or ".join(str(n) for n in allowed)
                reasons.append(f"The quote is not in section {names}, where this value belongs.")

        checks["matches_quote"] = value_in_text(value, quote or "", is_date=is_date)
        if not checks["matches_quote"]:
            reasons.append("The value does not match its quote.")

        if format_ok is not None:
            checks["format"] = format_ok
            if not format_ok:
                reasons.append(format_reason)

        confidence = round(sum(checks.values()) / len(checks), 2)
        status = Status.PASSED if all(checks.values()) else Status.NEEDS_REVIEW
        return FieldCheck(field_name, label, value, page, quote, status, confidence, checks, reasons)


def validate_extraction(extraction: SdsExtraction, document: ParsedDocument) -> list[FieldCheck]:
    """Validate every value. Values that fail grounding are returned with value None."""
    sections = split_sections(document)
    checker = _Checker(document, sections)
    results: list[FieldCheck] = []

    for name in ("product_name", "supplier", "storage", "ppe"):
        item = getattr(extraction, name)
        results.append(
            checker.check(
                field_name=name,
                kind=name,
                label=LABELS[name],
                value=item.value,
                page=item.page,
                quote=item.quote,
            )
        )

    rev = extraction.revision_date
    results.append(
        checker.check(
            field_name="revision_date",
            kind="revision_date",
            label="Revision date",
            value=rev.value,
            page=rev.page,
            quote=rev.quote,
            is_date=True,
            format_ok=None if rev.value is None else iso_date_ok(rev.value),
            format_reason="The date is not a real date in YYYY-MM-DD form.",
        )
    )

    signal = extraction.signal_word
    results.append(
        checker.check(
            field_name="signal_word",
            kind="signal_word",
            label="Signal word",
            value=signal.value,
            page=signal.page,
            quote=signal.quote,
            format_ok=None if signal.value is None else signal_word_ok(signal.value),
            format_reason="The signal word must be Danger or Warning.",
            missing_reason="No signal word found. This can be right for unclassified products.",
        )
    )

    for index, hazard in enumerate(extraction.hazard_statements):
        results.append(
            checker.check(
                field_name=f"hazard_statements[{index}]",
                kind="hazard_statement",
                label="H code",
                value=hazard.code,
                page=hazard.page,
                quote=hazard.quote,
                format_ok=h_code_ok(hazard.code),
                format_reason="This is not a valid H code format (H plus 3 digits).",
            )
        )

    for index, picto in enumerate(extraction.pictograms):
        results.append(
            checker.check(
                field_name=f"pictograms[{index}]",
                kind="pictogram",
                label="Pictogram",
                value=picto.code,
                page=picto.page,
                quote=picto.quote,
                format_ok=pictogram_ok(picto.code),
                format_reason="Pictograms must be GHS01 to GHS09.",
            )
        )

    for index, ingredient in enumerate(extraction.ingredients):
        cas = ingredient.cas_number
        results.append(
            checker.check(
                field_name=f"ingredients[{index}].cas_number",
                kind="ingredient_cas",
                label=f"CAS · {ingredient.name or f'ingredient {index + 1}'}",
                value=cas,
                page=ingredient.page,
                quote=ingredient.quote,
                format_ok=None if cas is None else cas_check_digit_ok(cas),
                format_reason="CAS check digit is wrong. Check the number in the SDS.",
                missing_reason="No CAS number given for this ingredient.",
            )
        )

    # Guardrail from the PRD: an empty hazard section always goes to a person.
    if not extraction.hazard_statements:
        results.append(
            FieldCheck(
                field_name="hazard_statements",
                label="H codes",
                value=None,
                page=sections[2].start_page if 2 in sections else None,
                quote=None,
                status=Status.NEEDS_REVIEW,
                confidence=0.0,
                reasons=["No hazard statements found. Please check section 2."],
            )
        )
    return results


@dataclass(frozen=True)
class ReviewSummary:
    passed: int
    needs_review: int
    missing: int

    @property
    def review_rate(self) -> float:
        """Share of fields sent to a person. PRD target 10% to 25%."""
        total = self.passed + self.needs_review + self.missing
        return self.needs_review / total if total else 0.0


def summarise_checks(checks: list[FieldCheck]) -> ReviewSummary:
    return ReviewSummary(
        passed=sum(c.status is Status.PASSED for c in checks),
        needs_review=sum(c.status is Status.NEEDS_REVIEW for c in checks),
        missing=sum(c.status is Status.MISSING for c in checks),
    )
