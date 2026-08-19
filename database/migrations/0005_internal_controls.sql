-- Phase 6: internal control framework. Turns the customer's own uploaded
-- control framework (documents.document_type = 'internal_control_framework',
-- already supported since Phase 3) into discrete, structured rows Phase 7's
-- mapping engine can consume.

create table internal_controls (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  -- The customer's own control code, if their framework has one (e.g. a
  -- spreadsheet "Control ID" column) — nullable, since not every source
  -- format has one.
  control_id text,
  description text not null,
  -- e.g. a spreadsheet row number, for tracing a row back to its source —
  -- nullable, since the AI-extraction path (PDF/DOCX) has no row concept.
  source_row_ref text,
  extraction_method text not null check (extraction_method in ('deterministic', 'ai')),
  requires_review boolean not null default false,
  created_at timestamptz not null default now()
);

create index internal_controls_organization_id_idx on internal_controls (organization_id);
create index internal_controls_audit_period_id_idx on internal_controls (audit_period_id);

alter table internal_controls enable row level security;

create policy "members can view internal controls"
  on internal_controls for select
  using (is_organization_member(organization_id));

create policy "members can register internal controls"
  on internal_controls for insert
  with check (is_organization_member(organization_id));
