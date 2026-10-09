"""Score predictions against the gold set.

Critical fields (PRD): product name, supplier, revision date, H codes, pictograms
and CAS numbers. Each scalar field is one unit. Each code in a list is one unit,
and every extra code the model adds that is not in the gold set counts as a wrong
unit too, so inventing codes lowers accuracy.
"""

import re
import statistics
import unicodedata
from dataclasses import dataclass, field

from chemready.evals.formats import GoldRecord, Prediction
from chemready.schema import SdsExtraction, Sourced
from chemready.validation.grounding import appears_in, value_in_text

SCALAR_FIELDS = ("product_name", "supplier", "revision_date")
_TRAILING_PUNCTUATION = re.compile(r"[\s.,;:]+$")


def normalise_name(value: str | None) -> str | None:
    """Compare names ignoring case, spacing and trailing punctuation."""
    if value is None:
        return None
    value = unicodedata.normalize("NFKC", value)
    value = " ".join(value.split()).casefold()
    return _TRAILING_PUNCTUATION.sub("", value) or None


def normalise_code(value: str | None) -> str | None:
    """Codes are compared exactly, after removing spaces and upper-casing."""
    if value is None:
        return None
    return "".join(value.split()).upper() or None


def hazard_codes(extraction: SdsExtraction) -> set[str]:
    return {code for item in extraction.hazard_statements if (code := normalise_code(item.code))}


def pictogram_codes(extraction: SdsExtraction) -> set[str]:
    return {code for item in extraction.pictograms if (code := normalise_code(item.code))}


def cas_numbers(extraction: SdsExtraction) -> set[str]:
    return {cas for item in extraction.ingredients if (cas := normalise_code(item.cas_number))}


@dataclass
class DocumentScore:
    sds_id: str
    correct_units: int = 0
    total_units: int = 0
    gold_codes: int = 0
    found_codes: int = 0
    predicted_values: int = 0
    hallucinated_values: int = 0
    errors: list[str] = field(default_factory=list)
    failed: bool = False


def _scalar_correct(field_name: str, gold: Sourced, predicted: Sourced) -> bool:
    if field_name == "revision_date":
        return (gold.value or None) == (predicted.value or None)
    return normalise_name(gold.value) == normalise_name(predicted.value)


def _is_hallucinated(value: str, quote: str | None, text: str, *, is_date: bool = False) -> bool:
    """Invented = neither the quote nor the value can be found in the PDF text."""
    return not appears_in(quote, text) and not value_in_text(value, text, is_date=is_date)


def score_document(gold: GoldRecord, prediction: Prediction | None, pdf_text: str) -> DocumentScore:
    """Score one SDS. pdf_text is the full text of the PDF, used to detect invented values."""
    score = DocumentScore(sds_id=gold.sds_id)
    expected = gold.expected
    code_sets = (
        ("H codes", hazard_codes(expected)),
        ("pictograms", pictogram_codes(expected)),
        ("CAS numbers", cas_numbers(expected)),
    )

    if prediction is None or prediction.extraction is None:
        score.failed = True
        score.total_units = len(SCALAR_FIELDS) + sum(len(codes) for _, codes in code_sets)
        score.gold_codes = len(hazard_codes(expected)) + len(cas_numbers(expected))
        score.errors.append(prediction.error if prediction and prediction.error else "no prediction")
        return score

    predicted = prediction.extraction
    for name in SCALAR_FIELDS:
        gold_field, pred_field = getattr(expected, name), getattr(predicted, name)
        score.total_units += 1
        if _scalar_correct(name, gold_field, pred_field):
            score.correct_units += 1
        else:
            score.errors.append(f"{name}: expected {gold_field.value!r}, got {pred_field.value!r}")
        if pred_field.value is not None:
            score.predicted_values += 1
            if _is_hallucinated(
                pred_field.value, pred_field.quote, pdf_text, is_date=name == "revision_date"
            ):
                score.hallucinated_values += 1
                score.errors.append(f"{name}: {pred_field.value!r} is not in the PDF text")

    predicted_sets = {
        "H codes": (
            hazard_codes(predicted),
            {normalise_code(h.code): h.quote for h in predicted.hazard_statements},
        ),
        "pictograms": (
            pictogram_codes(predicted),
            {normalise_code(p.code): p.quote for p in predicted.pictograms},
        ),
        "CAS numbers": (
            cas_numbers(predicted),
            {normalise_code(i.cas_number): i.quote for i in predicted.ingredients},
        ),
    }
    for label, gold_codes in code_sets:
        got, quotes = predicted_sets[label]
        score.correct_units += len(gold_codes & got)
        score.total_units += len(gold_codes | got)
        if label != "pictograms":
            score.gold_codes += len(gold_codes)
            score.found_codes += len(gold_codes & got)
        for missing in sorted(gold_codes - got):
            score.errors.append(f"{label}: missed {missing}")
        for extra in sorted(got - gold_codes):
            score.errors.append(f"{label}: extra {extra}")
        for code in got:
            score.predicted_values += 1
            if _is_hallucinated(code, quotes.get(code), pdf_text):
                score.hallucinated_values += 1
                score.errors.append(f"{label}: {code} is not in the PDF text")
    return score


@dataclass(frozen=True)
class EvalSummary:
    documents: int
    failed_documents: int
    field_accuracy: float
    code_recall: float
    hallucination_rate: float
    mean_latency_ms: float
    p95_latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


def _ratio(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def summarise(
    scores: list[DocumentScore],
    predictions: list[Prediction],
    price_per_million: tuple[float, float] | None,
) -> EvalSummary:
    """Combine document scores. price_per_million is (input, output) in USD, or None if unknown."""
    latencies = sorted(p.latency_ms for p in predictions)
    p95 = latencies[min(len(latencies) - 1, round(0.95 * (len(latencies) - 1)))] if latencies else 0.0
    input_tokens = sum(p.input_tokens for p in predictions)
    output_tokens = sum(p.output_tokens for p in predictions)
    cost = None
    if price_per_million is not None:
        cost = (input_tokens * price_per_million[0] + output_tokens * price_per_million[1]) / 1_000_000
    return EvalSummary(
        documents=len(scores),
        failed_documents=sum(score.failed for score in scores),
        field_accuracy=_ratio(sum(s.correct_units for s in scores), sum(s.total_units for s in scores)),
        code_recall=_ratio(sum(s.found_codes for s in scores), sum(s.gold_codes for s in scores)),
        hallucination_rate=_ratio(
            sum(s.hallucinated_values for s in scores), sum(s.predicted_values for s in scores)
        ),
        mean_latency_ms=statistics.fmean(latencies) if latencies else 0.0,
        p95_latency_ms=p95,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
    )
