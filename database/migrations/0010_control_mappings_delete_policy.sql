-- `control_mappings` (0006) shipped with select/insert policies only — no
-- delete, since nothing needed to delete one yet. Now needed:
-- app/services/control_mapping.py clears a control's existing mappings at
-- the top of each run before recomputing, so a second "Map controls"
-- click is idempotent instead of hitting control_mappings' unique
-- (internal_control_id, soc_control_id) constraint on re-insert. Without
-- this policy that delete would silently match zero rows under RLS — the
-- same class of bug as 0008 (missing `documents` update policy) and the
-- original Phase 7 embedding-backfill fix folded into 0006 itself: caught
-- here by re-running the same local-Postgres RLS harness before shipping,
-- not discovered live.

create policy "members can delete control mappings"
  on control_mappings for delete
  using (is_organization_member(organization_id));
