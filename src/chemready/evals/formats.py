"""File formats for the gold set and for model predictions."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from chemready.schema import SdsExtraction


class SourceInfo(BaseModel):
    """Where a public SDS came from. Needed to show it was collected legally."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    publisher: str | None = None
    downloaded_at: str | None = Field(default=None, description="YYYY-MM-DD")
    licence_note: str | None = None


class GoldRecord(BaseModel):
    """One hand-labelled SDS: the correct answers a person checked against the PDF."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    sds_id: str
    file: str = Field(description="PDF file name inside the PDF folder.")
    synthetic: bool = Field(default=False, description="True only for fictional test files.")
    source: SourceInfo = Field(default_factory=SourceInfo)
    is_scanned: bool = False
    language: str = "en"
    labelled_by: str
    labelled_at: str
    notes: str = ""
    expected: SdsExtraction


class Prediction(BaseModel):
    """What one extraction run produced for one SDS, with timing and token counts."""

    model_config = ConfigDict(extra="forbid")

    sds_id: str
    provider: str
    model: str
    latency_ms: float = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    extraction: SdsExtraction | None = None
    error: str | None = None


def load_gold(folder: Path) -> list[GoldRecord]:
    """Load every *.json file in a folder as a gold record, sorted by id."""
    records = [
        GoldRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in folder.glob("*.json")
    ]
    return sorted(records, key=lambda record: record.sds_id)


def load_predictions(folder: Path) -> dict[str, Prediction]:
    """Load every *.json prediction in a folder, keyed by SDS id."""
    predictions = [
        Prediction.model_validate_json(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")
    ]
    return {prediction.sds_id: prediction for prediction in predictions}


def write_json(model: BaseModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
