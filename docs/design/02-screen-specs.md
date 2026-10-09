# Phase 1, Step 2: Screen specifications (P0)

For each screen: layout, key components, states (empty, loading, error,
success) and the exact copy. Builds on `01-tasks-screens-flow.md`.

All product, supplier and person names below are fictional samples. Hazard
codes on sample rows are illustrative only; never copy them into real data.

## Global rules

**Target device.** Laptop, minimum width 1280 px. No mobile layout (PRD non-goal).

**Shell layout (every screen).**

```
┌───────────────┬──────────────────────────────────────────────┐
│ ChemReady     │  Page title                 [Primary action] │
│ Facility name │  One line that says what this page is for    │
│               ├──────────────────────────────────────────────┤
│ Upload        │                                              │
│ Documents (12)│               Page content                   │
│ Inventory     │                                              │
│ Needs action 7│                                              │
│ Settings      │                                              │
│               │                                              │
│ ● Local model │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

- Sidebar 220 px. Counts show work waiting: Documents = files to review,
  Needs action = open flags.
- Bottom of sidebar: the processing mode badge, always visible
  ("● Local model" or "● Public test mode").
- One primary button per page, top right.

**Words we use, and words we never use.**

| Use | Never use | Why |
|---|---|---|
| Verified | Conformant, compliant, safe, approved chemical | ChemReady checks data, not regulation |
| Needs review | Error, AI uncertain | Tells the user what to do |
| Missing | Null, N/A, not found by AI | Plain fact about the SDS |
| Passed checks | Correct, confirmed | Only a person makes a value Verified |
| Quote not found in the PDF | Hallucination | Customer language, not ML language |

**Field statuses (used on S3, S5).**

| Status | Meaning | When |
|---|---|---|
| Passed checks | AI found it, quote exists in PDF, format checks pass, high confidence | Before a person approves |
| Needs review | Low confidence, a check failed, or a hazard section is empty | Before a person approves |
| Missing | The SDS does not contain it (confirmed by code or by a person) | Any time |
| Verified | A person approved the product with this value | After approval |

**Standard footer on Inventory, Product record and Export:**
"ChemReady checks that your data matches your SDS files. It does not decide
MRSL conformance. Use the ZDHC Gateway and your solution provider for that."

**Dates.** Always `9 Oct 2026` (day, short month, year). Never `10/09/2026`,
which is read differently in different countries.

---

## S1 Upload

**Purpose:** get a batch of SDS PDFs into ChemReady (R1).

**Layout**

```
Upload SDS files                                   [View documents →]
Add up to 50 PDF files at a time.

┌──────────────────────────────────────────────────────────────┐
│          Drag SDS PDF files here, or  [Choose files]         │
│          PDF only · up to 50 files · up to 20 MB each        │
└──────────────────────────────────────────────────────────────┘
● Local model: files are processed on the ChemReady server and are
  not sent to any outside AI service.

This batch (14 files)
 ✓ Caustic Soda Flakes SDS.pdf      added
 ✓ Sample Reactive Red SDS.pdf         added
 ✕ inventory_sept.xlsx              Not a PDF. Only PDF files can be added.
 ✕ Softener ABC SDS.pdf             Already uploaded on 3 Oct 2026. Skipped.
```

**Components:** drop zone, file picker button, processing mode notice,
batch result list (file name, result icon, reason).

**States**

| State | What the user sees |
|---|---|
| Empty | Drop zone only. Copy: "Drag SDS PDF files here, or Choose files". |
| Dragging | Drop zone border highlights. Copy: "Drop to add files". |
| Loading | Each file shows a thin upload bar. Copy: "Uploading 6 of 14…" |
| Success | Toast: "12 files added. Processing has started." Button: "View documents". |
| Partial | Accepted files listed with ✓, rejected with ✕ and the reason. |
| Error, too many | "You selected 62 files. Please select 50 or fewer." Nothing is added. |
| Error, not PDF | "Not a PDF. Only PDF files can be added." |
| Error, duplicate | "Already uploaded on {date}. Skipped." (uses file hash) |
| Error, too large | "This file is larger than 20 MB. Please check it is a single SDS." |
| Error, network | "Upload stopped. Check your connection and try again." Button: "Retry". |

**Mode notice copy**

- Local model: "Local model: files are processed on the ChemReady server and
  are not sent to any outside AI service."
- Public test mode (amber): "Public test mode: files are sent to Google's free
  Gemini service. Upload public SDS files only, never your factory's private
  files."

Assumption to confirm: 20 MB per file is not in the PRD. Check the size of real
pilot SDS files and adjust.

---

## S2 Documents (review queue)

**Purpose:** show progress per file and what is waiting for review (R1, R4).

**Layout**

```
Documents                                            [Upload files]
Every SDS you uploaded and where it is in the process.

