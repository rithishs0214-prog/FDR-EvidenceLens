# FDR EvidenceLens

Explainable **Fixed Deposit Receipt (FDR) document review assistant** — a Smart India Hackathon 2026 prototype.

It extracts fields from uploaded FDR-related documents (OCR), checks them against a configurable checklist, shows
**conflicting values side by side with the evidence behind each finding**, suggests next checks, records a human
review, keeps an application-level history, and prints a case report.

> **What it is not.** Decision-support software only. It is **not** an official AICTE system. It does **not** contact
> any bank, AICTE or government system, does **not** authenticate an FDR, and **never** approves or rejects a refund
> or releases money. "Review Completed" only records that a person finished the review step *inside this prototype*.
> The seeded checklist is a **demonstration checklist**, not an official requirement list.
> Local demo with a **basic username/password login** (no roles, no MFA, no password reset). Bind to localhost and
> use synthetic data only.

---

## 1. Verification status (read this first)

This project was built in a sandbox **without network access**, so not everything could be executed there.

| Component | Status |
|---|---|
| Verification engine, field extraction, normalisation, file validation, OCR wrapper, demo scenarios (`backend/app/core`) | **Run and tested** here with Python's `unittest` and a real Tesseract 5.3.4 (see §9) |
| FastAPI routers, SQLAlchemy models, services, demo seeder, CLI (`backend/app` outside `core`) | **Written, syntax- and name-checked only. Never executed.** FastAPI/SQLAlchemy could not be installed |
| API/database tests (`backend/tests/test_api.py`, pytest) | **Written, never executed** |
| Login: password hashing, session tokens, login throttling (`core/auth.py`) | **Run and tested** (11 unit tests) |
| Login page (`Login.tsx`, `login.css`) | **Rendered and tested in a real headless Chromium** at desktop/tablet/mobile with a mocked backend (21 checks, screenshots reviewed) |
| Login endpoints, cookie handling, route protection, `test_api.py` auth tests | **Written, never executed** (needs FastAPI) |
| Rest of the React/TypeScript/Vite frontend | **Never installed, built or opened in a browser against the real backend.** Only type-checked against hand-written stubs for React/React Router (no errors), which is much weaker than `npm run build` |
| End-to-end workflow (create case → upload → analyse → review → print) | **Not tested** |

Treat the unexecuted parts as a first draft that probably needs small fixes when you first run them. Please run the
commands in §5 and §8 and send back any errors. Do not describe the whole application as tested until you have done so.

---

## 2. Prerequisites

* **Python 3.11 or newer** (3.12 was used for the tested core)
* **Node.js 20 LTS or newer** with npm
* **Tesseract OCR program** (see §3). Installing the `pytesseract` Python package does **not** install Tesseract —
  `pytesseract` is only a thin wrapper that runs the separate `tesseract` program.
* PDF pages are rendered with the `pypdfium2` pip package (no separate Poppler install needed).

## 3. Install Tesseract

