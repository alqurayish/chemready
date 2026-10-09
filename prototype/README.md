# ChemReady clickable prototype (P0)

One HTML file, no build step, no server. All data is fictional.

## Open it

Double click `index.html`, or run `python -m http.server 8000` in this folder and open
http://localhost:8000.

## Demo login

| Email | Password |
|---|---|
| `demo@chemready.app` | `demo1234` |

Or click **Try demo** on the website, or **Use demo account** in the sign in box.
Add `#demo` to the address to open the app already signed in.

## Demo path for interviews (about 5 minutes)

Show this only **after** the discovery questions (PRD: never pitch during the interview).

0. **Landing page**: read the headline together. Click **Try the demo** (signs in with the demo account).
1. **Inventory**: the end result. Point at the statuses: Verified vs Needs action.
2. **Review** → **Review** on *Demowet NF*: three doubtful fields come first.
   - Revision date: the AI quoted text that is not in the PDF, so the value was removed.
     Click **Edit** and enter 1 Mar 2025 from the page on the right.
   - H code `H3l9`: a bad scan. **Edit** to `H319`.
   - CAS `7732-18-6`: the check digit is wrong. Try saving it unchanged (it is refused), then `7732-18-5`.
   - **Approve product**. The next SDS (*Isopropanol 99%*) has nothing flagged: look over it, then approve.
3. **Inventory** → click a product: every value with page and quote.
4. **Needs action**: old SDS, missing CAS, missing sections, unreadable files.
5. **Settings** (needs sign in): change SDS maximum age to 2, then look at Needs action again.
6. **Inventory** → **Export CIL**: warnings and the sheet preview.
7. **Upload documents**: the sign in modal appears. Sign in with any email and an 8+ character
   password; you land straight on the upload screen. **Try a sample batch**, then watch **Review** process it.
8. Profile menu (top right) → **Profile** or **Sign out** (returns to the website).

Use **Reset demo** (top right) between interviews.

## Keyboard on the review screen

`A` approve · `E` edit · `M` not in SDS · `J` / `K` next / previous field
