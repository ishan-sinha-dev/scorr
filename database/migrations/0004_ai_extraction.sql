-- Phase 5: AI control/CUEC/exception extraction. Runs staged, structured-
-- output-only OpenAI calls over Phase 4's extracted page text
-- (document_pages, 0003) to identify SOC controls, CUECs, exceptions, and
-- subservice organizations. The LLM interprets; it never becomes the
-- source of truth for application state — every row here is validated
-- against a Pydantic schema before persistence, and a malformed/refused
-- response is marked requires_review, never silently stored.
--
-- No semantic/vector retrieval yet — that's Phase 7, which is also where
-- pgvector gets introduced (not before it has a real consumer).

-- ANALYSIS JOBS -----------------------------------------------------------------
--
-- One row per (document, chunk) run of the structured-extraction stage —
-- the first genuinely one-to-many-per-document job type in the schema
-- (Phase 4's extraction status stayed as two columns on `documents` since
-- there's only ever one extraction run per document).

create table analysis_jobs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  job_type text not null check (job_type in ('structured_extraction')),
  chunk_index int not null,
  status text not null check (
    status in ('pending', 'processing', 'complete', 'failed', 'requires_review')
  ),
  error text,
  created_at timestamptz not null default now()
);

create index analysis_jobs_organization_id_idx on analysis_jobs (organization_id);
create index analysis_jobs_document_id_idx on analysis_jobs (document_id);

alter table analysis_jobs enable row level security;

create policy "members can view analysis jobs"
  on analysis_jobs for select
  using (is_organization_member(organization_id));

create policy "members can register analysis jobs"
  on analysis_jobs for insert
  with check (is_organization_member(organization_id));

create policy "members can update analysis jobs"
  on analysis_jobs for update
  using (is_organization_member(organization_id));

-- EXTRACTED REPORT ENTITIES -------------------------------------------------------
--
-- soc_controls / cuecs / exceptions / subservice_organizations. Each row
-- carries its own evidence pointer (document_id + page_number + excerpt) —
-- this is what Phase 8's findings evidence list reads from directly,
-- rather than a separate `evidence` table duplicating the same data.
--
-- audit_period_id is denormalized here now, deliberately ahead of need:
-- Phase 7's vector similarity search must scope candidates to one audit
-- period without an extra join, and adding this column after Phase 7
-- already has data would be an awkward migration. Costs nothing to add now.

create table soc_controls (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  page_number int not null,
  control_code text,
  description text not null,
  excerpt text not null,
  confidence double precision not null check (confidence between 0 and 1),
  requires_review boolean not null default false,
  created_at timestamptz not null default now()
);

create table cuecs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  page_number int not null,
  description text not null,
  related_control_code text,
  excerpt text not null,
  confidence double precision not null check (confidence between 0 and 1),
  requires_review boolean not null default false,
  created_at timestamptz not null default now()
);

create table exceptions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  page_number int not null,
  description text not null,
  related_control_code text,
  excerpt text not null,
  confidence double precision not null check (confidence between 0 and 1),
  requires_review boolean not null default false,
  created_at timestamptz not null default now()
);

create table subservice_organizations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  page_number int not null,
  name text not null,
  description text,
  excerpt text not null,
  confidence double precision not null check (confidence between 0 and 1),
  requires_review boolean not null default false,
  created_at timestamptz not null default now()
);

create index soc_controls_organization_id_idx on soc_controls (organization_id);
create index soc_controls_audit_period_id_idx on soc_controls (audit_period_id);
create index cuecs_organization_id_idx on cuecs (organization_id);
create index cuecs_audit_period_id_idx on cuecs (audit_period_id);
create index exceptions_organization_id_idx on exceptions (organization_id);
create index exceptions_audit_period_id_idx on exceptions (audit_period_id);
create index subservice_organizations_organization_id_idx on subservice_organizations (organization_id);
create index subservice_organizations_audit_period_id_idx on subservice_organizations (audit_period_id);

alter table soc_controls enable row level security;
alter table cuecs enable row level security;
alter table exceptions enable row level security;
alter table subservice_organizations enable row level security;

-- Same select/insert-for-members shape on all 4 tables. No update/delete
-- policy yet: correcting a bad extraction is Phase 9's (human review) job,
-- deliberately not built here.

create policy "members can view soc controls"
  on soc_controls for select using (is_organization_member(organization_id));
create policy "members can register soc controls"
  on soc_controls for insert with check (is_organization_member(organization_id));

create policy "members can view cuecs"
  on cuecs for select using (is_organization_member(organization_id));
create policy "members can register cuecs"
  on cuecs for insert with check (is_organization_member(organization_id));

create policy "members can view exceptions"
  on exceptions for select using (is_organization_member(organization_id));
create policy "members can register exceptions"
  on exceptions for insert with check (is_organization_member(organization_id));

create policy "members can view subservice organizations"
  on subservice_organizations for select using (is_organization_member(organization_id));
create policy "members can register subservice organizations"
  on subservice_organizations for insert with check (is_organization_member(organization_id));
