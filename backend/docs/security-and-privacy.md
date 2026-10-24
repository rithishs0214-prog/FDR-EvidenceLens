# Security and privacy notes

**Status:** local prototype with a basic username/password login. Not production-ready. Use synthetic data.

## Implemented (in code; API-level controls are unexecuted — see README §1)
* Upload validation: extension + declared MIME + magic bytes + size limit (streamed, rejected above the limit) + PDF page limit + image pixel limit. (core part tested)
* Server-generated random storage names; user filenames are sanitised and used for display only; path resolved and checked to stay inside the upload folder.
* Uploads stored outside the frontend; retrieval only via `/api/cases/{case}/documents/{doc}/file`, which looks the document up by *both* IDs (404 otherwise); `nosniff` and `no-store` headers.
* Explicit CORS origins (no wildcard, no credentials); backend binds to 127.0.0.1 in the documented command.
* ORM parameterised queries; no shell execution (Tesseract is invoked through `pytesseract`).
* OCR text, field values and identifiers are not written to application logs; errors returned to clients carry no stack traces.
* `.gitignore` excludes `.env`, database, uploads; `.env.example` has no secrets.

* Login: PBKDF2-SHA256 (600k iterations, per-user salt) password hashes; constant-work verification for unknown users; generic error message; server-side sessions (only a token hash stored) in an `HttpOnly` `SameSite=Lax` cookie (`Secure` outside development); app-wide deny-by-default dependency (all routes except `/api/health` and `/api/auth/login|logout`); login throttling; login/logout/failed-login audit events that never store the typed username or password. (hash/token/limiter logic tested; endpoints unexecuted)

## Known gaps
* **Authorisation is all-or-nothing.** There are no roles: any logged-in user can read, change and delete every case, and the audit trail.
* No MFA, password reset, account management UI, session list/revocation UI or HTTPS; login throttling is in memory and per process.
* CSRF protection relies on `SameSite=Lax` plus CORS restrictions (no CSRF tokens).
* Field corrections store previous/new values in the audit table (database access = access to those values).
* No encryption at rest, no malware scanning, no rate limiting, no HTTPS, no retention/deletion policy.
* Audit events are rows in SQLite; they can be altered by anyone with file access.
* Dependencies were pinned from knowledge, not audited here; run `pip audit` / `npm audit` before use.

## Needed before real-world use
Roles, MFA, password reset, HTTPS (and secure cookies behind it), tamper-evident per-user audit, encryption at rest, retention policy and deletion tooling,
upload malware scanning, task queue, migrations, production database, monitoring, security testing and a data-protection
assessment with the process owner.
