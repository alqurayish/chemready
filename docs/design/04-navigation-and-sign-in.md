# Phase 1, Step 4b: Navigation, public landing and sign in

Refinement after the first prototype review. Updates `01`, `02` and `03`;
where they differ, this file wins.

## Decisions

| Decision | Why |
|---|---|
| Public landing page; sign in only when needed (progressive sign in) | Visitors can understand and try the product before creating an account. |
| A public **sample workspace** with fictional data | Exploring must never show a real factory's data. The sample runs in the browser and nothing is saved. |
| **Upload** and **Settings** need an account | Anything that touches your own files or facility needs to know who you are and which facility you belong to. |
| Real Inventory, Review, Needs action and documents are private to the facility | Enforced on the server in Phase 7, never only in the browser. |
| Navigation keeps **Review** (the review queue) | Review is the core of the product (R4). It was in the original screen list as "Documents". |
| One sign in form with two fields, sign up with four | Fewer fields means less friction. Facility name is needed to create the workspace. |

## Navigation

Order follows the job: Upload documents → Review → Inventory → Needs action → Settings.

| Width | Pattern |
|---|---|
| 1024 px and wider | macOS style sidebar: icon + label + count, account at the bottom |
| 641 to 1023 px | Icon rail with short labels and badge counts |
| 640 px and narrower | Bottom tab bar (like iOS), account button in the top bar |

Active item: white raised background with the primary colour on desktop; primary
colour on the rail and tab bar. Counts in amber mean "work is waiting".

## User journey

```
Landing page ─┬─ Explore with sample data ──► Sample workspace (no account)
              │                                   │ Upload / Settings
              │                                   ▼
              └─ Upload documents ──► Sign in modal ──► Upload screen (same intent)
                                        │  Create account / Forgot password
                                        ▼
                Upload → Review (flagged fields first) → Inventory → Needs action → Export
```

After sign in, the user lands exactly where they were going (the "intent").
Signing out returns to the landing page.

## Sign in modal copy

| Mode | Title | Fields | Main button |
|---|---|---|---|
| From Upload | "Sign in to upload documents" | Work email, Password | Sign in |
| Create account | "Create your account" | Full name, Work email, Facility name, Password | Create account |
| Forgot password | "Reset your password" | Work email | Send reset link |
| Reset sent | "Check your email" | — | Back to sign in |

Error copy: "Enter a valid email address, for example name@factory.com." ·
"Use at least 8 characters." · "Enter your facility name."

The reset message is the same whether or not the account exists ("If an account
exists for …"), so nobody can use the form to find out who has an account.

## Security requirements for Phase 7 (backend)

The prototype only simulates sign in. The real system must:

1. Check access on the **server** for every request: a user sees only their own
   facility's documents, products and flags.
2. Store passwords only as slow hashes (for example Argon2id or bcrypt), never as
   plain text.
3. Keep the session in a secure, HttpOnly, SameSite cookie, with an expiry and
   sign out that ends the session on the server.
4. Make reset links single use and short lived.
5. Limit repeated sign in attempts.

Library and setting choices are made in Phase 7 and recorded in DECISIONS.md.

## Open question for interviews

Should any factory be able to sign up on its own, or should pilots be invited?
Invite only is simpler and safer for the first 2 pilots; open sign up can follow.
