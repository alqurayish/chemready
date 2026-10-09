# Demo GIF script

A 45 to 60 second screen recording for the README, LinkedIn and interviews. Record the
real app with the demo account (fictional data only).

## Setup

```bash
uv run chemready seed-demo
CHEMREADY_LLM_PROVIDER=rules uv run chemready serve
```

- Browser window 1280 × 800, zoom 100%, bookmarks bar hidden.
- Have one fictional PDF ready to upload: `uv run python -m chemready.demo.synthetic_set evals/synthetic`
  then use a file from `evals/synthetic/pdfs/`.
- Free recorders: ScreenToGif (Windows), Kap (Mac), Peek (Linux). Record at 12 to 15
  frames per second to keep the file small.

## Shots

| # | Seconds | Show | Caption to add |
| --- | --- | --- | --- |
| 1 | 0 to 5 | Website hero, then click **Try the demo** | "SDS files in, verified inventory out" |
| 2 | 5 to 12 | Upload: choose a PDF, tick "public SDS", click **Upload and process** | "Upload a batch of supplier SDS PDFs" |
| 3 | 12 to 18 | Review list: the new file goes from processing to **Needs review** | "AI extracts, code checks every value" |
| 4 | 18 to 32 | Open **Demosoft SL**: the flagged field is first; click a passed field and watch the quote highlight on the page | "Every value is traced to its page and quote" |
| 5 | 32 to 38 | Mark the doubtful field **Not in SDS**, then **Approve product** | "A person approves only what is doubtful" |
| 6 | 38 to 45 | Inventory, then **Actions** with "SDS too old" and "Missing CAS" | "See what needs action" |
| 7 | 45 to 50 | Click **Export CIL**, show the Excel file | "Export your chemical inventory list" |
| 8 | 50 to 55 | End card: logo, "ChemReady · A D-SAi Product", GitHub link | |

## Rules

- Fictional data only. Never record a factory's real files or names.
- Do not show a cost or accuracy number in the GIF until it comes from the real gold set.
- Keep the final GIF under 10 MB so it loads in the README. Save it as `docs/screenshots/demo.gif`.
