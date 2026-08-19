-- Phase 3: document upload and secure storage. Classification, extraction,
-- OCR, chunking, and embeddings are Phase 4+ — this migration only
-- registers documents and locks down where their bytes live.
--
-- Depends on 0001_organizations_users_audit_periods.sql for organizations,
-- audit_periods, is_organization_member(), and is_organization_owner() —
-- reused here, not reimplemented.

-- DOCUMENTS -----------------------------------------------------------------

create table documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references organizations(id) on delete cascade,
  audit_period_id uuid not null references audit_periods(id) on delete cascade,
  document_type text not null check (
    document_type in ('soc_report', 'bridge_letter', 'internal_control_framework')
  ),
  file_name text not null,
  -- Storage object path: {organization_id}/{audit_period_id}/{id}-{file_name}
  -- (see storage policies below, which parse organization_id back out of it).
  storage_path text not null unique,
  file_size_bytes bigint not null,
  content_type text not null,
  uploaded_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create index documents_organization_id_idx on documents (organization_id);
create index documents_audit_period_id_idx on documents (audit_period_id);

alter table documents enable row level security;

create policy "members can view documents"
  on documents for select
  using (is_organization_member(organization_id));

create policy "members can register documents"
  on documents for insert
  with check (
    is_organization_member(organization_id) and uploaded_by = auth.uid()
  );

create policy "uploader or owner can delete documents"
  on documents for delete
  using (
    is_organization_member(organization_id)
    and (uploaded_by = auth.uid() or is_organization_owner(organization_id))
  );

-- STORAGE ---------------------------------------------------------------------
--
-- Private bucket — no public URLs. Access is always through a short-lived
-- signed URL that apps/api generates using the caller's own token, so
-- these policies (not app code) are what actually enforce the tenant
-- boundary. Reuses is_organization_member()/is_organization_owner() by
-- parsing the org ID out of the object path, so there is one definition
-- of "who's a member" for both table RLS and storage.
--
-- NOTE: unlike the table policies above, these can't be validated against
-- a plain local Postgres instance (storage.objects/storage.buckets are
-- Supabase Storage infrastructure, not part of core Postgres) — verify
-- against the real project once one exists.

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

create policy "members can view org documents in storage"
  on storage.objects for select
  using (
    bucket_id = 'documents'
    and public.is_organization_member((storage.foldername(name))[1]::uuid)
  );

create policy "members can upload org documents to storage"
  on storage.objects for insert
  with check (
    bucket_id = 'documents'
    and public.is_organization_member((storage.foldername(name))[1]::uuid)
  );

create policy "uploader or owner can delete org documents from storage"
  on storage.objects for delete
  using (
    bucket_id = 'documents'
    and (
      owner = auth.uid()
      or public.is_organization_owner((storage.foldername(name))[1]::uuid)
    )
  );
