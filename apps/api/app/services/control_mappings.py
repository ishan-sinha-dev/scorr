from supabase import Client

from app.repositories import control_mappings as control_mappings_repo
from app.schemas.control_mappings import ControlMappingOut
from app.workers.mapping import run_control_mapping


def map_controls(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    actor_user_id: str,
    access_token: str,
) -> None:
    """HTTP-agnostic: only enqueues. The actual mapping run (embedding
    backfill, vector search, LLM confirmation) happens in the worker task,
    mirroring Phase 5's analyze_document()."""
    run_control_mapping.delay(organization_id, audit_period_id, actor_user_id, access_token)


def list_control_mappings(client: Client, *, audit_period_id: str) -> list[ControlMappingOut]:
    rows = control_mappings_repo.list_control_mappings(client, audit_period_id=audit_period_id)
    return [ControlMappingOut.model_validate(row) for row in rows]
