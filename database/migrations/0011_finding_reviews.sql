-- Phase 9: human review. AI never finalizes a conclusion — a reviewer
-- approves, overrides, or requests re-analysis, and that action is logged
-- (spec section 17). Append-only: a new review row is inserted per
-- action, never updated/deleted, so the review history is itself an audit
-- log. The finding's AI-derived coverage_status (0007) is never
-- overwritten — the *effective* status (AI status, or the latest
-- override) is computed at read time in app/services/findings.py, the
-- same "derive at read time, don't duplicate storage" pattern already
-- used for evidence.

create table finding_reviews (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  finding_id uuid not null references findings(id) on delete cascade,
  reviewer_id uuid not null references auth.users(id),
  decision text not null check (decision in ('approved', 'overridden', 'requires_reanalysis')),
  override_coverage_status text
    check (override_coverage_status in ('FULL', 'PARTIAL', 'NOT_COVERED', 'NOT_APPLICABLE', 'REQUIRES_REVIEW')),
  notes text,
  created_at timestamptz not null default now(),
  -- Never allow arbitrary AI-generated (or reviewer-typo'd) status strings
  -- to slip in disconnected from the decision that's supposed to carry
  -- them — an override must supply a status, and only an override may.
  constraint finding_reviews_override_status_shape check (
    (decision = 'overridden' and override_coverage_status is not null)
    or (decision <> 'overridden' and override_coverage_status is null)
  )
);

create index finding_reviews_organization_id_idx on finding_reviews (organization_id);
create index finding_reviews_finding_id_idx on finding_reviews (finding_id);

alter table finding_reviews enable row level security;

create policy "members can view finding reviews"
  on finding_reviews for select
  using (is_organization_member(organization_id));

create policy "members can record finding reviews"
  on finding_reviews for insert
  with check (is_organization_member(organization_id) and reviewer_id = auth.uid());

-- No update/delete policy: append-only by design, matching how audit_log
-- (0001) itself has none.
