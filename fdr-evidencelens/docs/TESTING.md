# Testing record (authoring sandbox, 24 Oct 2026)

Environment: Python 3.12, Tesseract 5.3.4, Pillow 12.1.1, pypdfium2 5.6.0. **No network** → FastAPI, SQLAlchemy,
pytest, httpx, Vite and `@types/react` were not installed.

## Executed

| Command (from `backend/`) | Result |
|---|---|
| `python -W ignore -m unittest discover -s tests -p "test_core_*.py" -v` | **Ran 77 tests, OK, 0 skipped (~13 s)** (66 original + 11 login/auth-helper tests) |
| `python3 -m py_compile` on every file in `app/` and `tests/` (incl. `test_api.py`) | all compile |
| Custom AST check (undefined names / bad internal imports) over `app/` | clean (one false positive: `__file__`) |
| `tsc -p .` over `frontend/src` against hand-written stubs for React/React Router, TypeScript 6.0.3 | exit 0 — weak check, **not** `npm run build` |
| Mutation checks on the verification engine (broke the amount rule; forced text conflicts to "issue") | the first was caught by 4 tests; the second **initially survived**, revealing a test gap; 3 tests were added and now catch it |

What the 66 tests cover: normalisation/parsing; label-based extraction (incl. never guessing damaged amounts, ambiguous
dates, conflicting values on one document); every verification rule listed in the brief (missing documents/fields,
FDR-number/amount/currency/bank/beneficiary/date conflicts, formatting-only differences not flagged, currency handling,
unreadable/uncertain values, invalid date order, maturity, duplicates, failed OCR, user-confirmed values becoming
trusted, no "verified/genuine" wording); upload validation (type, MIME, magic bytes, size, page and pixel limits,
corrupt files, filename sanitising); **real Tesseract OCR** on generated fictional PNG and multi-page PDF documents
(with page numbers and confidence), a degraded scan never producing a *trusted wrong* value, missing-Tesseract
handling; and the four demo scenarios A–D through real OCR → extraction → engine.

## Login feature (added later) — what was verified

* `core/auth.py` (PBKDF2 hashing, salts, malformed hashes, password policy, username rules, token hashing, login throttle with a fake clock): 11 unit tests, run.
* **Login page** (`Login.tsx` + `login.css`, plus the real `auth.tsx` and `api.ts`) bundled with esbuild and driven in headless Chromium against a *mocked* backend: 21 checks — no horizontal overflow at 1440/1000/390 px, animations actually move (floating card, scan line, striped panel), empty/wrong/right password flows, password cleared after failure, Show/Hide, Enter key submits, autofocus, cookies requested (`credentials: "include"`) on every call, successful login routes to `/`, `prefers-reduced-motion` disables animation without hiding content, no console errors. Screenshots were reviewed; two layout bugs found that way (global `main { max-width }` leaking in; clipped badge) and fixed.
* Not covered: the real backend endpoints, cookie behaviour across ports in a real browser, route protection of the full app (see below).

## Written but NOT executed

* `backend/tests/test_api.py` (pytest): health, case creation/validation, invalid/oversized uploads, successful upload and random storage names,
  document isolation between cases, missing documents, amount mismatch with evidence, formatting differences, currency
  mismatch, unreadable values, date order, manual correction + re-analysis, status changes + audit events, deletion
  rules, report contents, dashboard metrics, search/pagination, checklist edits, demo-endpoint protections, demo
  seed/reset only touching demo cases, demo scenarios via the API.
* The `test_api.py` authentication tests (all routes except health/login return 401 when logged out, login/logout/me flow, generic error for wrong credentials, inactive users, lockout after 5 failures, expired sessions, no plain-text passwords or tokens in the DB, audit without secrets) and the fixture change that logs in before every other API test.
* The whole FastAPI/SQLAlchemy layer and the React frontend wired to the real backend (see README §1).

Run locally: `pip install -r requirements-dev.txt && pytest -q` and `npm install && npm run build`.
