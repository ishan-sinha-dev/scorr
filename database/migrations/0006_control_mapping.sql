-- Phase 7: control mapping engine. pgvector is introduced here — not in
-- Phase 5/6's original tables — since it has no real consumer before this
-- phase (spec's "no extension before it has a real consumer" rule).
--
-- Design: embed each internal_control's description, cosine-search the
-- top-K candidate soc_controls/cuecs/exceptions in the same audit period
-- (match_* functions below), then one LLM call over the candidate set
-- confirms which are actually relevant and writes a plain-language
-- relevance_summary. The LLM narrows/explains; it never decides the
-- candidate set on its own (that's the deterministic vector search) and
-- never becomes the source of truth for whether a mapping exists (that's
-- the persisted control_mappings row).

create extension if not exists vector;

-- EMBEDDING COLUMNS -----------------------------------------------------------
--
-- vector(1536) matches text-embedding-3-small (core/config.py
-- openai_embedding_model) — this dimension is a one-way door: changing
-- embedding models later means a new column, not an ALTER of this one.

alter table internal_controls
  add column embedding vector(1536),
  add column mapping_attempted_at timestamptz;

alter table soc_controls add column embedding vector(1536);
alter table cuecs add column embedding vector(1536);
alter table exceptions add column embedding vector(1536);
-- subservice_organizations is deliberately excluded: nothing maps against
-- it semantically (see plan).

-- internal_controls/soc_controls/cuecs/exceptions previously had no UPDATE
-- policy (0004/0005 deliberately left correcting a bad extraction as
-- Phase 9's job). The embedding backfill above is a different write path —
-- application bookkeeping, not a human edit — and needs one now, or every
-- UPDATE ... SET embedding = ... silently touches zero rows under RLS.
-- Row-level (not column-level): the API surface never exposes an
-- arbitrary-column-update endpoint, so this doesn't loosen the trust model.

create policy "members can update internal controls"
  on internal_controls for update using (is_organization_member(organization_id));
create policy "members can update soc controls"
  on soc_controls for update using (is_organization_member(organization_id));
create policy "members can update cuecs"
  on cuecs for update using (is_organization_member(organization_id));
create policy "members can update exceptions"
  on exceptions for update using (is_organization_member(organization_id));

create index internal_controls_embedding_idx on internal_controls
  using hnsw (embedding vector_cosine_ops);
create index soc_controls_embedding_idx on soc_controls
  using hnsw (embedding vector_cosine_ops);
create index cuecs_embedding_idx on cuecs
  using hnsw (embedding vector_cosine_ops);
create index exceptions_embedding_idx on exceptions
  using hnsw (embedding vector_cosine_ops);

-- CONTROL MAPPINGS --------------------------------------------------------------

create table control_mappings (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  internal_control_id uuid not null references internal_controls(id) on delete cascade,
  soc_control_id uuid not null references soc_controls(id) on delete cascade,
  similarity_score double precision not null check (similarity_score between -1 and 1),
  confidence double precision not null check (confidence between 0 and 1),
  relevance_summary text not null,
  requires_review boolean not null default false,
  created_at timestamptz not null default now(),
  unique (internal_control_id, soc_control_id)
);

-- Join tables linking a confirmed mapping to the CUECs/exceptions that
-- came back attached to the same soc_control candidate — this is what
-- lets Phase 8 derive PARTIAL coverage without re-running the vector
-- search. organization_id is carried directly (not joined through), same
-- shape as every other RLS-protected table.

create table control_mapping_cuecs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  control_mapping_id uuid not null references control_mappings(id) on delete cascade,
  cuec_id uuid not null references cuecs(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (control_mapping_id, cuec_id)
);

create table control_mapping_exceptions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  control_mapping_id uuid not null references control_mappings(id) on delete cascade,
  exception_id uuid not null references exceptions(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (control_mapping_id, exception_id)
);

create index control_mappings_organization_id_idx on control_mappings (organization_id);
create index control_mappings_audit_period_id_idx on control_mappings (audit_period_id);
create index control_mappings_internal_control_id_idx on control_mappings (internal_control_id);
create index control_mapping_cuecs_organization_id_idx on control_mapping_cuecs (organization_id);
create index control_mapping_exceptions_organization_id_idx
  on control_mapping_exceptions (organization_id);

alter table control_mappings enable row level security;
alter table control_mapping_cuecs enable row level security;
alter table control_mapping_exceptions enable row level security;

create policy "members can view control mappings"
  on control_mappings for select using (is_organization_member(organization_id));
create policy "members can register control mappings"
  on control_mappings for insert with check (is_organization_member(organization_id));

create policy "members can view control mapping cuecs"
  on control_mapping_cuecs for select using (is_organization_member(organization_id));
create policy "members can register control mapping cuecs"
  on control_mapping_cuecs for insert with check (is_organization_member(organization_id));

create policy "members can view control mapping exceptions"
  on control_mapping_exceptions for select using (is_organization_member(organization_id));
create policy "members can register control mapping exceptions"
  on control_mapping_exceptions for insert with check (is_organization_member(organization_id));

-- VECTOR SEARCH RPCS --------------------------------------------------------------
--
-- Plain `language sql`, explicitly NOT `security definer` — unlike
-- is_organization_member() (which needs SECURITY DEFINER to avoid RLS
-- self-recursion inside a policy). A security-definer vector search here
-- would silently bypass RLS on soc_controls/cuecs/exceptions and leak
-- cross-tenant matches through the similarity search itself; running as
-- the calling (authenticated) role means Postgres still applies each
-- table's own RLS select policy before these results ever reach the
-- caller. Must be called directly by clients (client.rpc(...)), so —
-- like create_organization() in 0001 — needs an explicit EXECUTE grant;
-- ordinary functions default to PUBLIC EXECUTE in Postgres, but Supabase
-- projects lock that down, so this is made explicit rather than relying
-- on the default.

create function match_soc_controls(
  query_embedding vector(1536),
  target_audit_period_id uuid,
  match_count int
)
returns table (
  id uuid,
  document_id uuid,
  page_number int,
  control_code text,
  description text,
  excerpt text,
  similarity double precision
)
language sql
stable
as $$
  select
    soc_controls.id,
    soc_controls.document_id,
    soc_controls.page_number,
    soc_controls.control_code,
    soc_controls.description,
    soc_controls.excerpt,
    1 - (soc_controls.embedding <=> query_embedding) as similarity
  from soc_controls
  where soc_controls.audit_period_id = target_audit_period_id
    and soc_controls.embedding is not null
  order by soc_controls.embedding <=> query_embedding
  limit match_count;
$$;

create function match_cuecs(
  query_embedding vector(1536),
  target_audit_period_id uuid,
  match_count int
)
returns table (
  id uuid,
  document_id uuid,
  page_number int,
  description text,
  excerpt text,
  similarity double precision
)
language sql
stable
as $$
  select
    cuecs.id,
    cuecs.document_id,
    cuecs.page_number,
    cuecs.description,
    cuecs.excerpt,
    1 - (cuecs.embedding <=> query_embedding) as similarity
  from cuecs
  where cuecs.audit_period_id = target_audit_period_id
    and cuecs.embedding is not null
  order by cuecs.embedding <=> query_embedding
  limit match_count;
$$;

create function match_exceptions(
  query_embedding vector(1536),
  target_audit_period_id uuid,
  match_count int
)
returns table (
  id uuid,
  document_id uuid,
  page_number int,
  description text,
  excerpt text,
  similarity double precision
)
language sql
stable
as $$
  select
    exceptions.id,
    exceptions.document_id,
    exceptions.page_number,
    exceptions.description,
    exceptions.excerpt,
    1 - (exceptions.embedding <=> query_embedding) as similarity
  from exceptions
  where exceptions.audit_period_id = target_audit_period_id
    and exceptions.embedding is not null
  order by exceptions.embedding <=> query_embedding
  limit match_count;
$$;

grant execute on function match_soc_controls(vector, uuid, int) to authenticated;
grant execute on function match_cuecs(vector, uuid, int) to authenticated;
grant execute on function match_exceptions(vector, uuid, int) to authenticated;
