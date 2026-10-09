# Decisions

Why ChemReady is built the way it is. Each entry says what we chose, why, what we
gave up, and when to revisit it. Newest at the bottom.

---

### 1. Design and prototype before code

**Choice:** Phase 1 produced user flows, screen specs, a design system and a clickable
prototype before any product code.
**Why:** The PRD says nothing is built until interviews pass the go rule. A prototype
is cheap to change and lets chemical managers react to something real.
**Trade-off:** No working extraction during discovery.

### 2. Python, uv and a `src/` layout

**Choice:** Python 3.12, uv for environments and a lock file, code in `src/chemready/`.
**Why:** The founder's strongest language; the PDF and AI libraries are Python; uv is
fast and gives the same install everywhere (`uv.lock`).
**Revisit:** Python 3.14 once PyMuPDF and the other libraries fully support it.

### 3. One model interface: `llm.extract(schema, system, text)`

**Choice:** Every model sits behind one small interface (`LlmClient`). Providers:
Ollama (default), Gemini, a rules baseline, and a fake for tests.
**Why:** Switching models becomes a setting, and the evals decide which wins (PRD).
**Trade-off:** Provider-specific features (for example sending the whole PDF to Gemini
for scans) are not used yet.

### 4. Private factory files never go to a free AI tier

**Choice:** Uploads are private by default. `Settings.allows_private_data` is false for
the Gemini free tier, and `extract_sds` refuses with `PrivacyError` before anything is
sent. Ollama (local) is the default provider.
**Why:** Google's free tier may use submitted content to improve its products (PRD).
A leak would end the pilot and the business.
**Trade-off:** Pilots need Ollama on a decent laptop or a paid tier.

### 5. A rules baseline as a provider

**Choice:** `RulesClient` reads tidy "Label: value" lines with patterns, no AI.
**Why:** The demo and CI run without any account, and the evals need a baseline the
AI must beat.
**Trade-off:** It is weak on real, messy SDS files. It is a yardstick, not a product.

### 6. Every value carries its page and exact quote

**Choice:** The schema stores `value`, `page` and `quote` for every field; `null` means
not found.
**Why:** Auditors and sceptical managers must see where a value came from (PRD R2).
It also lets plain code check the AI.

### 7. Validation in plain code, confidence from evidence

**Choice:** Each value is checked: quote in the PDF (else the value is removed), quote on
the stated page, quote in the right SDS section, value inside its quote, and format
(CAS check digit, H code, pictogram, signal word, date). Confidence = share of checks
passed. Only values passing every check skip human review. Empty hazard sections always
go to review.
**Why:** The model's opinion of itself is not evidence. Code is cheaper and more
reliable for rules (PRD).
**Trade-off:** Some correct values go to review (for example pictograms shown only as
images). The evals measure the review rate (target 10% to 25%).

### 8. Prompt injection defence in four layers

**Choice:** (1) system prompt says the document is data only, (2) the document is wrapped
in tags it cannot close or fake page markers inside, (3) output must match the schema,
(4) the section check rejects values quoted from the wrong section.
**Why:** A supplier PDF is untrusted input. Layer 4 means even an obeyed injection cannot
pass validation silently. A test file with an injection is in the synthetic set.

### 9. SQLite with plain SQL

**Choice:** The six PRD tables plus `app_user`, `password_reset` and `model_call`, written
with the standard `sqlite3` module and no ORM.
**Why:** One file, no server, easy to back up; the SQL is readable for a learner.
**Revisit:** Move to Postgres when a second facility goes live (PRD).

### 10. One background worker thread

**Choice:** Documents are processed one at a time in a background thread; unfinished work
is picked up after a restart.
**Why:** Free tiers are rate limited; one at a time with retries and backoff stays inside
limits. No queue server to run.
**Revisit:** A real job queue if one facility uploads hundreds of files at once.

### 11. Server-rendered pages with Jinja2 (no JavaScript framework)

**Choice:** HTML pages rendered by FastAPI with Jinja2 templates and plain forms, using the
approved design's CSS. Menus use `<details>`; the review list refreshes itself.
**Why:** The founder knows Python, not React. Everything stays in one language and works on
slow connections.
**Trade-off:** No instant in-page updates or keyboard shortcuts yet (the prototype had them).

### 12. Accounts and sessions

**Choice:** Argon2 password hashes; signed session cookie (HttpOnly, SameSite=Lax, Secure in
production, 12 hours); `session_version` to sign out everywhere; five failed sign-ins lock an
email for 15 minutes; reset tokens hashed, single use, 30 minutes; same message whether or not
an email exists.
**Why:** Standard, well understood protections without extra services.
**Known gaps:** No CSRF tokens (SameSite=Lax blocks cross-site form posts in current browsers);
the sign-in lock is in memory (one server only); reset links are logged until an email
service is connected.

### 13. Every facility query filters by `facility_id`

**Choice:** Server-side authorization: no query reads another facility's rows. Tested by
signing in as two factories.
**Why:** A factory's chemical list is confidential.

### 14. Fictional data is labelled, and never used for accuracy claims

**Choice:** Synthetic SDS files say "FICTIONAL TEST DOCUMENT", gold records carry
`"synthetic": true`, and only real gold runs go into `evals/results.md`.
**Why:** Hard rule: never invent facts. A 100% score on tidy fictional files proves the
pipeline works, nothing more.

### 15. Public SDS PDFs are not stored in Git

**Choice:** Gold JSON files (labels, short quotes, source URL) are committed; PDFs are
fetched from their public source (`fetch_pdfs`) into a git-ignored folder.
**Why:** The publishers own the copyright.

### 16. Scanned PDFs are detected, not read, in the MVP

**Choice:** Image-only pages are detected and the document fails with a clear reason.
**Why:** OCR adds a system dependency (Tesseract) or sends the file to a cloud model. Measure
how many pilot SDS files are scans first (PRD open question).

### 17. Observability built in

**Choice:** Every model call is stored in `model_call` (tokens, time, retries, cost, error)
and logged as JSON with a request id. Costs use prices you set, 0 by default.
**Why:** The PRD asks for cost per SDS and under 30 s per SDS. You cannot improve what you
do not measure.

### 18. CI eval gate in two layers

**Choice:** Every push runs the full pipeline on the fictional set and fails on any drop or
invented value. Once the real gold set, a baseline and a Gemini secret exist, CI also runs
5 real files and fails if accuracy drops more than 2 points.
**Why:** PRD: "fails the build if accuracy drops". The fictional layer works today without
secrets; the real layer turns on by itself.

### 19. Docker image and a public demo on Hugging Face Spaces

**Choice:** One Dockerfile (non-root, production defaults, health check). The public demo
uses fictional data and the rules baseline.
**Why:** Free hosting for a portfolio demo. Real pilots need a private deployment.

### 20. Design refinements

The top navigation pill, plain white background, glass cards, short labels, progressive sign
in and branding were decided with the founder in Phase 1. See
[docs/design/04-navigation-and-sign-in.md](docs/design/04-navigation-and-sign-in.md).

---

## Open questions (from the PRD, still open)

- Which solution provider does each pilot use, and what columns does its CIL template need?
- Are most supplier SDS files digital PDFs or scans?
- Is the latest MRSL version 3.1 or 4.0, and when does the switch apply?
- Who signs off software spend at a facility, and at what monthly price?
- Do factories receive SDS files in languages other than English?
