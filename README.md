# ChemReady

**AI that turns chemical safety data sheets into a verified, audit ready chemical inventory. Every value is traced to its source page.**

> **Status: Discovery.** I am interviewing chemical and compliance managers at Bangladesh dyeing, washing and printing facilities before writing product code. This repository is built in public. Progress, eval results and decisions will be published here as they happen.

---

## The problem

Wet processing facilities that supply global fashion brands use roughly 170 to 200 chemical products each. Every product should have a safety data sheet (SDS), and brands expect a monthly chemical inventory screened against the ZDHC Manufacturing Restricted Substances List (MRSL).

A 2023 study of six Bangladesh facilities found that 28% to 48% of chemicals were still "not evaluated" against the MRSL. Building and maintaining the inventory from PDF safety data sheets is slow, manual work, and mistakes are risky.

## What ChemReady will do

1. **Upload** a batch of supplier SDS PDFs.
2. **Extract** key fields with an LLM: product, supplier, revision date, hazard codes, pictograms, ingredients with CAS numbers, PPE and storage. Every value carries its page number and exact quote.
3. **Validate** with plain code, not AI: the quote must exist in the PDF, CAS numbers must pass the check digit, hazard codes must be well formed.
4. **Review**: a person approves or edits only the doubtful fields.
5. **Export** an audit ready chemical inventory in Excel, with missing and outdated data flagged.

**Principle:** if the AI is not sure, it says "not found" and sends the field to human review. It never guesses. ChemReady never claims a chemical is MRSL conformant; only the official tools decide that.

## Architecture (planned)

```
PDF upload
  -> Parse text per page (PyMuPDF; scans go to OCR)
  -> Split into the 16 GHS sections
  -> Extract with LLM into a Pydantic schema (value + page + quote)
  -> Validate in code (grounding, CAS checksum, H code format)
  -> Human review of flagged fields
  -> Chemical inventory (SQLite) -> Excel export
```

## Planned stack

Python, FastAPI, Pydantic, PyMuPDF, SQLite, Gemini API (public files only) or a local model via Ollama (private files), sentence-transformers for search, GitHub Actions for CI.

## How quality will be measured

| Metric | Target |
| --- | --- |
| Critical field accuracy | 95% or higher |
| Invented values on critical fields | 0 |
| Saved values traced to a source quote | 100% |
| Time to prepare a monthly inventory | 70% less than today |

Results will be measured on a hand labelled gold set of 30 safety data sheets and published in `evals/results.md`.

## Roadmap

- [ ] Customer discovery: 10 interviews with chemical and compliance managers
- [ ] Gold set of 30 labelled safety data sheets and an eval script
- [ ] Extraction engine with validation
- [ ] Review screen, inventory and Excel export
- [ ] Pilot with 2 facilities
- [ ] Public demo

## Are you a chemical or compliance manager?

I would like to learn how you prepare your chemical inventory today. Reach me on [LinkedIn](https://www.linkedin.com/in/alqurayishsharkar/) or at alqurayish@gmail.com.

## Author

**Md Alqurayish Sharkar**, AI Product Engineer and Founder of [D-SAi](https://d-sai.com).

## Sources

- [Process wise ZDHC MRSL conformance status of the Bangladesh RMG sector](https://rsisinternational.org/journals/ijriss/articles/evaluation-of-process-wise-zdhc-mrsl-conformance-status-of-bangladesh-rmg-sector/), IJRISS, 2023
- [ZDHC MRSL](https://www.roadmaptozero.com/mrsl)
- [About InCheck: FAQ for suppliers](https://knowledge-base.roadmaptozero.com/hc/en-gb/articles/38172043364765-About-InCheck-Frequently-Asked-Questions-Suppliers)

## License

MIT
