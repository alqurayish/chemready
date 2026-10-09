# Collecting SDS files for the gold set

The gold set is 30 hand-labelled SDS files (PRD, Quality and evals). This guide
explains where to get them and how to keep the process legal and private.

> This is practical guidance, not legal advice. If a pilot factory or a supplier
> has its own terms, those terms win. When unsure, ask the publisher or a lawyer.

## Two kinds of files, two sets of rules

| | Public SDS | Private (pilot factory) SDS |
| --- | --- | --- |
| Where from | Manufacturer or distributor websites that offer SDS for free download | A pilot factory, with its written permission |
| Stored in | `evals/pdfs/` on your computer (git-ignored) | `data/private/` (git-ignored) |
| Committed to GitHub | The gold **JSON** only, with the source URL. Never the PDF. | Nothing. Not even the gold JSON, unless the factory agrees in writing. |
| AI allowed | Any provider, including the Gemini free tier | Ollama (local) or a paid tier only. Never a free tier. |

## Rules for public SDS

1. **Download only what the publisher offers publicly**, through its own website,
   without logging in, paying, or getting round any block.
2. **Read the site's terms of use** before downloading. If they forbid automated
   download, download by hand. If they forbid reuse, skip that site.
3. **Do not scrape.** Download files one by one by hand. Thirty files take
   about an hour.
4. **Do not redistribute the PDFs.** The publisher owns the copyright. Keep the
   PDFs in `evals/pdfs/` (git-ignored) and commit only the gold JSON, which has
   short quotes, your labels and the source URL.
5. **Record the source** in every gold file: URL, publisher and download date.
   This is your proof of where each file came from.
6. **Check that each file is a real SDS**: 16 numbered sections, a company name,
   a revision date. Skip product brochures and technical data sheets.

## What to collect (PRD targets)

| Requirement | Count |
| --- | --- |
| Total files | 30 |
| Different suppliers | at least 10 |
| Scanned (image-only) files | 5 |
| Badly formatted files (odd headings, tables, two columns) | 5 |
| Language | English only (PRD non-goal: other languages) |

Prefer the kinds of products a Bangladesh wet processing facility buys: dyes,
pretreatment auxiliaries (wetting agents, detergents), alkalis and acids,
softeners, binders, printing pastes and finishing chemicals. Your discovery
interviews will tell you which product types matter most.

## Where to look

- Websites of textile chemical manufacturers and distributors that publish an
  "SDS" or "MSDS" download area.
- Chemical distributors' public SDS libraries.
- If you are unsure a site is allowed, email the publisher and ask. Keep the reply.

## Private files from pilot factories

1. Get **written permission** (an email is enough) that says what files you may
   use and for what purpose.
2. Store them only in `data/private/`. Never in `evals/pdfs/`, never in a chat,
   never in a public issue.
3. Run them only with `CHEMREADY_LLM_PROVIDER=ollama`, or a paid tier with
   `CHEMREADY_GEMINI_FREE_TIER=false`. The settings refuse private files on the
   free tier (`Settings.allows_private_data`).
4. Delete them when the pilot agreement ends, if the factory asks.

## Steps

1. Download a file into `evals/pdfs/` and name it `sds-001.pdf`, `sds-002.pdf`, and so on.
2. Copy `docs/data/gold-template.json` to `evals/gold/sds-001.json`.
3. Fill in `source` (URL, publisher, date) and label the fields with the
   [labelling guide](labelling-guide.md).
4. Run `uv run python -m chemready.evals.check_gold evals/gold evals/pdfs` to catch typos.
