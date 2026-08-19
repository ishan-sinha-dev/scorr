# SOCRR — SOC Report Reviewer

Evidence-linked control intelligence platform for SOC 1/SOC 2 report review.
Every AI conclusion must trace back to source evidence (document, page,
section) — see `docs/architecture/phase0-assessment.md` for the full
architecture assessment and phased delivery plan.

**Status:** Phase 2 (auth + organizations + audit periods) complete. No
document upload or AI code yet — those are Phase 3+.

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
2. In the SQL editor, run
   `database/migrations/0001_organizations_users_audit_periods.sql`.
3. Copy `.env.example` to `.env` and fill in the project's URL and anon
   key (Project Settings → API). Never commit `.env`.

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

`.env` is read by both apps: `apps/api` via `pydantic-settings`
(`apps/api/app/core/config.py`), `apps/web` via `NEXT_PUBLIC_*` vars read at
request time (`apps/web/lib/env.ts`). OpenAI key isn't required until
Phase 5.

## Validation

```bash
# web
cd apps/web && npm run build && npm run lint

# api
cd apps/api && source .venv/bin/activate && pytest -q && ruff check . && mypy app tests
```
