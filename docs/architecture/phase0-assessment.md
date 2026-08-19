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
- ~~No live Supabase project yet~~ — closed during Phase 3: the full
  signup → login → create-org → create-audit-period → upload-document
  flow has now been exercised end-to-end against a real Supabase project
  (see the Phase 3 section below).
- `create_organization()`'s PostgREST RPC response shape (single object vs.
  one-element array) is handled defensively in
  `app/repositories/organizations.py` but unverified against real
  PostgREST — flagged in that file's docstring.
- No invite-another-user-to-an-org flow yet (no first org existed to
  design it against) — natural next addition once Phase 2 is exercised
  for real.

## Phase 3 — what was built (complete)

Document upload and secure storage. Stops there deliberately — per the
pipeline in the Architecture section above, classification, extraction,
OCR, chunking, and embeddings are Phase 4/5, not this phase.

- `database/migrations/0002_documents.sql`: `documents` (`document_type`
  fixed to `soc_report` / `bridge_letter` / `internal_control_framework` —
  no AI classification yet, chosen by the uploader), RLS reusing
  `is_organization_member()`/`is_organization_owner()` from the Phase 2
  migration rather than reimplementing them. A private `documents` Storage
  bucket, with `storage.objects` policies that parse the organization ID
  back out of the object path (`{organization_id}/{audit_period_id}/{document_id}-{file_name}`)
  so table RLS and Storage access enforce the same tenant boundary from one
  definition of membership.
  **Table RLS verified against a real Postgres engine**, same methodology
  as Phase 2 (local Postgres, stubbed `auth` schema, two simulated tenant
  users in real transactions). **Storage bucket policies could not be
  verified the same way** during development — `storage.objects`/
  `storage.buckets` are Supabase Storage infrastructure, not part of plain
  Postgres — but have since been exercised live against the user's real
  Supabase project (upload and signed-URL "View" both confirmed working;
  see the post-delivery fix below for the one real bug that surfaced
  during that check).
- `apps/api`: `app/repositories/documents.py` (Storage upload +
  `documents` row insert — not one atomic transaction, since Storage and
  Postgres are separate systems; a failed insert after a successful upload
  orphans the Storage object, accepted for now since nothing lists Storage
  directly), `app/services/documents.py` (HTTP-agnostic, so it's reusable
  by a future background worker), `app/api/documents.py`
  (`POST/GET /organizations/{id}/audit-periods/{id}/documents`, multipart
  upload with content-type allowlist + size-cap validation before anything
  touches storage — PDF/DOCX/XLSX/CSV, 50MB default, both centralized in
  `Settings`). 6 new tests (upload success, unsupported content-type,
  empty file, oversized file, list, auth-required) plus a pre-existing
  Phase 2 test (`test_tampered_signature_is_rejected`) fixed for a genuine
  flaky-test bug found while running the suite: base64url's final
  character of a trailing partial byte group carries decoder-discarded
  padding bits, so the old last-character toggle had a ~1/4 chance of
  leaving the decoded signature unchanged. 20/20 tests now pass
  consistently (verified over repeated runs).
- `apps/web`: `/organizations/[orgId]/audit-periods/[auditPeriodId]`
  (document list with a "View" link per row using a short-lived signed
  URL, upload form for file + document type). Audit periods on the org
  page now link to this new page instead of being plain text. Uploads go
  through a Server Action that forwards the browser's `FormData` straight
  to `apps/api` — fixed a real bug found while wiring this up:
  `lib/api.ts`'s `apiFetch` unconditionally set
  `Content-Type: application/json` whenever a request body was present,
  which would have silently broken multipart uploads by overriding the
  boundary `fetch` sets automatically for `FormData` bodies.
- Malware scanning is explicitly **not implemented** this phase — no
  scanning service is chosen yet, and building a stub would be exactly the
  placeholder the project rules prohibit. Documented as a known gap.

**Verified**: `apps/api` — 20/20 tests, ruff, mypy strict all clean.
`apps/web` — `npm run build` and `npm run lint` both clean.

**Known limitations** (documented, not silently skipped):
- No `document_versions`/re-upload workflow — SOC reports and bridge
  letters are treated as static evidence uploaded once per audit period;
  deferred until a concrete versioning need shows up.
- No malware scanning (see above).

### Post-delivery fix: Storage requests were running as anon, not the caller

Found live against a real Supabase project, once uploads were finally
exercisable: every upload failed with a Storage `403 new row violates
row-level security policy`, even for a genuine org member.

Root cause, confirmed by reading the installed `supabase-py` SDK's own
source (not guessed): `get_user_client()` built the client with the anon
key, then called `client.postgrest.auth(access_token)` to scope it to the
caller. That call only patches the already-constructed `postgrest`
sub-client's headers. `client.storage` (and `client.functions`) are
built lazily, straight from `self.options.headers`, the first time
they're accessed — and `.postgrest.auth()` never touches that dict. So
every Storage request went out carrying only the anon key, Postgres saw
an anonymous caller for `auth.uid()` inside the Storage RLS policies, and
`is_organization_member()` correctly rejected it. Table reads/writes
never hit this, since `postgrest`'s own headers were patched directly —
only Storage (and, latently, `functions`, unused so far) was affected.

Fix: `get_user_client()` now passes the caller's token via
`ClientOptions(headers={"Authorization": f"Bearer {access_token}"})` at
`create_client()` time, so every sub-client — not just `postgrest` —
is built already scoped to the real caller. One mechanism for "who is
this client acting as," not two.

**Confirmed fixed live**: after the fix, upload succeeded and the
returned signed URL opened the document. This is the first time the full
stack — auth, org/audit-period creation, document upload, Storage RLS,
and the signed-URL view — has been exercised end-to-end as one running
system rather than piecewise (migration logic locally, each app via its
own test suite).

## Phase roadmap (for visibility — not scoped until each one starts)

1. ~~Project foundation~~ (Phase 1, complete)
2. ~~Auth + organizations + audit periods~~ (Phase 2, complete)
3. ~~Document upload and storage~~ (Phase 3, complete)
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
