"""Run extraction on every SDS in the gold set and save one prediction file each.

    uv run python -m chemready.evals.run_extraction --gold evals/gold --pdfs evals/pdfs --out evals/runs/v1

The provider comes from settings (.env). Gold files are public SDS, so any
provider may be used. Then score the run with chemready.evals.run_evals.
"""

import argparse
import time
from pathlib import Path

from chemready.config import get_settings
from chemready.evals.formats import Prediction, load_gold, write_json
from chemready.extraction.extract import ScannedDocumentError, extract_sds
from chemready.extraction.llm import LlmClient, LlmError, make_client
from chemready.pdf.parse import PdfError, parse_pdf


def run(
    gold_folder: Path, pdf_folder: Path, out_folder: Path, client: LlmClient, limit: int | None = None
) -> list[Prediction]:
    predictions = []
    for record in load_gold(gold_folder)[:limit]:
        start = time.perf_counter()
        try:
            document = parse_pdf(pdf_folder / record.file)
            result = extract_sds(document, client, private=False)
            prediction = Prediction(
                sds_id=record.sds_id,
                provider=result.usage.provider,
                model=result.usage.model,
                latency_ms=result.usage.latency_ms,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                extraction=result.extraction,
            )
        except (PdfError, LlmError, ScannedDocumentError, FileNotFoundError) as error:
            prediction = Prediction(
                sds_id=record.sds_id,
                provider=client.provider,
                model=client.model,
                latency_ms=(time.perf_counter() - start) * 1000,
                error=str(error),
            )
        write_json(prediction, out_folder / f"{record.sds_id}.json")
        status = "error: " + prediction.error if prediction.error else f"{prediction.latency_ms / 1000:.1f} s"
        print(f"{record.sds_id}: {status}")
        predictions.append(prediction)
    return predictions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract every gold SDS and save predictions.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pdfs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Folder for this run, e.g. evals/runs/v1")
    parser.add_argument("--limit", type=int, help="Only the first N gold files")
    args = parser.parse_args(argv)
    run(args.gold, args.pdfs, args.out, make_client(get_settings()), args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
