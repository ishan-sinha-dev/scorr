-- Phase 11: deterministic risk engine. risk_level is derived purely from
-- coverage_status (see app/services/findings.py::derive_risk_level) — no
-- LLM call, no new inputs collected. Nullable like extraction_status
-- (0003): existing findings rows (if any) show no risk level until the
-- next "Compute findings" recompute, rather than a migration-time backfill
-- guess.

alter table findings
  add column risk_level text check (risk_level in ('LOW', 'MEDIUM', 'HIGH'));
