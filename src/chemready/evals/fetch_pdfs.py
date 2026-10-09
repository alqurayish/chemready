"""Download the public SDS PDFs named in the gold files, from their source URLs.

    uv run python -m chemready.evals.fetch_pdfs evals/gold evals/pdfs

The PDFs are not stored in Git (they belong to their publishers), so CI and new
contributors fetch them from the original public source recorded in each gold file.
"""

import sys
from pathlib import Path

import httpx

from chemready.evals.formats import load_gold


def fetch(gold_folder: Path, pdf_folder: Path, client: httpx.Client) -> list[str]:
    """Download missing PDFs. Returns a list of problems (empty when all files are present)."""
    problems = []
    pdf_folder.mkdir(parents=True, exist_ok=True)
    for record in load_gold(gold_folder):
        target = pdf_folder / record.file
        if record.synthetic or target.exists():
            continue
        if not record.source.url:
            problems.append(f"{record.sds_id}: no source URL in the gold file")
            continue
        try:
            response = client.get(record.source.url)
            response.raise_for_status()
        except httpx.HTTPError as error:
            problems.append(f"{record.sds_id}: download failed ({error})")
            continue
        if not response.content.startswith(b"%PDF"):
            problems.append(f"{record.sds_id}: the source URL did not return a PDF")
            continue
        target.write_bytes(response.content)
        print(f"{record.sds_id}: downloaded {len(response.content) // 1024} KB")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage: python -m chemready.evals.fetch_pdfs <gold folder> <pdf folder>")
        return 2
    headers = {"User-Agent": "ChemReady-evals/0.1 (gold set download for evaluation)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        problems = fetch(Path(args[0]), Path(args[1]), client)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
