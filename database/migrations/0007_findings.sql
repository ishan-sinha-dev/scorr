-- Phase 8: evidence-linked findings. Coverage status is derived by pure,
-- deterministic Python (app/services/findings.py::derive_coverage) reading
-- Phase 7's control_mappings — never another LLM call, and never a status
-- string the LLM invents (spec's "LLM is not the source of truth for app
-- state" rule).
--
-- Deliberately no `evidence` table: soc_controls/cuecs/exceptions (0004)
-- already carry document_id/page_number/excerpt, and cuecs/exceptions are
-- linked to a mapping via control_mapping_cuecs/control_mapping_exceptions
-- (0006). A finding's evidence list is assembled at read time by joining
-- findings -> control_mappings -> soc_controls (+ the two junction
-- tables) — a separate table here would just duplicate that data.

create table findings (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  internal_control_id uuid not null references internal_controls(id) on delete cascade,
  -- Nullable: a NOT_COVERED finding has no mapping to point at.
  control_mapping_id uuid references control_mappings(id) on delete cascade,
  coverage_status text not null check (
    coverage_status in ('FULL', 'PARTIAL', 'NOT_COVERED', 'NOT_APPLICABLE', 'REQUIRES_REVIEW')
  ),
  confidence double precision not null check (confidence between 0 and 1),
  reasoning text not null,
  created_at timestamptz not null default now(),
  -- One current finding per control — recompute upserts on this, no
  -- finding history/versioning (out of scope, see plan).
  unique (internal_control_id)
);

create index findings_organization_id_idx on findings (organization_id);
create index findings_audit_period_id_idx on findings (audit_period_id);

alter table findings enable row level security;

create policy "members can view findings"
  on findings for select using (is_organization_member(organization_id));
create policy "members can register findings"
  on findings for insert with check (is_organization_member(organization_id));
create policy "members can update findings"
  on findings for update using (is_organization_member(organization_id));
