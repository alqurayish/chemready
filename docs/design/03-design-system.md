# Phase 1, Step 3: Design system (P0)

A small set of rules for colour, type, spacing and status, so every screen
looks and behaves the same.

- Tokens (source of truth): `tokens.css`
- Visual preview: open `design-system-preview.html` in a browser

## Principles

1. **Calm and dense.** A manager scans 150+ products. Neutral greys, one
   accent colour, compact tables. Colour appears only where it means something.
2. **Colour is never the only signal.** Every status has an icon and a word
   too, so it still works for colour blind users and on a black and white printout
   for an auditor.
3. **Status colours are reserved.** Green, amber and red mean data status and
   nothing else. Buttons and links are blue.
4. **Codes look like codes.** CAS numbers, H codes and quotes use a monospace
   font so digits line up and are easy to compare with the PDF.
5. **Accessible by default.** All text meets WCAG AA contrast (4.5:1); icons
   and form field edges meet 3:1.

## Colours

### Neutrals and actions

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--color-page` | #F8FAFC | App background | — |
| `--color-surface` | #FFFFFF | Cards, tables, dialogs | — |
| `--color-surface-subtle` | #F1F5F9 | Table header, hover rows | — |
| `--color-text` | #0F172A | Main text | 17.85:1 on white |
| `--color-text-secondary` | #475569 | Labels, column headers | 7.58:1 |
| `--color-text-muted` | #64748B | Help text, timestamps | 4.76:1 on white, 4.55:1 on page |
| `--color-border` | #E2E8F0 | Dividers (decorative) | — |
| `--color-border-input` | #8391A7 | Form fields, secondary buttons | 3.19:1 |
| `--color-primary` | #1D4ED8 | Primary buttons, links, selected row | white text 6.70:1 |
| `--color-primary-hover` | #1E40AF | Button hover | white text 8.72:1 |
| `--color-focus` | #2563EB | Keyboard focus ring | 5.17:1 |
| `--color-danger` | #B91C1C | Destructive buttons (Remove file) | 6.47:1 |

### Data status (reserved)

| Status | Text | Background | Icon colour | Icon | Text contrast |
|---|---|---|---|---|---|
| Verified | #166534 | #DCFCE7 | #16A34A | ✓ | 6.49:1 |
| Needs review | #92400E | #FEF3C7 | #D97706 | ! | 6.37:1 |
| Missing | #991B1B | #FEE2E2 | #DC2626 | ○ | 6.80:1 |
| Passed checks | #334155 | #F1F5F9 | — | • | 9.45:1 |

Icon colours on white: verified 3.30:1, needs review 3.19:1, missing 4.83:1
(all pass the 3:1 rule for icons).

**Product level statuses** reuse the same families:
- Inventory "Verified" (approved, no open flags) uses the verified style.
- Inventory "Needs action" (open flag) uses the needs review (amber) style,
  because it means "your attention is needed", not "something is wrong".
- Document "Failed" uses the missing (red) style.

**Why missing is red, not grey:** a missing CAS number or section is a real gap
an auditor will ask about. Grey would hide it.

### Source highlight

| Token | Hex | Use |
|---|---|---|
| `--color-highlight-bg` | #BFDBFE | Quote highlight in the PDF viewer (text on it 12.56:1) |
| `--color-highlight-border` | #1D4ED8 | Outline of the highlighted quote |

Blue on purpose: blue means "the field you selected" in the list, so the
selected field and its quote share one colour. Yellow would clash with amber
"Needs review".

### Signal words and pictograms

Signal words (Danger, Warning) and GHS pictograms are **hazard data, not our
status**, so they never use status colours:

- Signal word badge: uppercase. "DANGER" is white on dark (#0F172A); "WARNING"
  is dark text with a grey outline. Not classified shows "—".
- Pictograms: show the official GHS pictogram image with its code and name as
  text (for example "GHS05 Corrosion"). Do not redraw the symbols. Use the
  official images published by UNECE (the UN body that maintains GHS); check
  their licence page before shipping.

## Typography

**Font: system fonts** (Segoe UI on Windows, San Francisco on Mac, Roboto on
Android/Linux). Nothing to download, so pages load fast on slow factory
connections, and it costs nothing.

**Monospace** for CAS numbers, H codes, file hashes and source quotes:
`ui-monospace, Cascadia Mono, Consolas, …`.

| Token | Size | Weight | Use |
|---|---|---|---|
| `--text-xl` | 24 px | 600 | Big numbers on empty states |
| `--text-lg` | 20 px | 600 | Page title |
| `--text-md` | 16 px | 600 | Section and card titles |
| `--text-base` | 14 px | 400 / 500 | Body, buttons, form fields |
| `--text-sm` | 13 px | 400 | Table cells, help text, status pills |
| `--text-xs` | 12 px | 500 | Page numbers, timestamps, footers |

Line height 1.5 for body text, 1.25 for titles. Only three weights: 400, 500, 600.

Base size is 14 px, not 16 px, because the main screens are dense tables on a
1280 px laptop. Do not go below 12 px anywhere.

If a Bangla interface is ever needed, add `Noto Sans Bengali` to the font list.
The MVP is English only (PRD non goal).

## Spacing, shape and layout

**Spacing scale (4 px base):** 4, 8, 12, 16, 24, 32, 48 (`--space-1` to `--space-7`).
Use only these values.

| Where | Value |
|---|---|
| Inside buttons | 8 px × 16 px |
| Inside cards | 24 px |
| Between cards | 24 px |
| Page padding | 32 px |
| Table row height | 40 px |
| Table cell side padding | 12 px |

**Radius:** 4 px (badges), 6 px (buttons, inputs), 10 px (cards, dialogs),
full (status pills).
**Shadows:** cards use a hairline shadow; only dialogs and toasts use the
larger one.
**Layout:** sidebar 220 px; minimum app width 1280 px.

## Components (P0 set)

| Component | Variants | Notes |
|---|---|---|
| Button | primary, secondary, danger, disabled | One primary per page. Disabled buttons need a tooltip saying why. |
| Status pill | verified, needs review, missing, passed checks | Always icon + word. |
| Signal word badge | danger, warning | Hazard data, not status. |
| Code text | CAS, H code | Monospace. |
| Table | default, row hover, selected row | Sticky header; sortable columns show ▲▼. |
| Tabs with counts | — | "Needs review 12". |
| Search + filter dropdowns | — | "Clear filters" link when any filter is on. |
| Drop zone | idle, dragging, uploading | Dashed border, blue when dragging. |
| Progress bar | per file | Shows the stage name too, not only a bar. |
| Field row (review) | needs review, missing, passed | Value, page, reason, three actions. |
| PDF viewer | page, highlighted quote | Page controls and zoom. |
| Toast | success, error | Bottom right, disappears after 5 s (errors stay until closed). |
| Dialog | confirm, export | Focus trapped inside, Esc closes. |
| Empty state | — | One sentence + one button. |
| Skeleton | table, form | Grey bars while loading. |

## Interaction rules

- **Focus is always visible:** 2 px blue ring (`--color-focus`), offset 2 px.
  The review screen depends on the keyboard.
- **Click targets** at least 32 px high.
- **No animation** beyond 150 ms fades. No spinners longer than 1 second
  without text saying what is happening.
- **No dark mode** in P0. Factory office laptops, daytime use; it would double
  the testing work. Revisit if pilots ask.
