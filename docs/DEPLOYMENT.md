# Deploying FDR EvidenceLens (keeps the existing Vercel frontend link)

**Status: written, not executed.** Nothing here could be tested from the authoring sandbox (no network, no Docker).
The cause of the first failed deployment was verified from your Vercel log; the fix below follows from it.

## Why the Vercel backend failed

The log said `sqlite3.OperationalError: attempt to write a readonly database` on `INSERT INTO audit_events` during
login. Vercel serverless functions have a **read-only filesystem** (only temporary, per-instance `/tmp`). This app keeps
a SQLite file and uploaded documents on disk and runs the **Tesseract program** for OCR, so on Vercel:

| Needed by the app | On Vercel serverless |
|---|---|
| Writable database | No (read-only; `/tmp` is wiped and not shared between instances) → **login crashed (HTTP 500)** |
| Uploaded files kept between requests | No |
| Tesseract program for OCR | Cannot be installed |
| Background OCR after the response | Not reliable |

The browser showed "Cannot reach the backend" because the 500 reply carried no CORS headers (fixed in this update), not
because the server was down — opening the backend URL showed `{"error":…"Not Found"}`, which proves it was running.

## Target setup

```
Browser ──► https://fdr-evidence-lens.vercel.app   (frontend, UNCHANGED link from your PPT)
              │  /api/*  is forwarded by a Vercel rewrite
              ▼
        https://<name>.onrender.com   (backend in Docker: FastAPI + Tesseract)
              ▼
        Neon Postgres (data)            uploaded files on the backend's disk
```
Because `/api` goes through the same address as the site, the login cookie is **first-party** (a separate
`*.vercel.app` backend would be a different "site" and browsers would drop the cookie).

Free tiers change: check the current limits of Render and Neon. At the time of writing, free Render web services
**go to sleep when idle** (first request can take about a minute) and their disk is **wiped on every redeploy/restart**.

## Steps

### 1. Database (Neon)
1. Create a free project at neon.tech → copy the connection string (`postgresql://user:pass@host/db?sslmode=require`).
2. On your computer (backend folder, venv active), install the new dependency and create the tables + your user **in that database**:
   ```powershell
   cd "C:\Users\ELCOT\OneDrive\Documents 1\SIH\fdr-evidencelens\backend"
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   $env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
   python -m app.cli init-db
   python -m app.cli create-user --username reviewer      # choose a strong password; there is no default
   ```
   (`$env:DATABASE_URL` only lasts for that PowerShell window; your local `.env` is untouched.)

### 2. Backend (Render, Docker)
1. Push the updated project to GitHub (this update adds `backend/Dockerfile`).
2. Render → **New → Web Service** → connect the repo → **Root Directory: `backend`** → Language/Runtime: **Docker** → instance type: Free.
3. Environment variables:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 1 |
   | `APP_ENV` | `production` |
   | `ALLOW_DEMO_IN_PRODUCTION` | `true` (lets you click *Load demo cases* in Settings; remove later if you prefer) |
   | `CORS_ORIGINS` | `https://fdr-evidence-lens.vercel.app` |
   | `SESSION_HOURS` | `8` |

4. Health check path: `/api/health`. Deploy, then open `https://<name>.onrender.com/api/health` — you should see
   `"status":"ok"` and `"ocr_available":true`.

### 3. Frontend (existing Vercel project — keep its URL)
1. Edit `frontend/vercel.json`: replace `REPLACE-WITH-YOUR-BACKEND.onrender.com` with your Render host name. Commit and push.
2. Vercel → your frontend project → Settings → Environment Variables: set **`VITE_API_BASE_URL` = `/`** (a single slash;
   replace the old backend URL). Vite reads it at build time, so **redeploy** (Deployments → ⋯ → Redeploy).
3. Open https://fdr-evidence-lens.vercel.app → log in → Settings → **Load / reload demo cases** (~1 minute).

The old `fdr-evidence-lens-hzky` Vercel backend project can be left alone or deleted; nothing should point to it any more.

## Before the judges open it
* Open `https://<name>.onrender.com/api/health` a couple of minutes earlier to wake the free instance, and log in once.
  (A free uptime pinger hitting that URL every ~10 minutes also keeps it awake.)
* After any Render redeploy/restart, uploaded files vanish: click *Load demo cases* again.
* The site is on the **public internet** and the login is its only protection: use a strong password and **fictional documents only**.

## If it still fails
| Symptom | Likely cause / fix |
|---|---|
| Login → "Cannot reach the backend … starting up" | Free instance asleep: wait ~1 minute and retry; check the Render URL in `vercel.json` has no typo |
| Login page again right after logging in | `VITE_API_BASE_URL` still holds a full URL (must be `/`) or you did not redeploy the frontend |
| 404 on `/api/...` from the Vercel site | `vercel.json` missing from the frontend project's root directory, or not pushed |
| 500 on login, Render log mentions the database | Wrong `DATABASE_URL`, or step 1 (`init-db`) not run against Neon |
| "Incorrect username or password" | User not created in **Neon** (step 1); run `create-user` with `DATABASE_URL` set |
| Documents "Failed – Tesseract not found" | The service is not running from the Dockerfile (choose Runtime = Docker, Root Directory = backend) |
| Large PDF upload fails | Try a small PNG first; proxies in front of the backend may limit request size |

**Fallback if the rewrite does not pass the login cookie (untested):** set `VITE_API_BASE_URL` to the full Render URL,
add Render env `COOKIE_SAMESITE=none`, and keep `CORS_ORIGINS` as above. Browsers that block third-party cookies
(Safari, some Chrome settings) will still break this mode, which is why the rewrite is the primary approach.