**Windows:** install the build from UB Mannheim (<https://github.com/UB-Mannheim/tesseract/wiki>), or in PowerShell
`winget install UB-Mannheim.TesseractOCR`. Then either add `C:\Program Files\Tesseract-OCR` to `PATH`, or set
`TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `.env`. Check with `tesseract --version`.
**macOS:** `brew install tesseract`. **Ubuntu/Debian:** `sudo apt install tesseract-ocr`.

The app starts without Tesseract; uploads then show "OCR is not available" and you can enter every field manually.

## 4. Configure

```powershell
copy .env.example .env      # macOS/Linux: cp .env.example .env
```
Edit `.env` if needed (upload limit, Tesseract path, demo switch). Never commit `.env`. Frontend API address:
`frontend\.env.example` → `frontend\.env` (`VITE_API_BASE_URL`, default `http://127.0.0.1:8000`).

## 5. Install and run (Windows PowerShell; two terminals)

**Terminal 1 — backend**
```powershell
cd fdr-evidencelens\backend
py -3 -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements-dev.txt
python -m app.cli init-db           # creates data\evidencelens.db and seeds the demo checklist
python -m app.cli create-user --username reviewer    # asks for a password (min. 10 chars); you log in with it
python -m app.cli seed-demo         # optional: four fictional demo cases (runs real OCR; ~30 s)
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```
**Terminal 2 — frontend**
```powershell
cd fdr-evidencelens\frontend
copy .env.example .env
npm install
npm run dev                          # http://127.0.0.1:5173
```
macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, the rest is identical (use `cp`).

* App: <http://127.0.0.1:5173> (you land on the **login page**; the dashboard opens after you log in) · API docs (OpenAPI/Swagger): <http://127.0.0.1:8000/docs> · Health: `/api/health`

## 5b. Login

* There is **no default account or password**. Create the first user with
  `python -m app.cli create-user --username reviewer` (password is typed hidden). Change it later with `set-password`.
* Every API route requires a login except `/api/health` and `/api/auth/login` (deny-by-default). Passwords are stored as
  PBKDF2-SHA256 hashes (600,000 iterations); the session cookie is `HttpOnly`, `SameSite=Lax` (and `Secure` outside
  development); only a hash of the session token is stored; sessions last `SESSION_HOURS` (default 8).
  5 failed logins for a username from one address lock that combination for 15 minutes (in memory; resets on restart).
* **Open the app and the API with the same host name** (both `127.0.0.1`, or both `localhost`). Mixing them makes the
  browser treat the cookie as third-party and the login will appear to "not stick".
* This is a basic login for a local prototype — not an identity system: no roles, no MFA, no password reset, no HTTPS.

## 6. Demo data

Four fictional scenarios, all marked **SYNTHETIC DEMO DATA** (every generated page says so):
A missing supporting document · B conflicting FDR amount (INR 1,000,000.00 vs 100,000.00) · C poor-quality scan needing
confirmation · D no discrepancies detected by the configured checks. They are created through the same upload, OCR and
verification code as real cases.

* Load / reload: Settings page → *Load demo cases*, or `python -m app.cli seed-demo`
* Reset: Settings page → *Reset demo cases*, or `python -m app.cli reset-demo`. **Only cases flagged as demo are
  deleted.** Demo endpoints work only when `APP_ENV=development` and `ENABLE_DEMO_ENDPOINTS=true` (otherwise HTTP 403).
* Scenario C depends on Tesseract's reading of a degraded image; results can differ slightly between Tesseract versions
  (it will always be flagged "needs confirmation" or "missing" rather than silently trusted).

## 7. How verification works

`backend/app/core/verification.py` (pure Python, no web/database imports). Every finding has a rule ID, a reason,
evidence (document, page, field, value, OCR confidence) and a suggested next check. Outcomes are only
**issue detected / needs confirmation / not checked / no issue detected by configured rules** — never "verified".

* Missing required documents and required fields (from the editable checklist)
* Conflicting FDR numbers, amounts, currencies, bank names, institution/beneficiary names, issue/maturity dates
* Maturity date after issue date; passed / approaching maturity (only for case types where enabled)
* Unreadable, low-confidence (< 80% by default) or unconfirmed values; failed OCR; duplicate files
* Formatting-only differences (case, spacing, punctuation, "Ltd" vs "Limited", `1,000,000` vs `10,00,000`) are not conflicts
* Amounts are only compared within the same currency; an amount with no currency is never compared
* A missing value is not a mismatch. A conflict involving an unconfirmed value is "needs confirmation", not an issue
* Ambiguous numeric dates (e.g. `05/06/2025`) are flagged instead of guessed; manual entry requires `YYYY-MM-DD`

## 8. Tests and builds

```powershell
cd backend
# Core logic only (incl. auth helpers) — needs just Python + Pillow + pytesseract + pypdfium2 (no FastAPI):
python -m unittest discover -s tests -p "test_core_*.py" -v
# Everything, incl. API/database tests (temporary DB + upload folder; touches no real data):
pytest -q
cd ..\frontend
npm run build                        # type-checks (tsc) then builds with Vite
```
Tests that need the Tesseract program skip themselves if it is not installed.

## 9. What was actually executed in the authoring sandbox

* `python -m unittest discover -s tests -p "test_core_*.py"` → see the final run recorded in `docs/TESTING.md`.
* Not run: `pytest` API tests, `npm install`, `npm run build`, the live app. See §1.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| "OCR is not available … Tesseract program was not found" | Install Tesseract (§3); set `TESSERACT_CMD` in `.env`; restart the backend |
| `ModuleNotFoundError: pytesseract` / `pypdfium2` | Activate the venv and run `pip install -r requirements-dev.txt` |
| Login says OK but you land on the login page again | Open the app and API with the same host (`127.0.0.1` in both `VITE_API_BASE_URL` and the browser address bar) so the cookie is sent |
| "Incorrect username or password" for a new install | No user exists yet: run `python -m app.cli create-user --username reviewer`. Forgot it: `python -m app.cli set-password --username reviewer` |
| "Too many failed attempts" | Wait 15 minutes or restart the backend |
| Everything fails with "Cannot reach the backend" | Start uvicorn; check `VITE_API_BASE_URL` and that `CORS_ORIGINS` contains the frontend origin |
| CORS error in the browser console | Open the app at exactly `http://localhost:5173` or `http://127.0.0.1:5173`, or edit `CORS_ORIGINS` |
| Upload rejected: "content does not match its extension" | The file isn't really a PDF/PNG/JPEG; re-export it |
| OCR finds nothing on a phone photo | Use a straight, well-lit, higher-resolution scan; otherwise enter fields manually |
| Wrong language characters | Install the Tesseract language pack and set `OCR_LANG` |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process Bypass` in that terminal |
| Database schema errors after pulling changes | This prototype has no migrations: stop the app, delete `backend/data/evidencelens.db`, run `python -m app.cli init-db` (this deletes all cases) |

## 11. Project layout

```
fdr-evidencelens/
  backend/app/core/      framework-free logic: verification, extraction, normalisation, OCR, file validation, scenarios
  backend/app/           FastAPI app (routers/), SQLAlchemy models, services, demo seeder, CLI
  backend/tests/         test_core_*.py (unittest, run) and test_api.py (pytest, not run)
  frontend/src/          React + TypeScript (pages/, components/)
  docs/                  manual E2E checklist, security notes, demo script, testing record
  .env.example  .gitignore  README.md
```

## 12. Current limitations

* Basic login only: no roles (every logged-in user sees every case), no MFA, no password reset or lockout notifications, no HTTPS. No encryption at rest.
* Audit history is application-level logging in SQLite — editable by anyone with database access; not tamper-proof.
* OCR is Tesseract only, English by default; handwriting, stamps, rotated or low-quality scans are unreliable.
  Extraction is label-based (`FDR No:`, `Principal Amount:` …) and expects one value per line.
* Rules are generic comparisons; real institutions' requirements are not modelled and the checklist is a demo.
* OCR runs in a FastAPI background task inside the web process (no queue); one process, SQLite, no migrations.
* No bank / AICTE / government integration, so nothing is authenticated.
* The UI has had no accessibility audit with assistive technology and no cross-browser testing.

## 13. Before any real-world use

Roles and fine-grained access control, MFA, password reset, HTTPS, per-user audit with tamper-evident storage, encryption at rest, a
retention/deletion policy, malware scanning of uploads, a real task queue, database migrations (Alembic) and a
production database, rate limiting, security review and penetration test, data-protection assessment, and
requirements confirmed with the actual process owners. See `docs/security-and-privacy.md`.

## 14. Future improvements

Authorised bank-verification integration (if ever permitted), configurable extraction templates per bank, side-by-side
document viewer with highlighted evidence, multi-language OCR, Alembic migrations, e-mail notifications for
"awaiting information", role-based review workflow.
