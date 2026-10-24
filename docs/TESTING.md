# Testing record (authoring sandbox, 24 Oct 2026)

Environment: Python 3.12, Tesseract 5.3.4, Pillow 12.1.1, pypdfium2 5.6.0. **No network** → FastAPI, SQLAlchemy,
pytest, httpx, Vite and `@types/react` were not installed.

## Executed

| Command (from `backend/`) | Result |
|---|---|
| `python -W ignore -m unittest discover -s tests -p "test_core_*.py" -v` | **Ran 66 tests, OK, 0 skipped (~12 s)** |
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

## Written but NOT executed

* `backend/tests/test_api.py` (pytest): health, case creation/validation, invalid/oversized uploads, successful upload and random storage names,
  document isolation between cases, missing documents, amount mismatch with evidence, formatting differences, currency
  mismatch, unreadable values, date order, manual correction + re-analysis, status changes + audit events, deletion
  rules, report contents, dashboard metrics, search/pagination, checklist edits, demo-endpoint protections, demo
  seed/reset only touching demo cases, demo scenarios via the API.
* The whole FastAPI/SQLAlchemy layer and the React frontend (see README §1).

Run locally: `pip install -r requirements-dev.txt && pytest -q` and `npm install && npm run build`.
