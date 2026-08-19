# SOCRR — SOC Report Reviewer

Evidence-linked control intelligence platform for SOC 1/SOC 2 report review.
Every AI conclusion must trace back to source evidence (document, page,
section) — see `docs/architecture/phase0-assessment.md` for the full
architecture assessment and phased delivery plan.

**Status:** Phase 3 (document upload and storage) complete. No document
extraction or AI code yet — those are Phase 4+.

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
2. In the SQL editor, run each migration in `database/migrations/` in
   order: `0001_organizations_users_audit_periods.sql`, then
   `0002_documents.sql`.
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
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000/health
```

### Redis (needed starting Phase 4, harmless to run now)

```bash
docker compose up redis
```

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
```

**`apps/web/.env.local`** (Next.js's convention for local, uncommitted env
vars — read via `apps/web/lib/env.ts`):
```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Both `.env` and `.env.local` are gitignored everywhere in this repo.
`OPENAI_API_KEY` (in `apps/api/.env`) isn't required until Phase 5.

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
