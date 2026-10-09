# Phase 1, Step 5: Usability test plan (5 tasks)

Test the clickable prototype with real chemical and compliance managers.

- Prototype: `prototype/index.html` (demo login `demo@chemready.app` / `demo1234`)
- Time: about 15 minutes, at the **end** of a discovery interview, never before it
- People: the same managers you interview (aim for at least 5 across 3 factory groups)

## How to run it

1. **Ask for consent.** "Can I show you an early prototype and watch how you use it?
   I am testing the design, not you. Nothing you click is saved. May I take notes
   (or record the screen)?"
2. **Ask them to think aloud.** "Please say what you are looking at and what you
   expect to happen as you go."
3. **Read each task word for word.** Do not explain buttons, point, or help. If
   they are stuck for 60 seconds, note it as a failure, then help and move on.
4. **After each task, ask the follow-up question.** Then stay quiet and let them talk.
5. **Reset the demo** (top right) before the next person.

Never use real factory files in the prototype. If a manager offers real SDS
files, collect them separately with written permission (Phase 3).

## The 5 tasks

### 1. Find the problem in a new SDS (review screen)

> "A supplier just sent a new SDS for *Demowet NF*. Please check it and add it to
> your inventory if it is correct."

Start: signed in, on Inventory.

| | |
|---|---|
| Tests | R3, R4. Can they find Review, see the 3 flagged fields first, and fix them using the source page? |
| Success | Fixes the revision date, the H code and the CAS number, then clicks Approve product, without help. |
| Watch for | Do they look at the PDF page on the right? Do they understand "Quote not found in the PDF"? Do they try to approve the wrong CAS number? |
| Follow-up | "How sure are you now that this product's data is correct? What would make you more sure?" |

### 2. Prove a value to an auditor (traceability)

> "An auditor asks where the hazard statement H314 for *Caustic Soda Flakes* came
> from. Show them."

| | |
|---|---|
| Tests | R2 and the core trust promise: every value is traced to its page and quote. |
| Success | Opens the product from Inventory, clicks the H314 row, and points at the highlighted quote. |
| Watch for | Do they search, or scroll? Is "page and quote" what an auditor would really accept, or do they want the original PDF file? |
| Follow-up | "Would this be enough for your auditor? What else do they usually ask for?" |

### 3. Decide what to fix first (action flags)

> "Your monthly report is due on Friday. What would you work on first, and why?"

| | |
|---|---|
| Tests | R6, H3. Do the flags help them choose, and do the categories match how they think? |
| Success | Opens Actions within 30 seconds and names a specific item to work on. |
| Watch for | Which flag they pick first (too old, missing CAS, missing sections, unreadable). Whether they expect to filter by supplier, or to email the supplier (R10, P1). |
| Follow-up | "Is anything missing from this list that you chase every month?" |

### 4. Export for your solution provider (CIL export)

> "Prepare this month's chemical inventory file to upload to the tool you use for
> InCheck."

| | |
|---|---|
| Tests | R7 and the open question about the real CIL template. |
| Success | Finds Export CIL, reads the warnings, and downloads (preview appears). |
| Watch for | Do they read the warnings? Do they compare the columns with their real template? |
| Follow-up | "Which columns does your solution provider need that you do not see here? Can you show me your template?" |

### 5. First visit and privacy (website and sign in)

> "Imagine a colleague sent you this website. Find out what it does, then upload
> one of your own SDS files."

Start: signed out, on the website.

| | |
|---|---|
| Tests | Landing page clarity, progressive sign in, and trust in data privacy. |
| Success | Explains the product in their own words, clicks Upload documents, signs in, and reaches the upload screen. |
| Watch for | Do they understand "sample workspace" vs their own account? Do they hesitate to upload because of privacy? Do they find the demo account? |
| Follow-up | "Who at your factory would need to approve before you upload real supplier files here?" |

## What to record per person

| # | Completed without help? (Y / N) | Time (min:sec) | Errors or wrong clicks | Exact quote worth keeping | Ease 1 to 5 (their rating) |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

At the end, ask: **"If this worked with your real files, would you use it next
month? What would stop you?"** Write their answer word for word.

## How to decide what to change

- A task that **2 or more people fail** is a design problem. Fix it before Phase 8.
- A task everyone completes but rates 1 or 2 is too slow. Look at the clicks.
- One person's opinion ("I prefer blue") is a note, not a change.
- Anything that shows people **do not trust** the data (tasks 1 and 2) matters
  most: the PRD's core bet (H4) is that clean, trusted data is the hard part.

Write the results in `docs/design/usability-results.md` after each round, with
the date and the version of the prototype tested.
