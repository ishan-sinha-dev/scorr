# Migrations

Plain SQL files, applied via the Supabase SQL editor (paste and run) or
`supabase db push` once the project is linked with the Supabase CLI — one
migration mechanism for the one database, not two competing ones.

- `0001_organizations_users_audit_periods.sql` (Phase 2): `organizations`,
  `organization_members`, `audit_periods`, `audit_log`, RLS policies, and
  the `create_organization()` RPC. See
  `docs/architecture/phase0-assessment.md` for the design notes and how
  this was validated before shipping.
