"""Tests for the gold format, the metrics and run_evals.py."""

from pathlib import Path

import pytest

from chemready.demo.synthetic_set import build
from chemready.evals.formats import GoldRecord, Prediction, load_gold, write_json
from chemready.evals.metrics import normalise_name, score_document, summarise
from chemready.evals.run_evals import main
from chemready.pdf.parse import parse_pdf
from chemready.schema import HazardStatement, Ingredient, SdsExtraction, Sourced


@pytest.fixture
def synthetic(tmp_path: Path) -> tuple[Path, list[GoldRecord]]:
    return tmp_path, build(tmp_path)


def _perfect(record: GoldRecord) -> Prediction:
    return Prediction(
        sds_id=record.sds_id,
        provider="test",
        model="perfect",
        latency_ms=1000,
        input_tokens=100,
        output_tokens=50,
        extraction=record.expected,
    )


def _text(folder: Path, record: GoldRecord) -> str:
    return parse_pdf(folder / "pdfs" / record.file).full_text


def test_gold_files_round_trip(synthetic: tuple[Path, list[GoldRecord]]) -> None:
    folder, records = synthetic

    assert [r.sds_id for r in load_gold(folder / "gold")] == [r.sds_id for r in records]
    assert all(record.synthetic for record in records)


def test_perfect_prediction_scores_100_percent_and_no_hallucinations(
    synthetic: tuple[Path, list[GoldRecord]],
) -> None:
    folder, records = synthetic
    scores = [score_document(r, _perfect(r), _text(folder, r)) for r in records]

    summary = summarise(scores, [_perfect(r) for r in records], price_per_million=(0.0, 0.0))

    assert summary.field_accuracy == 1.0
    assert summary.code_recall == 1.0
    assert summary.hallucination_rate == 0.0
    assert summary.cost_usd == 0.0


def test_wrong_and_invented_values_are_counted(synthetic: tuple[Path, list[GoldRecord]]) -> None:
    folder, records = synthetic
    record = records[0]  # Demowet NF: H315, H319, GHS07, CAS 67-63-0 and 7732-18-5
    extraction = record.expected.model_copy(deep=True)
    extraction.revision_date = Sourced(value="2025-04-12", page=1, quote="Revision date: 12.04.2025")
    extraction.hazard_statements = [
        HazardStatement(code="H315", quote="H315 Causes skin irritation."),
        HazardStatement(code="H360", quote="H360 May damage fertility."),
    ]
    extraction.ingredients = [Ingredient(name="Water", cas_number="7732-18-5")]
    prediction = Prediction(
        sds_id=record.sds_id, provider="t", model="t", latency_ms=1, extraction=extraction
    )

    score = score_document(record, prediction, _text(folder, record))

    # Units: 3 scalars + H codes {H315, H319, H360} + {GHS07} + CAS {67-63-0, 7732-18-5} = 9
    assert score.total_units == 9
    # Correct: product, supplier, H315, GHS07, 7732-18-5 = 5
    assert score.correct_units == 5
    assert score.gold_codes == 4 and score.found_codes == 2
    # Invented: the 12.04.2025 date and H360 are nowhere in the PDF
    assert score.hallucinated_values == 2
    assert any("H360 is not in the PDF text" in error for error in score.errors)


def test_missing_prediction_counts_all_units_as_wrong(synthetic: tuple[Path, list[GoldRecord]]) -> None:
    folder, records = synthetic

    score = score_document(records[0], None, _text(folder, records[0]))

    # 3 scalars + 2 H codes + 1 pictogram + 2 CAS numbers = 8 units
    assert score.failed and score.correct_units == 0 and score.total_units == 8


def test_correct_not_found_counts_as_correct(synthetic: tuple[Path, list[GoldRecord]]) -> None:
    folder, records = synthetic
    record = records[0]
    record.expected.revision_date = Sourced(value=None)
    prediction = _perfect(record)
    assert prediction.extraction is not None
    prediction.extraction.revision_date = Sourced(value=None)

    assert score_document(record, prediction, _text(folder, record)).correct_units == 8


@pytest.mark.parametrize(
    ("raw", "clean"), [("  Demowet  NF. ", "demowet nf"), (None, None), ("ACME Ltd", "acme ltd")]
)
def test_names_are_normalised(raw: str | None, clean: str | None) -> None:
    assert normalise_name(raw) == clean


def test_cost_is_unknown_without_prices() -> None:
    assert summarise([], [], price_per_million=None).cost_usd is None


def test_run_evals_cli_prints_table_logs_and_gates(
    synthetic: tuple[Path, list[GoldRecord]], capsys: pytest.CaptureFixture[str]
) -> None:
    folder, records = synthetic
    for record in records:
        write_json(_perfect(record), folder / "runs" / "perfect" / f"{record.sds_id}.json")
    log = folder / "results.jsonl"

    code = main([
        "--gold", str(folder / "gold"), "--pdfs", str(folder / "pdfs"),
        "--predictions", str(folder / "runs" / "perfect"),
        "--price-in", "0", "--price-out", "0", "--label", "perfect", "--log", str(log), "--gate",
    ])  # fmt: skip

    output = capsys.readouterr().out
    assert code == 0
    assert "| Critical field accuracy | 100.0% | >= 95% | yes |" in output
    assert '"label": "perfect"' in log.read_text()


def test_gate_fails_when_predictions_are_missing(
    synthetic: tuple[Path, list[GoldRecord]], capsys: pytest.CaptureFixture[str]
) -> None:
    folder, _ = synthetic
    (folder / "runs" / "empty").mkdir(parents=True)

    code = main([
        "--gold", str(folder / "gold"), "--pdfs", str(folder / "pdfs"),
        "--predictions", str(folder / "runs" / "empty"), "--gate", "--details",
    ])  # fmt: skip

    assert code == 1
    assert "Eval gate failed" in capsys.readouterr().out


def test_empty_extraction_is_valid_and_means_nothing_found() -> None:
    assert SdsExtraction().product_name.value is None


def test_check_gold_passes_on_clean_files(synthetic: tuple[Path, list[GoldRecord]]) -> None:
    from chemready.evals.check_gold import main as check_main

    folder, _ = synthetic

    assert check_main([str(folder / "gold"), str(folder / "pdfs")]) == 0


def test_check_gold_reports_typos(
    synthetic: tuple[Path, list[GoldRecord]], capsys: pytest.CaptureFixture[str]
) -> None:
    from chemready.evals.check_gold import main as check_main

    folder, records = synthetic
    record = records[0]
    record.expected.product_name = Sourced(value="Demowet NF", page=1, quote="Product name: Demowet MF")
    record.expected.ingredients.append(Ingredient(name="Typo", cas_number="7732-18-6"))
    record.expected.hazard_statements.append(HazardStatement(code="H3l9"))
    write_json(record, folder / "gold" / f"{record.sds_id}.json")

    assert check_main([str(folder / "gold"), str(folder / "pdfs")]) == 1
    output = capsys.readouterr().out
    assert "quote not found on page 1" in output
    assert "fails the check digit" in output
    assert "is not H plus 3 digits" in output


def test_check_gold_rejects_the_unfilled_template(tmp_path: Path) -> None:
    from chemready.evals.check_gold import main as check_main

    (tmp_path / "gold").mkdir()
    template = Path(__file__).parents[1] / "docs" / "data" / "gold-template.json"
    (tmp_path / "gold" / "sds-001.json").write_text(template.read_text())

    assert check_main([str(tmp_path / "gold"), str(tmp_path)]) == 1
