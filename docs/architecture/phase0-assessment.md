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
- **Export**: openpyxl (Excel), Phase 10 — PDF export scoped out, see the
  Phase 10 writeup below.
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

## Phases 4–8 — what was built (complete, live-verified)

Built as one batch per the user's request, to avoid a manual browser
click-through after every single phase — but each phase still got its own
migration, its own test/build/lint/mypy gate, and its own local-Postgres
RLS validation before the next phase's code was written; only the
*user-facing* checkpoint was deferred to the end. That end-of-batch live
check (uploading a real report through the full pipeline against the
user's actual Supabase project) has not happened yet — see "What's left"
below.

**Phase 4 — document extraction pipeline.** `database/migrations/0003_document_pages_extraction.sql`
adds `documents.extraction_status`/`extraction_error` and a new
`document_pages` table (`pdfplumber` for PDF text, MIT-licensed —
PyMuPDF was ruled out as AGPL-3.0, a real licensing exposure for
closed-source SaaS; `python-docx` for DOCX as one synthetic page, since
`.docx` has no fixed page boundaries in the file itself). A page with no
extractable text is flagged `needs_ocr=true`, never fabricated — no OCR
service is wired up yet. Celery (`apps/api/app/workers/`) is introduced
here: no result backend (outcomes are written straight to Postgres, which
is already the source of truth), no Flower, no queue routing. A worker
task has no HTTP request of its own, so the enqueuing route passes the
caller's own Supabase access token through and the task calls
`get_user_client(access_token)` exactly like a request would — RLS, never
a service-role bypass, still enforces tenant isolation inside the worker.

**Phase 5 — AI control/CUEC/exception extraction.** `0004_ai_extraction.sql`
adds `analysis_jobs` and four extracted-entity tables
(`soc_controls`/`cuecs`/`exceptions`/`subservice_organizations`), each
carrying its own evidence pointer (`document_id`/`page_number`/`excerpt`)
so Phase 8 never needed a separate evidence table. OpenAI's structured
outputs (`chat.completions.parse`, `gpt-4o-mini`) are validated against a
Pydantic schema before anything is persisted; a refused or malformed
response is marked `requires_review`, never silently stored — the model
interprets, it doesn't become the source of truth for what got extracted.
All four entity categories are extracted from the same chunk in one
structured-output call, not four, per the spec's batching rule. Explicit
`POST .../analyze` button — analysis is never auto-chained after
extraction, keeping OpenAI spend a deliberate decision.

**Phase 6 — internal control framework.** `0005_internal_controls.sql`
adds `internal_controls`. Two parsing paths dispatched by content type:
XLSX/CSV parse synchronously and deterministically (`openpyxl`/`csv`,
first sheet only, a small fixed header-synonym list — a 422 if no
description-like column is found, never a silent empty result); PDF/DOCX
fall back to the same AI-extraction machinery as Phase 5, reusing its
chunking unchanged, and every AI-extracted row is marked
`requires_review=true` unconditionally (deterministic rows never are).

**Phase 7 — control mapping engine.** `0006_control_mapping.sql`
introduces `pgvector` — deliberately not before this phase, since nothing
needed vector search earlier — adding `embedding vector(1536)` (matching
`text-embedding-3-small`) to `internal_controls`/`soc_controls`/`cuecs`/`exceptions`
with HNSW indexes, a `control_mappings` table plus
`control_mapping_cuecs`/`control_mapping_exceptions` join tables, and
three `match_*` SQL functions for cosine similarity search. Per internal
control: embeddings are backfilled (idempotent — only `embedding IS NULL`
rows are touched), the top-K candidates above a similarity threshold are
handed to one LLM call that confirms which are genuinely relevant, and
only confirmed matches are persisted; a total LLM failure persists the
raw vector-search candidates as `requires_review` rows instead of
silently dropping them, so Phase 8 can tell "found candidates, AI
confirmation failed" apart from "nothing found at all." Any ID the model
returns that wasn't in the candidate pool it was given is dropped, never
persisted — the candidate set comes from the deterministic vector search,
not the model's imagination.
  **Caught before shipping, not after**: the local-Postgres RLS harness
  (same two-simulated-users methodology as every migration since Phase 2)
  showed the embedding backfill's `UPDATE` silently touching zero rows —
  `internal_controls`/`soc_controls`/`cuecs`/`exceptions` had only ever
  gotten SELECT/INSERT policies (0004/0005 deliberately deferred UPDATE as
  "correcting a bad extraction is Phase 9's job"), but the embedding
  backfill is a different write path — application bookkeeping, not a
  human edit — and needed one now. Added directly to `0006`'s migration
  before it was ever applied anywhere real, verified by re-running the
  RLS check afterward and confirming the UPDATE actually persists for a
  member and is rejected for a non-member.
  The `match_*` functions are plain `language sql`, explicitly **not**
  `security definer` (unlike `is_organization_member()`, which needs that
  to avoid RLS self-recursion inside a policy) — a security-definer
  vector search here would silently bypass RLS and leak cross-tenant
  matches through the similarity search itself. This was verified, not
  just asserted: a non-member calling `match_soc_controls` against the
  same audit period got zero rows back, even though the function's own
  `WHERE` clause only filters by `audit_period_id`, because Postgres still
  applied `soc_controls`' own RLS policy to the function's caller.
  `pgvector` (0.6.0, HNSW included) turned out to be installable in the
  local validation environment, so this migration got the full local RLS
  treatment rather than being deferred as a known gap the way Phase 3's
  Storage policies were.

**Phase 8 — evidence-linked findings.** `0007_findings.sql` adds
`findings` (one row per internal control, upserted on recompute — no
history/versioning). No separate `evidence` table: a finding's evidence
list is assembled at read time by joining
`findings → control_mappings → soc_controls` plus the two junction
tables, since `soc_controls`/`cuecs`/`exceptions` already carry their own
document/page/excerpt. Coverage status is derived by
`app/services/findings.py::derive_coverage` — a pure, deterministic
function, not another LLM call: `NOT_COVERED` when zero mappings exist,
`REQUIRES_REVIEW` when mappings exist but none were AI-confirmed,
`PARTIAL` when a confirmed mapping has a linked CUEC or exception, `FULL`
otherwise. `NOT_APPLICABLE` is not reachable from this logic (no
control-category field was modeled) and stays human-override-only until
Phase 9. `reasoning` is templated from the mapping's own
`relevance_summary` plus counts, not a fresh LLM call. `GET .../findings`
generates fresh short-lived signed URLs for each evidence document at
request time, matching how Phase 3's document view links already work.

**Verified for all five phases**: `apps/api` — 84/84 tests, ruff, mypy
strict all clean. `apps/web` — `npm run build` and `npm run lint` both
clean. Every migration (0003–0007) was applied in order to a local
Postgres instance with a stubbed `auth` schema and exercised as two
simulated tenant users in real transactions — including the upsert/
conflict paths for `document_pages` and `findings`, and, for Phase 7, the
`pgvector` extension and `match_*` RPC functions themselves (not just the
plain tables), which earlier phases assumed would have to be deferred to
a live check.

**Known limitations** (documented, not silently skipped):
- No OCR — a page with no embedded text layer is flagged `needs_ocr`,
  never has text fabricated for it.
- No re-embedding on edits, no re-ranking beyond one cosine-then-LLM
  pass, no reuse of prior-year mappings.
- A Celery task that retries or sits queued past its access token's
  expiry fails with 401 — no retry/refresh is implemented; hasn't come up
  in practice yet.
- `NOT_APPLICABLE` coverage is not automatically derivable and has no
  override UI yet (Phase 9).

### Live verification (done)

The user ran this batch against their real Supabase project and OpenAI
key. That live pass surfaced two genuine RLS bugs neither local validation
nor mocked tests could catch (a missing `documents` UPDATE policy, and a
`control_mappings` re-run idempotency/missing-DELETE-policy pair) — both
fixed and re-verified with the same local RLS harness before being
delivered; see `README.md`'s "Bug found and fixed during live testing"
note and the migration list (0008, 0010).

## Phases 9–15 — what was built (complete)

Built as one batch per the user's explicit instruction ("continue building
9 to 15 without stopping, take all the necessary decisions which result in
feasibility"). Each phase still got its own migration and its own
test/build/lint/mypy gate; every new table or new write path also got the
same local two/three-simulated-user RLS harness used since Phase 2 before
the phase was considered done. Several feasibility/scope calls were made
unilaterally, per that authorization, and are documented per-phase below
rather than silently built or silently skipped.

**Phase 9 — human review.** `0011_finding_reviews.sql` adds
`finding_reviews`: append-only (select/insert RLS only, no update/delete),
same shape as `audit_log` — every review action is a new row, never a
mutation of a prior one. `decision` is `approved` / `overridden` /
`requires_reanalysis`; a CHECK constraint
(`finding_reviews_override_status_shape`, mirrored by a Pydantic
`model_validator` for a clean 422 instead of a raw Postgres error) requires
`override_coverage_status` exactly when `decision='overridden'`, never
otherwise. `GET .../findings` now derives `effective_coverage_status` and
`latest_review` at read time by joining in the latest review row per
finding (ordered by `created_at`) — the original AI-derived
`coverage_status` is never overwritten in place, so the audit trail of
"what the AI said" vs. "what a human decided" stays intact. Frontend: the
findings table's expanded row has three review forms (Approve / Request
re-analysis / Override with a reason), each a plain server-action form —
no client-side decision-dependent field toggling, trading a small amount
of polish for materially less client state.

