# Quality and observability (Phase 9)

## Tracing every model call

`TracedClient` (`src/chemready/app/observability.py`) wraps whichever model client
is configured. Every call, successful or failed, is stored in the `model_call`
table and logged:

| Column | Why |
| --- | --- |
| `trace_id`, `document_id`, `facility_id` | Find all calls for one document or one factory |
| `provider`, `model`, `prompt_version` | Compare models and prompt versions over time |
| `input_tokens`, `output_tokens`, `latency_ms`, `attempts` | Speed, retries on rate limits, token use |
| `cost_usd` | Tokens × `CHEMREADY_PRICE_*_PER_MILLION` (0 for Ollama and the free tier) |
| `ok`, `error` | Which calls failed and why |

Settings → **AI usage this month** and `GET /api/usage` summarise it.

## Logs

- `CHEMREADY_LOG_FORMAT=json` writes one JSON object per line (for log tools);
  `text` is easier to read locally.
- Every request gets an id (or keeps the caller's `X-Request-ID`), returned in the
  `X-Request-ID` header and included in every log line for that request.
- Logged per request: method, path, status, milliseconds. Never passwords, keys,
  file contents or extracted values.

## Error handling

- Expected problems (bad file, wrong format, privacy refusal) are shown to the user
  in plain words.
- Unexpected errors are logged with the stack trace and the request id; the user sees
  "Something went wrong on our side… Reference: <id>" and never internal details.
- A failed document never stays stuck in "processing": it becomes `failed` with a reason.

## CI eval gate

`.github/workflows/ci.yml`, job **Eval gate**:

1. **Every push:** builds the fictional set, runs the full pipeline with the rules
   baseline (no AI, no secrets) and fails if accuracy or recall drops against
   `evals/baselines/synthetic-rules.json`, or if any value is invented.
2. **When the real gold set exists:** add the repository secret
   `CHEMREADY_GEMINI_API_KEY`, the repository variable `CHEMREADY_GEMINI_MODEL`, and
   `evals/baselines/real.json` (copy the accepted v1 numbers). The job then downloads
   the public PDFs from their source URLs, runs the model on 5 gold files and fails
   if field accuracy or recall drops more than 2 points, or if anything is invented.

Example `evals/baselines/real.json`, filled in from your first accepted real run:

```json
{"field_accuracy": 0.0, "code_recall": 0.0}
```
