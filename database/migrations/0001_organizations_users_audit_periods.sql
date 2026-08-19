-- Phase 2: organizations, membership, audit periods, audit log.
-- Run via the Supabase SQL editor, or `supabase db push` once the project is
-- linked with the CLI (see database/migrations/README.md).
--
-- Design notes:
-- - RLS is enabled on every table; there is no bypass without a policy.
-- - is_organization_member / is_organization_owner are SECURITY DEFINER so
--   policies that reference organization_members don't recurse into RLS on
--   that same table when evaluating themselves.
-- - Organization creation is atomic via create_organization(): one RPC call
--   inserts the org and the creator's owner membership together, so the API
--   layer never needs a multi-statement transaction for it.

create extension if not exists "pgcrypto";

-- ORGANIZATIONS -------------------------------------------------------------

create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

alter table organizations enable row level security;

-- ORGANIZATION MEMBERS --------------------------------------------------------

create table organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'member')),
  created_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create index organization_members_organization_id_idx
  on organization_members (organization_id);
create index organization_members_user_id_idx
  on organization_members (user_id);

alter table organization_members enable row level security;

-- AUDIT PERIODS ---------------------------------------------------------------

create table audit_periods (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  name text not null,
  period_start date not null,
  period_end date not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  constraint audit_periods_period_order check (period_end > period_start)
);

create index audit_periods_organization_id_idx on audit_periods (organization_id);

alter table audit_periods enable row level security;

-- AUDIT LOG ---------------------------------------------------------------

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) on delete cascade,
  actor_user_id uuid not null references auth.users(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index audit_log_organization_id_idx on audit_log (organization_id);

alter table audit_log enable row level security;

-- MEMBERSHIP HELPERS (SECURITY DEFINER — bypass RLS internally to avoid
-- recursive policy evaluation on organization_members) -----------------------

create or replace function is_organization_member(org_id uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from organization_members
    where organization_id = org_id and user_id = auth.uid()
  );
$$;

create or replace function is_organization_owner(org_id uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from organization_members
    where organization_id = org_id and user_id = auth.uid() and role = 'owner'
  );
$$;

-- POLICIES: organizations -----------------------------------------------------

create policy "members can view their organizations"
  on organizations for select
  using (is_organization_member(id));

create policy "owners can update their organizations"
  on organizations for update
  using (is_organization_owner(id));

-- No direct insert policy: creation only happens via create_organization().

-- POLICIES: organization_members ----------------------------------------------

create policy "members can view fellow members"
  on organization_members for select
  using (is_organization_member(organization_id));

create policy "owners can add members"
  on organization_members for insert
  with check (is_organization_owner(organization_id));

create policy "owners can remove members"
  on organization_members for delete
  using (is_organization_owner(organization_id));

-- POLICIES: audit_periods ------------------------------------------------------

create policy "members can view audit periods"
  on audit_periods for select
  using (is_organization_member(organization_id));

create policy "members can create audit periods"
  on audit_periods for insert
  with check (
    is_organization_member(organization_id) and created_by = auth.uid()
  );

create policy "members can update audit periods"
  on audit_periods for update
  using (is_organization_member(organization_id));

-- POLICIES: audit_log ----------------------------------------------------------

create policy "members can view their org's audit log"
  on audit_log for select
  using (
    (organization_id is null and actor_user_id = auth.uid())
    or (organization_id is not null and is_organization_member(organization_id))
  );

create policy "users can write audit log entries for their own actions"
  on audit_log for insert
  with check (actor_user_id = auth.uid());

-- RPC: create_organization -----------------------------------------------------

create or replace function create_organization(org_name text)
returns organizations
language plpgsql
security definer
set search_path = public
as $$
declare
  new_org organizations;
begin
  insert into organizations (name) values (org_name) returning * into new_org;
  insert into organization_members (organization_id, user_id, role)
    values (new_org.id, auth.uid(), 'owner');
  return new_org;
end;
$$;

grant execute on function create_organization(text) to authenticated;
