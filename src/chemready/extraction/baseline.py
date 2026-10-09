"""An offline baseline with no AI: simple patterns that read "Label: value" lines.

It is here for two reasons: the demo can run without any AI account, and the evals
need a baseline to beat. It only understands tidy layouts, so expect low accuracy
on real SDS files. That is the point: the evals will show how much the AI adds.
"""

import re
import time

from pydantic import BaseModel

from chemready.extraction.llm import LlmError, LlmResult, LlmUsage
from chemready.schema import HazardStatement, Ingredient, Pictogram, SdsExtraction, Sourced

_PAGE = re.compile(r"^=== page (\d+) ===$")
_H_LINE = re.compile(r"^(H\d{3})\s+(.+)$")
_PICTO = re.compile(r"\b(GHS0[1-9])\b")
_CAS = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
_DATE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
_LABELS = {
    "product_name": ("product name", "trade name", "product identifier"),
    "supplier": ("supplier", "manufacturer", "company"),
    "revision_date": ("revision date", "date of revision", "revised"),
    "signal_word": ("signal word",),
    "ppe": ("ppe", "personal protective equipment"),
}


def _lines(text: str) -> list[tuple[int, str]]:
    page = 1
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        match = _PAGE.match(line)
        if match:
            page = int(match.group(1))
        elif line and not line.startswith("<"):
            out.append((page, line))
    return out


def _labelled(lines: list[tuple[int, str]], labels: tuple[str, ...]) -> Sourced:
    for page, line in lines:
        head, sep, value = line.partition(":")
        if sep and head.strip().lower() in labels and value.strip():
            return Sourced(value=value.strip(), page=page, quote=line)
    return Sourced()


def extract_with_rules(text: str) -> SdsExtraction:
    lines = _lines(text)
    result = SdsExtraction(
        product_name=_labelled(lines, _LABELS["product_name"]),
        supplier=_labelled(lines, _LABELS["supplier"]),
        revision_date=_labelled(lines, _LABELS["revision_date"]),
        signal_word=_labelled(lines, _LABELS["signal_word"]),
        ppe=_labelled(lines, _LABELS["ppe"]),
    )

    raw_date = result.revision_date.value
    match = _DATE.search(raw_date) if raw_date else None
    result.revision_date.value = (
        f"{match.group(3)}-{int(match.group(2)):02d}-{int(match.group(1)):02d}" if match else None
    )
    if result.signal_word.value not in ("Danger", "Warning"):
        result.signal_word = Sourced()

    in_section: int | None = None
    for page, line in lines:
        heading = re.match(r"^(?:section\s*)?(\d{1,2})\s*[:.]", line, re.IGNORECASE)
        if heading:
            in_section = int(heading.group(1))
            continue
        if in_section == 2 and (h := _H_LINE.match(line)):
            result.hazard_statements.append(
                HazardStatement(code=h.group(1), statement=h.group(2), page=page, quote=line)
            )
        if in_section == 2:
            result.pictograms += [
                Pictogram(code=code, page=page, quote=line) for code in _PICTO.findall(line)
            ]
        if in_section == 3:
            cas = _CAS.search(line)
            name = re.split(r"\s{2,}|\s+CAS", line)[0].strip()
            result.ingredients.append(
                Ingredient(name=name or None, cas_number=cas.group(1) if cas else None, page=page, quote=line)
            )
        if in_section == 7 and result.storage.value is None:
            result.storage = Sourced(value=line, page=page, quote=line)
    return result


class RulesClient:
    """Fits the LlmClient interface, but uses patterns instead of a model."""

    provider = "rules"
    model = "rules-baseline-v1"
    allows_private_data = True  # nothing leaves the machine

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]:
        if schema is not SdsExtraction:
            raise LlmError("The rules baseline only fills SdsExtraction.")
        start = time.perf_counter()
        output = extract_with_rules(text)
        usage = LlmUsage(self.provider, self.model, 0, 0, (time.perf_counter() - start) * 1000)
        return LlmResult(output=schema.model_validate(output.model_dump()), usage=usage)
