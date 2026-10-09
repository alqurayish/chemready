"""The data contract for one SDS: what the AI fills in and what the gold set holds.

Every value carries the page it came from and the exact quote, so plain code can
check it against the PDF text and a person can see the source. A value of None
means "not found in this SDS". The AI must never guess a value to fill a gap.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sourced(_Strict):
    """One value, with the page it is on and the exact words that support it."""

    value: str | None = Field(default=None, description="The value, or null if the SDS does not contain it.")
    page: int | None = Field(default=None, ge=1, description="1-based page number where the quote appears.")
    quote: str | None = Field(
        default=None, description="Exact text copied from the SDS that shows the value."
    )


class HazardStatement(_Strict):
    code: str = Field(description="Hazard statement code exactly as printed, for example H315.")
    statement: str | None = Field(default=None, description="The sentence after the code.")
    page: int | None = Field(default=None, ge=1)
    quote: str | None = None


class Pictogram(_Strict):
    code: str = Field(description="GHS pictogram code, GHS01 to GHS09.")
    page: int | None = Field(default=None, ge=1)
    quote: str | None = None


class Ingredient(_Strict):
    name: str | None = Field(default=None, description="Substance name from section 3.")
    cas_number: str | None = Field(default=None, description="CAS number exactly as printed, or null.")
    percent: str | None = Field(default=None, description="Concentration or range as printed, e.g. 10-20%.")
    page: int | None = Field(default=None, ge=1)
    quote: str | None = None


class SdsExtraction(_Strict):
    """The key fields ChemReady needs from one SDS (PRD requirement R2)."""

    product_name: Sourced = Field(default_factory=Sourced)
    supplier: Sourced = Field(default_factory=Sourced)
    revision_date: Sourced = Field(
        default_factory=Sourced, description="Revision date as YYYY-MM-DD. Not the print date."
    )
    signal_word: Sourced = Field(default_factory=Sourced, description="Danger or Warning, or null.")
    hazard_statements: list[HazardStatement] = Field(default_factory=list)
    pictograms: list[Pictogram] = Field(default_factory=list)
    ingredients: list[Ingredient] = Field(default_factory=list)
    ppe: Sourced = Field(default_factory=Sourced, description="Personal protective equipment, section 8.")
    storage: Sourced = Field(default_factory=Sourced, description="Storage conditions, section 7.")
