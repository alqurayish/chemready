# AI extraction (Phase 5)

## Flow

```
PDF ─► parse (PyMuPDF) ─► sections 1, 2, 3, 7, 8, 16 with page markers
    ─► privacy check ─► llm.extract(SdsExtraction, SYSTEM_PROMPT, text)
    ─► JSON that must match the schema ─► validation (Phase 6)
```

| File | Job |
| --- | --- |
| `src/chemready/schema.py` | The contract: every value has `value`, `page`, `quote`; `null` means not found |
| `src/chemready/extraction/llm.py` | One interface, `extract(schema, system, text, client)`. Providers: Gemini, Ollama, Fake (tests) |
| `src/chemready/extraction/baseline.py` | Rules baseline, no AI. Offline demo and the number the AI must beat |
| `src/chemready/extraction/prompts.py` | System prompt (`PROMPT_VERSION`), document wrapping, injection defence |
| `src/chemready/extraction/extract.py` | Privacy guard, scan guard, one call per SDS |

## Choosing a provider

| Provider | Setting | Files allowed | Notes |
| --- | --- | --- | --- |
| Ollama | `CHEMREADY_LLM_PROVIDER=ollama`, `CHEMREADY_OLLAMA_MODEL=<name>` | Public and private | Runs on your laptop. Install from ollama.com, then `ollama pull <model>`. Pick a model that supports structured output; compare candidates with the evals. |
| Gemini | `CHEMREADY_LLM_PROVIDER=gemini`, key and model | Public only while `CHEMREADY_GEMINI_FREE_TIER=true` | Check the current free-tier models and limits on Google's pricing page on the day you start; they change. |
| Rules | `CHEMREADY_LLM_PROVIDER=rules` | Any (no AI) | Baseline and offline demo |

No model name is hard-coded. Pick it in `.env` and let the evals decide.

## Prompt injection defence

An SDS is untrusted input: a PDF can contain text like "ignore your instructions".

1. The system prompt says the document is data only and must never be obeyed.
2. The document sits inside `<sds_document>` tags. The text cannot close the tag
   or fake a `=== page N ===` marker (both are neutralised).
3. Output must match the Pydantic schema exactly, or it is rejected (`LlmError`).
4. Validation (Phase 6) checks every quote is in the PDF **and in the right
   section**, so an injected value from section 16 cannot become a product name.

The synthetic set includes such an injection (`synthetic-004`).

## Run v1 and record results

```bash
# 1. Collect and label the real gold set first (docs/data/collecting-sds.md)
# 2. Extract every gold SDS with the provider in .env
uv run python -m chemready.evals.run_extraction --gold evals/gold --pdfs evals/pdfs --out evals/runs/v1
# 3. Score it and log it
uv run python -m chemready.evals.run_evals --gold evals/gold --pdfs evals/pdfs --predictions evals/runs/v1 \
    --price-in 0 --price-out 0 --label v1 --log evals/results.jsonl --details
# 4. Copy the table into evals/results.md with the date, model and PROMPT_VERSION
```

Also run the rules baseline (`CHEMREADY_LLM_PROVIDER=rules`, label `v0-rules`) so
the results table shows how much the AI adds.

## Improve (v2, v3)

Read the `--details` errors, group them (wrong date picked, missed combined
codes, scans, two-column layouts) and change one thing at a time: the prompt
(bump `PROMPT_VERSION`), the sections sent, or the model. Re-run, compare, keep
what wins. Never tune on one file; look at the whole set.

**Status:** no real results yet. The code is tested end to end on fictional files
only. Real numbers need the 30-file gold set and a model (your Ollama install or
Gemini key).
