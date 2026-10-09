"""Run the evals and print a results table.

Score saved predictions:
    uv run python -m chemready.evals.run_evals --gold evals/gold --pdfs evals/pdfs --predictions evals/runs/v1

Prices are optional. Without them cost is shown as "unknown"; on the free tier pass 0 and 0.
"""

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from chemready.evals.formats import load_gold, load_predictions
from chemready.evals.metrics import DocumentScore, EvalSummary, score_document, summarise
from chemready.pdf.parse import ParsedDocument, PdfError, parse_pdf

# Targets from the PRD. A run that misses any of them is reported as failing.
TARGETS = {"field_accuracy": 0.95, "code_recall": 0.95, "hallucination_rate": 0.0, "calibration": 0.98}


def load_pdf(pdf_folder: Path, file_name: str) -> ParsedDocument | None:
    path = pdf_folder / file_name
    if not path.exists():
        raise FileNotFoundError(f"PDF for gold record not found: {path}")
    try:
        return parse_pdf(path)
    except PdfError:
        return None


def evaluate(
    gold_folder: Path, pdf_folder: Path, predictions_folder: Path, price: tuple[float, float] | None
) -> tuple[EvalSummary, list[DocumentScore]]:
    gold = load_gold(gold_folder)
    if not gold:
        raise SystemExit(f"No gold records found in {gold_folder}")
    predictions = load_predictions(predictions_folder)
    scores = []
    for record in gold:
        document = load_pdf(pdf_folder, record.file)
        text = document.full_text if document else ""
        scores.append(score_document(record, predictions.get(record.sds_id), text, document))
    used = [predictions[record.sds_id] for record in gold if record.sds_id in predictions]
    return summarise(scores, used, price), scores


def meets_targets(summary: EvalSummary) -> dict[str, bool]:
    return {
        "field_accuracy": summary.field_accuracy >= TARGETS["field_accuracy"],
        "code_recall": summary.code_recall >= TARGETS["code_recall"],
        "hallucination_rate": summary.hallucination_rate <= TARGETS["hallucination_rate"],
        "calibration": summary.calibration is None or summary.calibration >= TARGETS["calibration"],
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def format_table(summary: EvalSummary) -> str:
    passed = meets_targets(summary)
    cost = "unknown" if summary.cost_usd is None else f"${summary.cost_usd:.4f}"
    rows = [
        ("Critical field accuracy", f"{summary.field_accuracy:.1%}", ">= 95%", passed["field_accuracy"]),
        ("H code and CAS recall", f"{summary.code_recall:.1%}", ">= 95%", passed["code_recall"]),
        ("Hallucination rate", f"{summary.hallucination_rate:.1%}", "0%", passed["hallucination_rate"]),
        ("Calibration (confident and correct)", _pct(summary.calibration), ">= 98%", passed["calibration"]),
        ("Fields sent to review", _pct(summary.review_rate), "10% to 25%", None),
        ("Mean latency per SDS", f"{summary.mean_latency_ms / 1000:.1f} s", "< 30 s", None),
        ("p95 latency per SDS", f"{summary.p95_latency_ms / 1000:.1f} s", "", None),
        ("Tokens in / out", f"{summary.input_tokens} / {summary.output_tokens}", "", None),
        ("Cost", cost, "", None),
        ("Documents (failed)", f"{summary.documents} ({summary.failed_documents})", "", None),
    ]
    lines = ["| Metric | Result | Target | Pass |", "| --- | --- | --- | --- |"]
    for name, value, target, ok in rows:
        mark = "" if ok is None else ("yes" if ok else "**no**")
        lines.append(f"| {name} | {value} | {target} | {mark} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score ChemReady predictions against the gold set.")
    parser.add_argument("--gold", type=Path, required=True, help="Folder of gold *.json files")
    parser.add_argument(
        "--pdfs", type=Path, required=True, help="Folder with the PDFs named in the gold files"
    )
    parser.add_argument("--predictions", type=Path, required=True, help="Folder of prediction *.json files")
    parser.add_argument("--price-in", type=float, help="USD per million input tokens")
    parser.add_argument("--price-out", type=float, help="USD per million output tokens")
    parser.add_argument("--label", default="", help="Name for this run in the results log, e.g. v1")
    parser.add_argument("--log", type=Path, help="Append the summary as one JSON line to this file")
    parser.add_argument("--details", action="store_true", help="Print every error per document")
    parser.add_argument("--gate", action="store_true", help="Exit with code 1 if any target is missed")
    args = parser.parse_args(argv)

    price = (
        (args.price_in, args.price_out) if args.price_in is not None and args.price_out is not None else None
    )
    summary, scores = evaluate(args.gold, args.pdfs, args.predictions, price)

    print(format_table(summary))
    if args.details:
        for score in scores:
            for error in score.errors:
                print(f"- {score.sds_id}: {error}")
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "label": args.label,
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            **asdict(summary),
        }
        with args.log.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")

    if args.gate and not all(meets_targets(summary).values()):
        print("Eval gate failed: at least one target was missed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