[All 48] [Needs review 12] [Processing 3] [Approved 31] [Failed 2]   🔍 Search

File                       Product              Status           Flags  Uploaded
Sample Reactive Red SDS.pdf   Sample Reactive Red     Needs review       4    9 Oct 2026   [Review]
Caustic Soda SDS.pdf       —                    Extracting ▓▓▓░░   —    9 Oct 2026
Old binder scan.pdf        —                    Failed             —    8 Oct 2026   [Retry] [Remove]
Softener ABC SDS.pdf       Softener ABC         Approved           0    3 Oct 2026   [View]
```

**Components:** status tabs with counts, search box, table, one row action.
Default sort: Needs review first, then newest.

**Processing stages** (shown under the status while processing):
Queued → Reading pages → Finding sections → Extracting → Checking → Ready for review.
Scanned PDFs show a small "Scanned, using OCR" tag.

**States**

| State | What the user sees |
|---|---|
| Empty | "No SDS files yet. Upload your first batch to start your inventory." Button: "Upload files". |
| Loading | Table skeleton (grey bars) for under 1 second. |
| Processing | Live progress per row. Top banner: "Processing 3 files. You can keep working; we will update this page." |
| Waiting for AI | Row copy: "Waiting for AI capacity. Retrying automatically." (free tier rate limits) |
| Error, failed file | Status "Failed" with reason on hover: "Could not read this file. It may be a poor scan or password protected." Actions: Retry, Remove. Also creates an "Unreadable file" flag on S6. |
| Success | Tab "Needs review" count drops as files are approved. Toast after approval: "Sample Reactive Red added to inventory." |
| All done | When nothing is waiting: "All caught up. Nothing waiting for review." |

---

## S3 Review SDS

**Purpose:** a person checks only the doubtful fields, sees the source and
approves the product (R2, R3, R4). This is the most important screen.

**Layout**

```
← Documents   Sample Reactive Red · Example Dyechem Ltd            [Approve product]
4 fields need review · 21 passed checks · 1 missing           (disabled until 0 need review)

