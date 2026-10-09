# Backend (Phase 7)

FastAPI + SQLite. Start it with `uv run chemready serve` and open
http://127.0.0.1:8000/docs for the interactive API page (FastAPI makes it).

## Database

`src/chemready/app/db.py`. The six PRD tables plus `app_user` and `password_reset`.

| Table | Holds |
| --- | --- |
| `facility` | One row per factory, its settings (SDS max age, solution provider) |
| `app_user` | Accounts: Argon2 password hash, `session_version` for "sign out everywhere" |
| `sds_document` | Each upload: hash (stops duplicates), status, stage, model, tokens, latency |
| `field_value` | **The audit trail**: every value with page, quote, checks, reasons, confidence, review |
| `chemical_product` | One approved product per SDS, with who approved it and when |
| `ingredient`, `hazard` | Section 3 substances (CAS, check result) and section 2 H codes and pictograms |

## Document lifecycle

`queued → extracting (Reading pages → Finding sections → Extracting → Checking) → in_review → approved`,
or `failed` with a message the user can act on. A background worker handles one
document at a time (free-tier rate limits) and resumes unfinished work after a restart.

## Endpoints

| Method and path | What |
| --- | --- |
| `POST /api/auth/signup`, `/signin`, `/signout`, `/signout-all` | Accounts and sessions |
| `POST /api/auth/reset`, `/reset/confirm` | Password reset (link is logged until an email service is connected) |
| `GET /api/me` | Current user and facility |
| `GET/POST /api/documents` | List, upload (up to 50 PDFs, 20 MB each, `public_sds` flag) |
| `POST /api/documents/{id}/retry`, `DELETE /api/documents/{id}` | Retry a failed file, remove a file |
| `GET /api/documents/{id}/review`, `/pages/{n}` | Fields to review, page text for the source viewer |
| `POST /api/fields/{id}` | `approve`, `edit` (same format rules as the AI) or `missing` |
| `POST /api/documents/{id}/approve` | Refused while any field still needs review |
| `GET /api/inventory`, `/api/products/{id}` | Filter by `q`, `supplier`, `hazard`, `status` |
| `POST /api/products/{id}/reopen`, `PUT /api/products/{id}/note` | Re-review, note for the auditor |
| `GET /api/actions` | Old SDS, missing CAS, missing sections, unreadable files |
| `GET/PUT /api/settings` | Facility settings |
| `GET /api/export.xlsx` | CIL sheet + Flags sheet |

## Security

- Every query that reads facility data filters by the signed-in user's `facility_id`.
- Sessions: signed cookie (`HttpOnly`, `SameSite=Lax`, `Secure` in production), 12 hours.
- Five failed sign-ins for an email lock it for 15 minutes.
- Reset tokens: random, stored as SHA-256 hashes, single use, 30 minutes.
- Private uploads never go to a free AI tier (`PrivacyError`); the file is marked failed with the reason.
