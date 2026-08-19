-- Phase 4: document extraction pipeline. Turns an uploaded document's bytes
-- (already in Storage, registered in `documents` — 0002) into page-scoped
-- extracted text, preserving provenance (document_id + page_number) for the
-- evidence-first requirement the whole product is built around.
--
-- AI classification/CUEC extraction is Phase 5 — this migration only stores
-- the deterministic extraction output. No AI/LLM involved here.

-- DOCUMENTS: extraction status -------------------------------------------------
--
-- Nullable/default-NULL, not a "pending"-by-default column: a document
-- whose content type never goes through this pipeline (XLSX/CSV — parsed
-- directly as rows in Phase 6) should show no status at all, not a
-- permanently-stuck 'pending'.

alter table documents
  add column extraction_status text
    check (extraction_status in ('pending', 'processing', 'complete', 'failed')),
  add column extraction_error text;

-- DOCUMENT PAGES ----------------------------------------------------------------

create table document_pages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  page_number int not null,
  text text not null default '',
  -- True whenever extraction found no text layer on this page (a scanned/
  -- image-only page). Never fabricated — this is the honest terminal state
  -- until a real OCR service is integrated (out of scope for Phase 4; no
  -- OCR service is configured yet, and a stub would be a fake AI response).
  needs_ocr boolean not null default false,
  created_at timestamptz not null default now(),
  unique (document_id, page_number)
);

create index document_pages_organization_id_idx on document_pages (organization_id);
create index document_pages_document_id_idx on document_pages (document_id);

alter table document_pages enable row level security;

create policy "members can view document pages"
  on document_pages for select
  using (is_organization_member(organization_id));

create policy "members can register document pages"
  on document_pages for insert
  with check (is_organization_member(organization_id));

-- Re-extraction upserts (on_conflict document_id,page_number) resolve to an
-- UPDATE on the existing row when a page already exists — Postgres requires
-- UPDATE privilege/policy for that path, not just INSERT's WITH CHECK.
create policy "members can update document pages"
  on document_pages for update
  using (is_organization_member(organization_id));

create policy "members can delete document pages"
  on document_pages for delete
  using (is_organization_member(organization_id));
