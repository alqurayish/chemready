"""Action flags for one approved product (PRD requirement R6)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ActionFlag:
    kind: str  # "old_sds" | "missing_cas" | "missing_sections" | "unreadable"
    label: str
    detail: str


def _years_between(start: date, end: date) -> float:
    return (end - start).days / 365.25


def product_flags(
    *,
    revision_date: str | None,
    cas_numbers: list[str | None],
    missing_sections: list[int],
    max_age_years: int,
    today: date,
) -> list[ActionFlag]:
    flags = []
    if revision_date:
        age = _years_between(date.fromisoformat(revision_date), today)
        if age > max_age_years:
            flags.append(
                ActionFlag("old_sds", "SDS too old", f"Revision date {revision_date}, {age:.1f} years old")
            )
    else:
        flags.append(ActionFlag("old_sds", "SDS too old", "No revision date, so the age cannot be checked"))
    missing = sum(cas is None for cas in cas_numbers)
    if missing:
        flags.append(
            ActionFlag(
                "missing_cas",
                "Missing CAS",
                f"{missing} of {len(cas_numbers)} ingredients have no CAS number",
            )
        )
    if missing_sections:
        listed = ", ".join(str(n) for n in missing_sections)
        flags.append(ActionFlag("missing_sections", "Missing sections", f"Sections {listed} not found"))
    return flags
