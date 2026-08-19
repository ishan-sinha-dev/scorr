# Phase 0 — Assessment & Architecture

## Recon findings

The repo (`C:\Users\IshanSinha\socr` on the user's machine) was completely
empty at the start: no code, no package manifests, no Docker, no Supabase
config. This is a greenfield build — Phase 1 started from nothing, no
existing decisions to reconcile with.

## Confirmed decisions

- **Supabase: hosted project**, not the local Supabase CLI stack. Local
  `docker-compose.yml` only runs what hosted Supabase doesn't provide
  (Redis, from Phase 4). The app connects to the hosted project via env
  vars once one exists.
- **Credentials**: `.env.example` ships placeholders only; no real keys
  committed anywhere at any point.

## Architecture

- **Monorepo**: `apps/web` (Next.js + TypeScript + Tailwind + shadcn/ui),
  `apps/api` (FastAPI + Pydantic, SQLAlchemy from Phase 2 once there's a
  schema to map).
- **Database**: Supabase Postgres + pgvector (from Phase 4, when embeddings
  exist). Tenant isolation via Postgres RLS — every tenant-owned table
  carries `organization_id` and a policy, enforced at the DB layer, not
  only in application code.
- **Auth**: Supabase Auth.
- **Storage**: Supabase Storage, signed URLs for document access.
- **AI**: OpenAI, structured outputs only, staged pipeline (classification →
  structured extraction → control/CUEC/exception identification → semantic
  retrieval → control mapping → evidence verification → risk calculation).
  Model names centralized in one settings module, never hardcoded inline.
  Cheaper models for classification/simple extraction, stronger models
  reserved for ambiguous mapping and reviewer-facing explanations.
- **Background jobs**: Celery + Redis for document processing (Phase 4+).
- **Export**: openpyxl (Excel) / ReportLab (PDF), Phase 10.
- **DevOps**: Docker Compose for local services; GitHub Actions added once
  there's a build/test to gate.

The full folder tree from the original spec is not created up front —
directories like `apps/api/app/workers`, `apps/api/app/ai`,
`apps/api/app/documents` get created in the phase that introduces them
(4/5), not now. Same for tables: `organizations`/`audit_periods` in Phase 2,
`documents` in Phase 3, `internal_controls`/`soc_controls`/`control_mappings`
in Phases 6–7, etc. — designed around implemented workflows, not
speculatively created.

## Phase 1 — what was built (complete)

- `apps/web`: Next.js 16 (App Router, TypeScript strict, Tailwind v4),
  shadcn/ui base config (`components.json`, `lib/utils.ts`, CSS variables)
  added by hand — the `shadcn` CLI's `init` command requires reaching
  `ui.shadcn.com`, which this build sandbox's network allowlist blocks.
  The written files are the same standard shadcn/ui boilerplate the CLI
  would generate; only the fetch step was skipped. Deferred: actually
  installing shadcn components (`npx shadcn add <component>`) needs that
  same network access — do this from a machine that can reach
  `ui.shadcn.com`, e.g. the user's own machine, once the first real UI
  phase needs components.
  Also **not** using `next/font/google` (Geist): it requires a build-time
  fetch to `fonts.googleapis.com`, which the same sandbox network blocks —
  and plausibly some of this product's enterprise customers' networks
  would block too. Using the system font stack instead removes that
  build-time network dependency entirely; this is a permanent choice, not
  a temporary workaround.
- `apps/api`: FastAPI app, `app/core/config.py` (Pydantic `BaseSettings`,
  the single place env vars are read), `GET /health` and `GET /` routes,
  ruff + mypy (strict) + pytest configured in `pyproject.toml`, one smoke
  test.
- Root: `README.md`, `CLAUDE.md`, `.env.example`, `.gitignore`,
  `docker-compose.yml` (Redis only), `database/migrations/README.md`.

**Verified**: `apps/web` builds (`npm run build`) and lints clean
(`npm run lint`); `apps/api` boots, `/health` and `/` both respond, and
`pytest`/`ruff check`/`mypy` all pass clean.

**Known limitation**: shadcn UI components themselves aren't installed yet
(only the base config) — see above. Not a blocker for Phase 1, since Phase
1 has no UI beyond a static landing page.

## Phase 2 — what was built (complete)

Auth, organizations, and audit periods — the first real DB schema, first
real API surface, first real UI.

- `database/migrations/0001_organizations_users_audit_periods.sql`:
  `organizations`, `organization_members` (owner/member roles),
  `audit_periods` (with a `period_end > period_start` check constraint),
  `audit_log`. RLS enabled on every table; a `create_organization()` RPC
  (SECURITY DEFINER) inserts the org and the creator's owner membership
  atomically.
  **Verified against a real Postgres engine**, not just syntax-checked: a
  local Postgres instance was stood up in the build sandbox with a minimal
  stand-in for Supabase's `auth` schema, the migration applied cleanly, and
  RLS was exercised end-to-end as two simulated users — org creation,
  cross-tenant read isolation, cross-tenant write rejection (including a
  direct attempt using a known org ID, not just an invisible one), and the
  date-order check constraint all behaved as designed. This was manual
  validation during development, not an automated test — no live Supabase
  project exists yet to point real integration tests at.
- `apps/api`: `app/core/security.py` (JWT verification via Supabase's JWKS
  endpoint — assumption: targets the current default of asymmetric signing
  keys; revisit this one file if the eventual project uses legacy HS256),
  `app/core/supabase.py` (per-request Supabase client scoped to the
  caller's own access token, so Postgres RLS — not a service-role
  bypass — is what actually enforces tenant isolation), `schemas/`,
  `repositories/`, `services/` (including a best-effort `audit_log`
  service used by both mutation endpoints), `POST/GET /organizations`,
  `POST/GET /organizations/{id}/audit-periods`. 14 tests: JWT verification
  against a local test keypair, Pydantic date-order validation, and
  route-level tests with the Supabase client dependency mocked.
- `apps/web`: `@supabase/ssr` wired for cookie-based auth (`lib/supabase/`,
  `proxy.ts` for session refresh — Next.js 16 renamed `middleware.ts` to
  `proxy.ts`; migrated during this phase, not left on the deprecated name),
  `/login` (sign in/up via Server Actions), a protected `(app)` route group
  that redirects to `/login` without a session, `/organizations` and
  `/organizations/[orgId]` (list/create, via Server Actions calling
  `apps/api` — never Supabase directly for data, only for auth; see the
  data-access decision above).
- All writes go through `apps/api`; `apps/web` never talks to Supabase
  for data, only for auth (login/session).

**Verified**: `apps/api` — 14/14 tests, ruff, mypy strict all clean.
`apps/web` — `npm run build` and `npm run lint` both clean.

**Known limitations** (documented, not silently skipped):
- No live Supabase project yet, so the signup → login → create-org →
  create-audit-period flow hasn't been exercised end-to-end through the
  actual running apps — only the migration's SQL/RLS logic (via the local
  Postgres check above) and each app's own code (via its own test suite)
  have been verified in isolation. This closes once the user provides a
  real Supabase project's URL/keys.
- `create_organization()`'s PostgREST RPC response shape (single object vs.
  one-element array) is handled defensively in
  `app/repositories/organizations.py` but unverified against real
  PostgREST — flagged in that file's docstring.
- No invite-another-user-to-an-org flow yet (no first org existed to
  design it against) — natural next addition once Phase 2 is exercised
  for real.

## Phase roadmap (for visibility — not scoped until each one starts)

1. ~~Project foundation~~ (Phase 1, complete)
2. ~~Auth + organizations + audit periods~~ (Phase 2, complete)
3. Document upload and storage
4. Document extraction pipeline
5. AI control/CUEC/exception extraction
6. Internal control framework
7. Control mapping engine
8. Evidence-linked findings
9. Human review
10. Excel/PDF export
11. Risk engine
12. SOC report comparison
13. Control intelligence graph
14. Continuous control memory
15. Security hardening and production readiness