┌──────── Fields (left, 45%) ─────────┬──────── Source (right, 55%) ────────┐
│ NEEDS REVIEW (4)                     │ Page 2 of 9          [‹] [›] [zoom] │
│ ▸ H code  "H319"           p.2  ⚠    │                                     │
│   Low confidence                     │  ...Causes serious eye irritation  │
│   [Approve] [Edit] [Not in SDS]      │  ████ H319 ████ highlighted quote   │
│ ▸ CAS (ingredient 2) 1310-73-3  ✕    │                                     │
│   CAS check digit is wrong           │                                     │
│ ▸ Revision date      —          ⚠    │                                     │
│   Quote not found in the PDF         │                                     │
│ ▸ Pictograms   GHS05            ⚠    │                                     │
│                                      │                                     │
│ MISSING (1)                          │                                     │
│ ▸ Storage            Missing         │                                     │
│                                      │                                     │
│ PASSED CHECKS (21)  [Show]           │                                     │
└──────────────────────────────────────┴─────────────────────────────────────┘
Keyboard: A approve · E edit · M not in SDS · J/K next/previous field
```

**Field groups** (follow the SDS sections so the manager recognises them):

1. Identification (section 1): product name, supplier, revision date
2. Hazards (section 2): signal word, H codes with statements, pictograms
3. Composition (section 3): ingredients with substance name, CAS number, percent
4. Handling and storage (section 7): storage conditions
5. Exposure controls (section 8): PPE

**Each field row shows:** label, value, page number, status icon, the reason
it needs review, and three actions. Clicking a row scrolls the PDF to the page
and highlights the quote.

**Actions per field**

| Button | What happens | Copy after action |
|---|---|---|
| Approve | Keeps the AI value | "Approved" |
| Edit | Inline box; person types the correct value and can point to a page | "Edited by {name}" |
| Not in SDS | Value saved as Missing; may create an action flag (for example Missing CAS) | "Marked as missing" |

**Reasons shown (exact copy)**

| Check result | Copy |
|---|---|
| Quote not in PDF text | "Quote not found in the PDF. The value was removed." |
| CAS check digit fails | "CAS check digit is wrong. Check the number in the SDS." |
| H code format wrong | "This is not a valid H code format (H plus 3 digits)." |
| Low confidence | "Low confidence. Please check against the source." |
| Empty hazard section | "Section 2 looks empty. Please check the hazards." |
| Not found | "Not found in this SDS." |

**States**

| State | What the user sees |
|---|---|
| Loading | Fields skeleton left, "Loading page 1…" right. |
| PDF page fails to load | "Could not show this page. Field values and quotes are still available." Button: "Try again". |
| In progress | Header counter updates live: "2 fields need review". |
| Ready to approve | Primary button enabled. Copy: "All doubtful fields are resolved. Approve product to add it to your inventory." |
| Approve disabled | Tooltip: "Resolve the 2 fields that need review first." |
| Success | Toast: "Sample Reactive Red added to inventory." Auto-opens the next SDS waiting: "Next: Caustic Soda Flakes (3 fields to review)". |
| Save error | "Could not save your change. Your edit is kept on this page. Try again." |
| Zero flags | Header: "All 26 fields passed checks. Look over them, then approve." Approve still needs one click. |

---

## S4 Inventory

**Purpose:** one searchable table of approved products (R5).

**Layout**

```
Inventory                                                   [Export CIL]
Every approved chemical product in your facility.          148 products

🔍 Search product, supplier, CAS or H code
[Supplier ▾] [Hazard ▾] [Pictogram ▾] [Status ▾]   Clear filters

Product            Supplier             Signal   H codes          SDS date      Status
Sample Reactive Red   Example Dyechem Ltd  Warning  H317 H334        12 Mar 2024   ● Verified
Caustic Soda       Example Chem Co      Danger   H290 H314        2 Jan 2021    ● Needs action: SDS 5 years old
Binder XL          Example Polymers     —        —                5 Jun 2025    ● Needs action: Missing CAS
```

**Components:** search, four filters, sortable table, status pill, row click
opens S5. Status filter values: Verified, Needs action.

**States**

| State | What the user sees |
|---|---|
| Empty | "Your inventory is empty. Approve reviewed SDS files and they will appear here." Button: "Go to documents". |
| No results | "No products match your search. Clear filters to see all 148 products." |
| Loading | Table skeleton. |
| Error | "Could not load your inventory. Refresh the page. Your data is safe." Button: "Refresh". |
| Success | Table with count: "Showing 12 of 148 products". |

---

## S5 Product record (audit trail)

**Purpose:** show an auditor where every value came from (R2, R3).

**Layout:** same split view as S3, read only.

```
← Inventory   Caustic Soda Flakes · Example Chem Co     [Upload newer SDS] [Reopen review]
Approved by Rahima Akter on 9 Oct 2026 · SDS revision date 2 Jan 2021 · Source: Caustic Soda SDS.pdf

Field          Value                          Page  Quote                          Check          Status
H code         H314 Causes severe skin burns   2    "H314 Causes severe skin..."   Format OK      Verified
CAS (ingr. 1)  1310-73-2                       3    "Sodium hydroxide 1310-73-2"   Check digit OK Verified
Storage        Missing                         —    —                              —              Missing
Revision date  2 Jan 2021                      1    "Revision date: 02.01.2021"    Date OK        Verified · Edited by Rahima Akter
```

**Components:** header with approval info, value table, PDF viewer (opens on
row click), change history per field.

**States**

| State | What the user sees |
|---|---|
| Loading | Skeleton. |
| Error | "Could not load this product. Go back to the inventory and try again." |
| Source PDF missing | "The source file is no longer available. Values and quotes are kept for your records." |
| Reopen review | Confirm dialog: "Reopen review? This product stays in the inventory but shows Needs review until you approve it again." Buttons: "Reopen review", "Cancel". |

---

## S6 Needs action

**Purpose:** one list of what the manager must chase or fix (R6).

**Layout**

```
Needs action                                                 7 open
Fix these before your monthly report.

