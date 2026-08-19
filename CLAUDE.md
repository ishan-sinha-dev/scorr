# SOCRR — Engineering Ground Rules

Full build spec lives in the "Socrr" doc in the user's TEST project on
claude.ai. This file is the short version so a session working in this repo
doesn't need the whole spec repeated.

## What this is

A B2B compliance product that analyzes SOC 1/SOC 2 reports against a
customer's internal control framework and produces evidence-linked coverage
findings (FULL / PARTIAL / NOT_COVERED / NOT_APPLICABLE / REQUIRES_REVIEW).
Not a PDF chatbot — every AI conclusion must cite document + page + section,
and a human reviewer approves or overrides before anything is final.

## Non-negotiable rules

- **Evidence-first**: no finding without a traceable source citation.
  Preserve page/section/document provenance through the whole pipeline —
  never destroy it during chunking.
- **LLM is not the source of truth for app state.** Coverage status,
  risk scores, permissions, and workflow are deterministic application
  logic. The LLM interprets; it does not decide status strings — only the
  fixed enum values are valid.
- **Structured outputs only** for AI extraction. Validate before
  persisting; malformed output is marked "requires review," never
  silently stored.
- **Multi-tenant isolation via Postgres RLS**, not just app-layer checks.
  Every tenant-owned table has an `organization_id` and a policy.
- **No over-engineering**: no Kubernetes/Kafka/microservices, no
  speculative abstractions, no tables or endpoints without a current
  consumer. Smallest correct implementation for the phase being built.
- **Staged AI pipeline**: classification → extraction → mapping → risk.
  Never one giant prompt over a whole report. Model names are centralized
  (`apps/api/app/core/config.py`), never hardcoded inline.
- **Server-only secrets**: `SUPABASE_SERVICE_ROLE_KEY` and `OPENAI_API_KEY`
  live in `apps/api` only, never in `apps/web` or shipped to the browser.

## Stack (confirmed, do not swap without a reason)

Next.js/TS/Tailwind/shadcn (`apps/web`) + FastAPI/Pydantic (`apps/api`) +
hosted Supabase (Postgres/pgvector, Auth, Storage) + Redis/Celery (from
Phase 4) + OpenAI (from Phase 5). See `docs/architecture/phase0-assessment.md`
for the reasoning and the full phase list.

## Workflow

One phase at a time (see the phase list in the architecture doc). Don't
start the next phase while the current one has failing tests/build. Before
adding code, check whether it belongs in the phase currently being built —
if not, leave it out and note it instead of building it speculatively.
