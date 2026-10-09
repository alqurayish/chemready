# Evals

An eval is an automatic test of the AI's answers against answers a person
checked by hand. Without evals we cannot say ChemReady works.

## Folders

| Folder | What | In Git? |
| --- | --- | --- |
| `evals/gold/` | Hand-labelled answers, one JSON file per real public SDS | Yes |
| `evals/pdfs/` | The public SDS PDFs named in the gold files | No (not ours to redistribute) |
| `evals/runs/<label>/` | Predictions from one extraction run | No |
| `evals/synthetic/` | Fictional SDS + answers, made by code, for software tests only | No (generated) |
| `evals/results.md` | The results table of every recorded run | Yes |

Guides: [collecting SDS](../docs/data/collecting-sds.md) ·
[labelling](../docs/data/labelling-guide.md) ·
[gold template](../docs/data/gold-template.json)

## Metrics (PRD targets)

| Metric | How it is scored | Target |
| --- | --- | --- |
| Critical field accuracy | Product name, supplier, revision date (one unit each) and every H code, pictogram and CAS number (one unit each). Extra codes not in the gold set count as wrong. | ≥ 95% |
| H code and CAS recall | Share of gold H codes and CAS numbers found | ≥ 95% |
| Hallucination rate | Share of predicted critical values whose quote and value are both missing from the PDF text | 0% |
| Latency | Mean and p95 seconds per SDS | < 30 s |
| Cost | Tokens × the price you pass in. "unknown" if no price is given. | measure in week 2 |

## Commands

```bash
# Check gold files for typos (JSON format, CAS check digit, H codes, quotes in the PDF)
uv run python -m chemready.evals.check_gold evals/gold evals/pdfs

# Score a saved run (prices in USD per million tokens; 0 and 0 on the free tier)
uv run python -m chemready.evals.run_evals --gold evals/gold --pdfs evals/pdfs \
    --predictions evals/runs/v1 --price-in 0 --price-out 0 --label v1 --log evals/results.jsonl --details

# Try the whole thing on the fictional set
uv run python -m chemready.demo.synthetic_set evals/synthetic
```

Extraction runs that create `evals/runs/<label>/` are added in Phase 5.
