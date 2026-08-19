from typing import Literal

from supabase import Client

from app.repositories import control_mappings as control_mappings_repo
from app.repositories import internal_controls as internal_controls_repo
from app.schemas.control_mappings import ControlMappingOut, MappingStatusOut
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


def get_mapping_status(client: Client, *, audit_period_id: str) -> MappingStatusOut:
    """Polled by the frontend while a "Map controls" run is in flight."""
    controls = internal_controls_repo.list_internal_controls(
        client, audit_period_id=audit_period_id
    )
    total = len(controls)
    mapped = sum(1 for control in controls if control.get("mapping_attempted_at"))
    status: Literal["not_started", "processing", "complete"]
    if mapped == 0:
        status = "not_started"
    elif mapped < total:
        status = "processing"
    else:
        status = "complete"
    return MappingStatusOut(status=status, mapped=mapped, total=total)
