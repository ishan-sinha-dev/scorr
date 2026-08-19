-- Adds delete support for audit periods. `audit_periods` (0001) shipped
-- with select/insert/update policies only — no delete, since nothing
-- needed to delete one yet.
--
-- Restricted to the period's creator or an organization owner, not any
-- member: every audit_period_id foreign key added since (documents,
-- document_pages, soc_controls/cuecs/exceptions/subservice_organizations,
-- internal_controls, control_mappings + join tables, findings) is
-- `on delete cascade`, so deleting a period deletes everything under it —
-- a more consequential action than the member-level create/update.
--
-- Storage objects for any documents under the deleted period are not
-- cleaned up by this cascade — Postgres deleting a `documents` row has no
-- effect on the actual bytes in Supabase Storage. Same accepted gap
-- already documented for document uploads
-- (apps/api/app/repositories/documents.py::upload_and_register), not
-- newly introduced here.

create policy "creator or owner can delete audit periods"
  on audit_periods for delete
  using (
    is_organization_member(organization_id)
    and (created_by = auth.uid() or is_organization_owner(organization_id))
  );
