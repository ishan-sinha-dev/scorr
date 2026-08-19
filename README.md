# SOCRR — SOC Report Reviewer

Evidence-linked control intelligence platform for SOC 1/SOC 2 report review.
Every AI conclusion must trace back to source evidence (document, page,
section) — see `docs/architecture/phase0-assessment.md` for the full
architecture assessment and phased delivery plan.

**Status:** Phases 1–15 complete (foundation through review workflow,
export, risk scoring, period comparison, control-relationship evidence,
carry-forward, and packaging/CI). Code-complete and validated locally
(102/102 backend tests, ruff/mypy clean, `npm run build`/`lint` clean) —
see `docs/architecture/phase0-assessment.md` for the full per-phase
writeup, including documented scope decisions and known gaps for Phases
9–15.

## Structure

```
apps/web/   Next.js + TypeScript + Tailwind + shadcn/ui, Supabase Auth
apps/api/   FastAPI + Pydantic, verifies Supabase JWTs, enforces RLS-scoped access
database/   Migrations (run via Supabase CLI or the SQL editor)
docs/       Architecture assessment and decisions
```

All data reads/writes go through `apps/api`; `apps/web` only talks to
Supabase directly for auth (login/session). See
`docs/architecture/phase0-assessment.md` for why.

## One-time setup: Supabase project

1. Create a project at [supabase.com](https://supabase.com) (or use an
   existing one).
2. In the SQL editor, run each migration in `database/migrations/` **in
   numeric order, 0001 through 0012** — each file is named for its
   number so `ls database/migrations/` already gives you the right
   sequence. Two are worth calling out: `0006_control_mapping.sql`
   enables the `pgvector` extension itself (available on all Supabase
   projects by default, no separate step needed), and
   `0008_documents_update_policy.sql` fixes a real bug found during live
   testing (see below). `0011_finding_reviews.sql` and
   `0012_findings_risk_level.sql` are Phase 9/11 — required for the
   review workflow and risk badges in the UI to work.
3. Get the project's URL, anon key, and service-role key (Project Settings
   → API), and set up each app's own env file — see Configuration below.
   `.env.example` at the repo root is a reference template only; each app
   loads its env from its own directory, not from the repo root.

## Running locally

### Web

```bash
cd apps/web
npm install
npm run dev       # http://localhost:3000
```

### API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate   # .venv\Scripts\Activate.ps1 on Windows PowerShell (not .venv\Scripts\activate — that's the cmd.exe/batch script and does not affect PowerShell's current session)
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000/health
```

### Redis + Celery worker (needed from Phase 4 on — document extraction,
AI analysis, internal control parsing, and control mapping all run as
background tasks)

```bash
docker compose up -d redis   # needs Docker Desktop; -d runs it in the background
```

```bash
cd apps/api
source .venv/bin/activate   # .venv\Scripts\Activate.ps1 on Windows PowerShell (not .venv\Scripts\activate — that's the cmd.exe/batch script and does not affect PowerShell's current session)
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

`--pool=solo` is required on native Windows — Celery's default worker
pool uses `os.fork()`, which doesn't exist there; `solo` (single-threaded)
is the standard workaround for local dev. Drop the flag on Linux/macOS if
you want the default concurrent pool instead.

Run the worker alongside `uvicorn`, in its own terminal, and leave both
running — without the worker, uploads/analyze/parse/map requests will
queue a task that never gets picked up (the API request still returns
normally; the document just stays in `pending`/no results appear).

**Bug found and fixed during live testing:** `documents` (migration 0002)
shipped with select/insert/delete RLS policies but no update policy.
Phase 4 (0003) then added `extraction_status`/`extraction_error` and a
code path that updates them on every upload and by the extraction worker.
Without an update policy, Postgrest's UPDATE silently matched zero rows —
no exception, 200 OK either way — so the status column stayed `NULL`
forever and the UI showed no extraction badge at all, even though the
worker logged "succeeded." Fixed by `0008_documents_update_policy.sql`.
If you ran migrations before this fix, apply `0008` now — no need to redo
anything else.

## Configuration

The repo-root `.env.example` is a reference for what variables exist — it
is not read directly. Each app looks for its env file in its own
directory (this is how `pydantic-settings` and Next.js resolve env files:
relative to the process's working directory / the app's own root, not the
monorepo root), so create two files:

**`apps/api/.env`** (read via `pydantic-settings`,
`apps/api/app/core/config.py`):
```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_ROLE_KEY=<service role key>
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=<openai api key>
```

**`apps/web/.env.local`** (Next.js's convention for local, uncommitted env
vars — read via `apps/web/lib/env.ts`):
```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Both `.env` and `.env.local` are gitignored everywhere in this repo.
`OPENAI_API_KEY` goes in `apps/api/.env`, alongside the Supabase keys
above — required from Phase 5 on (AI extraction, internal control AI
fallback, and control mapping all call it; Phases 1–4 don't need it).

By default, Supabase requires a user to confirm their email before they
can sign in — after signing up at `/login` for the first time, check the
inbox for that address (or, for faster local testing, turn off "Confirm
email" under Authentication → Providers → Email in the Supabase
dashboard).

## Validation

```bash
# web
cd apps/web && npm run build && npm run lint

# api
cd apps/api && source .venv/bin/activate && pytest -q && ruff check . && mypy app tests
```

## Docker (apps/api)

`apps/api/Dockerfile` builds a single image used two ways — same
dependencies, same code, no second Dockerfile:

```bash
cd apps/api
docker build -t socrr-api .
docker run --env-file .env -p 8000:8000 socrr-api                 # FastAPI (default CMD)
docker run --env-file .env socrr-api celery -A app.workers.celery_app worker --loglevel=info   # worker
```

CI (`.github/workflows/ci.yml`) runs lint/typecheck/test for both apps on
every push/PR — it does not build or push the Docker image. Known
packaging gaps, not built (see `docs/architecture/phase0-assessment.md`
for the full list): no rate limiting, no secret rotation, no malware
scanning on uploads, no OCR for scanned/image-only PDF pages.
