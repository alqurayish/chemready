"""Grounding: does a value really appear in the PDF text?

PDF text extraction changes spacing, line breaks and dashes, so both sides are
normalised before comparing. A quote that is not in the text after normalising
is treated as invented.
"""

import re
import unicodedata
from datetime import date

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")
# Curly quotes become straight quotes.
_QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'}
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lower case, unify dashes and quotes, collapse all whitespace to single spaces."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES).translate(_QUOTES)
    return _SPACES.sub(" ", text).strip().casefold()


def appears_in(needle: str | None, haystack: str) -> bool:
    """True when the needle appears in the haystack after normalising both."""
    if not needle or not needle.strip():
        return False
    return normalise(needle) in normalise(haystack)


def date_variants(iso_date: str) -> list[str]:
    """The common ways an SDS prints a date, so an ISO value can be found in the text."""
    try:
        day = date.fromisoformat(iso_date)
    except ValueError:
        return [iso_date]
    d, m, y = day.day, day.month, day.year
    months = day.strftime("%B"), day.strftime("%b")
    variants = {
        iso_date,
        f"{d:02d}.{m:02d}.{y}",
        f"{d}.{m}.{y}",
        f"{d:02d}/{m:02d}/{y}",
        f"{m:02d}/{d:02d}/{y}",
        f"{d:02d}-{m:02d}-{y}",
        f"{y}/{m:02d}/{d:02d}",
    }
    for month in months:
        variants |= {f"{d} {month} {y}", f"{d:02d} {month} {y}", f"{month} {d}, {y}", f"{d}-{month}-{y}"}
    return sorted(variants)


def value_in_text(value: str | None, text: str, *, is_date: bool = False) -> bool:
    """True when the value itself (or, for dates, any common print format) appears in the text."""
    if value is None:
        return False
    candidates = date_variants(value) if is_date else [value]
    return any(appears_in(candidate, text) for candidate in candidates)
