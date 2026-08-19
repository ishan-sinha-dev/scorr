from typing import Any, cast

from supabase import Client

from app.schemas.internal_controls import InternalControlExtraction
from app.services.internal_controls_parser import ParsedControl


def insert_deterministic(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    controls: list[ParsedControl],
) -> None:
    if not controls:
        return
    client.table("internal_controls").insert(
        [
            {
                "organization_id": organization_id,
                "audit_period_id": audit_period_id,
                "document_id": document_id,
                "control_id": control.control_id,
                "description": control.description,
                "source_row_ref": control.source_row_ref,
                "extraction_method": "deterministic",
            }
            for control in controls
        ]
    ).execute()


def insert_ai_extracted(
    client: Client,
    *,
    organization_id: str,
    audit_period_id: str,
    document_id: str,
    controls: list[InternalControlExtraction],
) -> None:
    if not controls:
        return
    client.table("internal_controls").insert(
        [
            {
                "organization_id": organization_id,
                "audit_period_id": audit_period_id,
                "document_id": document_id,
                "control_id": control.control_id,
                "description": control.description,
                "extraction_method": "ai",
                # internal_controls has no per-item confidence column (unlike
                # soc_controls/cuecs/exceptions) — extraction_method is the
                # whole signal, so every AI-guessed row is flagged for human
                # confirmation before Phase 7 maps against it. A
                # deterministic spreadsheet parse never sets this.
                "requires_review": True,
            }
            for control in controls
        ]
    ).execute()


def copy_controls(
    client: Client,
    *,
    organization_id: str,
    to_audit_period_id: str,
    source_controls: list[dict[str, Any]],
) -> int:
    """Phase 14 (scoped carry-forward): duplicates rows from a prior
    period's internal_controls into a new one — document_id keeps pointing
    at the *original* document (still a valid row, just filed under a
    different audit_period_id), since the source evidence itself hasn't
    changed. No change-detection against the new SOC report — that's the
    full "continuous control memory" engine, explicitly deferred.
    """
    if not source_controls:
        return 0
    client.table("internal_controls").insert(
        [
            {
                "organization_id": organization_id,
                "audit_period_id": to_audit_period_id,
                "document_id": control["document_id"],
                "control_id": control["control_id"],
                "description": control["description"],
                "source_row_ref": control["source_row_ref"],
                "extraction_method": control["extraction_method"],
                "requires_review": control["requires_review"],
            }
            for control in source_controls
        ]
    ).execute()
    return len(source_controls)


def list_internal_controls(client: Client, *, audit_period_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("internal_controls")
        .select("*")
        .eq("audit_period_id", audit_period_id)
        .order("created_at")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data)
