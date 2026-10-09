# Labelling guide

How to write the correct answers for one SDS. A gold file is only useful if two
people would label the same SDS the same way, so follow these rules exactly.

**Golden rule: copy what the SDS says. Never correct it, complete it or guess.**
If the SDS is wrong (for example an invalid CAS number), label what is printed
and explain in `notes`. If something is not in the SDS, use `null`.

## The file

Start from `docs/data/gold-template.json`. Fill in every field below `expected`.
Each value has three parts:

| Part | Meaning |
| --- | --- |
| `value` | The answer, written by the rules below, or `null` if not in the SDS |
| `page` | The page number in the PDF viewer, starting at 1 |
| `quote` | The exact words copied from the PDF that show the value (copy and paste) |

## Field rules

| Field | Section | Rule | Example |
| --- | --- | --- | --- |
| `product_name` | 1 | Trade name as printed, without "Product name:" | `Demowet NF` |
| `supplier` | 1 | Company that issued the SDS (manufacturer or importer), legal name as printed | `Example Auxiliaries Ltd` |
| `revision_date` | 1 or 16 | The **revision** date as `YYYY-MM-DD`. Not the print date or issue date unless it is the only date, then say so in `notes`. | `2025-03-01` |
| `signal_word` | 2 | Exactly `Danger` or `Warning`, or `null` if there is none | `Warning` |
| `hazard_statements` | 2 | One item per H code in section 2. `code` exactly as `H` + 3 digits. Do not add codes from other sections. | `{"code": "H315", "statement": "Causes skin irritation."}` |
| `pictograms` | 2 | One item per pictogram, `GHS01` to `GHS09`. If the SDS shows only the image, identify it from the symbol and put `"quote": null`. | `{"code": "GHS07"}` |
| `ingredients` | 3 | One item per listed substance. `cas_number` exactly as printed, or `null` if not disclosed. | `{"name": "Water", "cas_number": "7732-18-5", "percent": "75-85%"}` |
| `ppe` | 8 | The personal protection text, shortened to the list of equipment | `Protective gloves, safety goggles` |
| `storage` | 7 | The storage conditions sentence | `Store in a cool, dry place.` |

### Edge cases

- **EUH statements** (EU supplementary, for example EUH031) are not H codes.
  Leave them out of `hazard_statements` and mention them in `notes`.
- **Combined codes** like `H302+H312`: record each code as its own item.
- **Trade secret CAS**: `cas_number: null`, and copy the "not disclosed" text into `quote`.
- **Several dates**: use the one labelled revision; note the others.
- **Two products in one SDS**: skip the file; it is not a typical case.
- **Scanned file**: set `"is_scanned": true`. Page numbers still follow the PDF viewer.

## Checking your work

1. Run `uv run python -m chemready.evals.check_gold evals/gold evals/pdfs`. It checks
   the JSON format, CAS check digits, H code format and that every quote is in the PDF.
2. A CAS number that fails the check digit may be a real typo in the SDS. Keep it as
   printed and explain in `notes`.
3. Ask a second person to label 5 of the 30 files on their own. Where you disagree,
   fix this guide so the rule is clearer, then fix the labels.

## Time

About 20 to 30 minutes per SDS at first, faster later. The PRD estimates two days
for 30 files. It is the most valuable asset in the project: protect it.