[All 7] [SDS too old 3] [Missing CAS 2] [Missing sections 1] [Unreadable file 1]

Product / file         Problem                     Detail                                  Action
Caustic Soda Flakes    SDS too old                 Revision date 2 Jan 2021, 5 years old   [Upload newer SDS]
Binder XL              Missing CAS                 2 of 4 ingredients have no CAS number    [Open record] [Add note]
Fixer FX               Missing sections            Sections 8 and 9 not found               [Open record]
Old binder scan.pdf    Unreadable file             Could not read text from this file      [Retry] [Remove]
```

**Flag rules (from the PRD):** SDS older than the set age (default 3 years,
from Settings), missing CAS numbers, missing sections, unreadable file.
Flags close themselves when the cause is fixed (for example a newer SDS is
approved). They cannot be dismissed; the manager can add a note, which is
kept for the auditor.

**States**

| State | What the user sees |
|---|---|
| Empty (good) | "Nothing needs action. Your inventory data is complete." |
| Loading | Skeleton. |
| Error | "Could not load action flags. Refresh the page." |
| Note added | Toast: "Note saved." Row shows "Note: Supplier says CAS is a trade secret, asked on 9 Oct". |

---

## S7 Export CIL (dialog)

**Purpose:** download the monthly chemical inventory list in Excel (R7).

**Layout**

```
Export chemical inventory list
Month         [October 2026 ▾]
Template      [Generic CIL (ChemReady) ▾]

Before you export
⚠ 3 documents are still waiting for review. They will not be in this export.
⚠ 7 products have open action flags. They are listed on a separate "Flags" sheet.

Includes 148 approved products.
                                               [Cancel]  [Download Excel]
```

**Excel file:** first sheet matches the chosen template columns exactly. A
second sheet "Flags" lists open action flags, so the main sheet stays clean
for upload to the solution provider. File name:
`ChemReady_CIL_{facility}_{YYYY-MM}.xlsx`.

**States**

| State | What the user sees |
|---|---|
| Empty | "There are no approved products to export yet." Download disabled. |
| Warnings | Amber warnings as above. Download still allowed: the manager decides. |
| Loading | Button: "Preparing file…" |
| Success | "Downloaded ChemReady_CIL_Sunrise_2026-10.xlsx." |
| Error | "Could not create the file. Try again. If it keeps failing, contact support." |

Open question: the real template columns depend on the pilot's solution
provider. Until we see one, only "Generic CIL (ChemReady)" exists.

---

## S8 Settings

**Purpose:** set facility rules once (R6, R7).

**Layout:** one column form.

| Field | Control | Default | Help text |
|---|---|---|---|
| Facility name | Text | — | "Shown on exports." |
| Location | Text | — | "For example Gazipur." |
| Solution provider | Text | — | "The tool you upload your CIL to." |
| Export template | Dropdown | Generic CIL (ChemReady) | "More templates will be added for pilot facilities." |
| SDS maximum age | Number, years | 3 | "SDS files older than this are flagged as too old." |
| Processing mode | Read only | Local model | "Set by your administrator. Private factory files are never sent to a free AI service." |

Button: "Save settings".

**States**

| State | What the user sees |
|---|---|
| Loading | Form skeleton. |
| Validation error | Under SDS age: "Enter a whole number of years from 1 to 10." |
| Success | Toast: "Settings saved. Action flags updated." |
| Error | "Could not save settings. Try again." |

Processing mode is read only on purpose: switching to the public free tier is
a deliberate admin decision with the factory's written consent, not a toggle a
busy user can click by mistake.