**Phase 10 — export.** **Feasibility call: Excel only, no PDF this
phase** — a reviewer's actual workflow (sort/filter/comment in a
spreadsheet) is better served by Excel, and adding a second export format
and a PDF-rendering dependency for a phase batch already covering seven
phases wasn't justified without being asked for specifically.
`app/services/export.py::build_findings_workbook` is a pure function
(openpyxl `Workbook` → `BytesIO`) — no Supabase Storage round-trip, no
Celery job; the file is generated and streamed back in the same request
via a plain FastAPI `Response`. `GET .../findings/export.xlsx`. The
frontend can't attach an API bearer token to a plain `<a href>` download,
so `apps/web` proxies it through its own route handler
(`.../findings/export/route.ts`), which reuses the same authenticated
`apiFetch` every other mutation on the page already uses and streams the
response body straight through.

**Phase 11 — risk engine.** `0012_findings_risk_level.sql` adds a nullable
`risk_level` column to `findings`. **Feasibility call: derived, not
AI-scored** — a full risk-scoring model (control criticality, historical
exceptions, business impact weighting) is out of scope for what the spec
itself frames as a v1; instead `app/services/findings.py::derive_risk_level`
is a pure function of `coverage_status` alone
(`NOT_COVERED`/`REQUIRES_REVIEW` → `HIGH`, `PARTIAL` → `MEDIUM`,
`FULL`/`NOT_APPLICABLE` → `LOW`), unit-tested via a parametrized table,
matching the same "LLM/heuristic interprets, deterministic code decides
the stored value" rule used for coverage itself. `effective_risk_level` is
recomputed from `effective_coverage_status` at read time through the same
function — never stored as a second column that could drift out of sync
with a human override. Legacy finding rows written before this migration
have `risk_level IS NULL` in the DB; `list_findings` falls back to
deriving it live for those rows rather than requiring a backfill migration
for a column that's cheap to compute on read.

