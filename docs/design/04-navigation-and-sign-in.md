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

Order follows the job, with short labels: Upload → Review → Inventory → Actions → Settings.

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

## Refinement 2: glass and demo login

- Website uses a light glass effect: a floating frosted top bar, frosted cards and
  a soft colour wash behind. The top bar stays 86% opaque so text is readable even
  where the browser cannot blur.
- The app stays solid for dense data; glass only on the phone tab bar, the phone
  top bar and behind dialogs.
- Demo account `demo@chemready.app` / `demo1234`, one click from the website and
  the sign in box. `#demo` in the address opens the signed in app.

## Refinement 3: top navigation, profile and branding

**The left sidebar is removed.** The app uses one horizontal glass top bar:

```
[◇ ChemReady  Prototype]  Upload  Review 2  Inventory  Actions 8  Settings      ● Local model  (RA) Rahima Akter ▾
```

| Width | Navigation |
|---|---|
| 1024 px and wider | Icons and labels, user name on the right |
| 768 to 1023 px | Labels only, avatar only |
| 767 px and narrower | Menu button opens a list of all pages, profile and sign out |

- Active page: white raised pill with primary text. Amber counts mean work is waiting.
- Profile menu (avatar, right): name and email, Profile, Settings, Sign out.
- New **Profile** page (needs an account): name and role, workspace, change
  password, sign out of all devices, sign out.

**Branding**, each shown once in the right place:

| Where | Text |
|---|---|
| Logo tag (website and app) | ChemReady · Prototype |
| Website hero label | A D-SAi Product |
| Website About section | Designed and built by Md. Alqurayish Sharkar, AI Product Engineer |
| Footers and profile menu | ChemReady Prototype · A D-SAi Product · © 2026 D-SAi |

## Refinement 4: compact pill navigation and glass cards

- The top bar is no longer full width. It is a compact floating glass pill,
  centred, as wide as its content: logo, five pages, then the profile.
- Every card is glass: 58% white, 20 px blur, a white top highlight and a soft
  blue shadow, over a gentle colour wash.
- Muted text darkened from #64748B to #58677D so it stays above 4.5:1 on glass.

## Refinement 5: plain white background

The page background is plain white everywhere (website and app). The colour
wash is removed. Cards keep their glass treatment (translucent white, blur,
white top highlight, soft shadow); on white they read as soft, raised white
cards.