**Phase 12 — SOC report comparison.** New `app/services/comparison.py` +
`GET /organizations/{id}/compare-audit-periods`. **Feasibility call,
documented in the response schema's own docstring, not silently guessed**:
SOC controls are diffed item-by-item by `control_code` (a stable
identifier, e.g. "CC6.1") into added/removed/changed/unchanged buckets.
CUECs, exceptions, and subservice organizations have no equivalent stable
identifier across two independently-extracted reports — they're reported
as per-period counts only, not matched item-to-item; a real cross-period
semantic match for those would need its own AI matching pass, which is a
new capability, not a "connect what's already there" job like the
control-code diff is. Frontend: a new `/organizations/[orgId]/compare`
page with two audit-period selects (plain GET form, no client JS needed)
and a linked "Compare periods" entry point from the documents page.

**Phase 13 — control intelligence graph.** **Feasibility call: no new
graph/visualization library.** The spec's "control intelligence graph"
novelty is implemented as a `kind` field
(`soc_control`/`cuec`/`exception`) added to the existing `EvidenceRef`
returned by `GET .../findings`, giving each evidence item in a finding's
expanded detail view a labeled relationship (e.g. "this finding is FULL
because of SOC control CC6.1, but PARTIAL because that control also has a
linked Exception"). Every relationship in this data model is exactly one
hop from a finding — there is no multi-hop traversal need that would
justify react-flow/d3/vis.js as a new dependency; the existing
evidence-list UI, now with kind labels, is the correct-sized
implementation.

**Phase 14 — continuous control memory.** **Feasibility call: scoped to
carry-forward, not the full change-detection engine.** The spec's Novelty
6 describes revalidating a prior period's mappings against a new report
and flagging drift automatically — a materially larger feature (would need
its own re-matching/re-confidence pipeline) than fits this batch.
Implemented instead: `POST .../carry-forward-controls?from_audit_period_id=X`
copies `internal_controls` rows from a prior audit period into the current
one (`app/repositories/internal_controls.py::copy_controls`), so a
customer's control framework doesn't need re-uploading every period.
Copied rows are freshly mapped by running "Map controls" again in the new
period — carry-forward does not copy stale mappings across periods.
Frontend: a "Carry forward from…" select + button on the documents page,
listing the org's other audit periods.

**Phase 15 — security hardening and production readiness.** `apps/api/Dockerfile`
— single `python:3.11-slim` image, two entrypoints via CMD override
(`uvicorn` by default; `docker run <image> celery -A app.workers.celery_app
worker --loglevel=info` for the worker) — same dependencies, same code, no
second Dockerfile. `.github/workflows/ci.yml` — two jobs (`api`: pip
install, ruff, mypy, pytest; `web`: npm install, lint, build), on push to
`main` and on every PR. **Feasibility call: this phase is scoped to
packaging + CI, not exhaustive production hardening** — rate limiting,
secret rotation, and malware scanning on uploads are explicitly not built;
listed as known gaps below rather than stubbed out with fake
implementations. Docker's daemon isn't reachable in this build sandbox, so
`docker build` itself couldn't be run here; verified instead by running
the Dockerfile's core `pip install --no-cache-dir .` step in a clean venv
and confirming `from app.main import app` succeeds — a real but partial
substitute for an actual `docker build`, disclosed as such rather than
claimed as a full build verification.

**Verified for all seven phases**: `apps/api` — 102/102 tests, ruff, mypy
strict all clean. `apps/web` — `npm run build` and `npm run lint` both
clean. Migrations 0011–0012 got the same local-Postgres two/three-user RLS
harness as every migration since Phase 2.

**Known limitations** (documented, not silently skipped):
- No PDF export (Phase 10) — Excel only.
- Risk scoring (Phase 11) is a 3-level heuristic derived from coverage
  status alone, not a weighted model incorporating control criticality or
  historical exception data.
- SOC report comparison (Phase 12) matches SOC controls by `control_code`
  only; CUECs/exceptions/subservice orgs are counts-only, not item-matched.
- The "control intelligence graph" (Phase 13) is one-hop evidence
  relationships in the existing findings UI, not a navigable graph
  visualization.
- Continuous control memory (Phase 14) is a manual "carry forward
  controls" copy action, not automatic drift detection between periods.
- No rate limiting, no secret rotation, no malware scanning on uploads, no
  OCR (Phase 15 / standing gap since Phase 4).
- `docker build` was not run in this environment (no Docker daemon
  available); verified indirectly via a clean-venv `pip install`.

## Phase roadmap (for visibility)

1. ~~Project foundation~~ (Phase 1, complete)
2. ~~Auth + organizations + audit periods~~ (Phase 2, complete)
3. ~~Document upload and storage~~ (Phase 3, complete)
4. ~~Document extraction pipeline~~ (Phase 4, complete)
5. ~~AI control/CUEC/exception extraction~~ (Phase 5, complete)
6. ~~Internal control framework~~ (Phase 6, complete)
7. ~~Control mapping engine~~ (Phase 7, complete)
8. ~~Evidence-linked findings~~ (Phase 8, complete)
9. ~~Human review~~ (Phase 9, complete)
10. ~~Excel/PDF export~~ (Phase 10, complete — Excel only, see above)
11. ~~Risk engine~~ (Phase 11, complete — heuristic, see above)
12. ~~SOC report comparison~~ (Phase 12, complete — control-code diff, see above)
13. ~~Control intelligence graph~~ (Phase 13, complete — one-hop evidence labels, see above)
14. ~~Continuous control memory~~ (Phase 14, complete — carry-forward only, see above)
15. ~~Security hardening and production readiness~~ (Phase 15, complete — packaging + CI, see above)
